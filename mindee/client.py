import json
from typing import BinaryIO, Dict, Optional, Type

from mindee.documents.base import Document, TypeDocument
from mindee.documents.config import DocumentConfig, DocumentConfigDict
from mindee.documents.custom.custom_v1 import CustomV1
from mindee.documents.financial.financial_v1 import FinancialV1
from mindee.documents.invoice.invoice_v3 import InvoiceV3
from mindee.documents.passport.passport_v1 import PassportV1
from mindee.documents.receipt.receipt_v3 import ReceiptV3
from mindee.documents.receipt.receipt_v4 import ReceiptV4
from mindee.documents.us.bank_check.bank_check_v1 import BankCheckV1
from mindee.endpoints import OTS_OWNER, CustomEndpoint, HTTPException, StandardEndpoint
from mindee.input.page_options import PageOptions
from mindee.input.sources import (
    Base64Input,
    BytesInput,
    FileInput,
    InputSource,
    PathInput,
)
from mindee.logger import logger
from mindee.response import PredictResponse


def get_bound_classname(type_var) -> str:
    """Get the name of the bound class."""
    return type_var.__bound__.__name__


class DocumentClient:
    input_doc: InputSource
    doc_configs: DocumentConfigDict
    raise_on_error: bool = True

    def __init__(
        self,
        input_doc: InputSource,
        doc_configs: DocumentConfigDict,
        raise_on_error: bool,
    ):
        self.raise_on_error = raise_on_error
        self.doc_configs = doc_configs
        self.input_doc = input_doc

    def parse(
        self,
        document_class: TypeDocument,
        endpoint_name: Optional[str] = None,
        account_name: Optional[str] = None,
        include_words: bool = False,
        close_file: bool = True,
        page_options: Optional[PageOptions] = None,
    ) -> PredictResponse[TypeDocument]:
        """
        Call prediction API on the document and parse the results.

        :type document_class: DocT
        :param endpoint_name: Document type to parse
        :param account_name: API username, the endpoint owner
        :param include_words: Include all the words of the document in the response
        :param close_file: Whether to `close()` the file after parsing it.
            Set to `False` if you need to access the file after this operation.
        :param page_options: PageOptions object for cutting multipage documents.
        """
        if get_bound_classname(document_class) != CustomV1.__name__:
            endpoint_name = get_bound_classname(document_class)
        elif endpoint_name is None:
            raise RuntimeError("document_type is required for CustomDocument")

        logger.debug("Parsing document as '%s'", endpoint_name)

        found = []
        for k in self.doc_configs.keys():
            if k[1] == endpoint_name:
                found.append(k)

        if len(found) == 0:
            raise RuntimeError(f"Document type not configured: {endpoint_name}")

        if account_name:
            config_key = (account_name, endpoint_name)
        elif len(found) == 1:
            config_key = found[0]
        else:
            usernames = [k[0] for k in found]
            raise RuntimeError(
                (
                    "Duplicate configuration detected.\n"
                    f"You specified a document_type '{endpoint_name}' in your custom config.\n"
                    "To avoid confusion, please add the 'account_name' attribute to "
                    f"the parse method, one of {usernames}."
                )
            )

        doc_config = self.doc_configs[config_key]
        doc_config.check_api_keys()
        if page_options and self.input_doc.is_pdf():
            self.input_doc.process_pdf(
                page_options.operation,
                page_options.on_min_pages,
                page_options.page_indexes,
            )
        return self._make_request(document_class, doc_config, include_words, close_file)

    def _make_request(
        self,
        document_class: TypeDocument,
        doc_config: DocumentConfig,
        include_words: bool,
        close_file: bool,
    ) -> PredictResponse[TypeDocument]:
        if get_bound_classname(document_class) != doc_config.document_class.__name__:
            raise RuntimeError("Document class mismatch!")

        response = doc_config.document_class.request(
            doc_config.endpoints,
            self.input_doc,
            include_words=include_words,
            close_file=close_file,
        )

        dict_response = response.json()

        if not response.ok and self.raise_on_error:
            raise HTTPException(
                "API %s HTTP error: %s"
                % (response.status_code, json.dumps(dict_response))
            )
        return PredictResponse[TypeDocument](
            http_response=dict_response,
            doc_config=doc_config,
            input_source=self.input_doc,
            response_ok=response.ok,
        )

    def close(self) -> None:
        """Close the file object."""
        self.input_doc.file_object.close()


class Client:
    """
    Mindee API Client.

    See: https://developers.mindee.com/docs/
    """

    _doc_configs: DocumentConfigDict
    raise_on_error: bool
    api_key: str

    def __init__(self, api_key: str = "", raise_on_error: bool = True):
        """
        Mindee API Client.

        :param api_key: Your API key for all endpoints
        :param raise_on_error: Raise an Exception on HTTP errors
        """
        self._doc_configs: Dict[tuple, DocumentConfig] = {}
        self.raise_on_error = raise_on_error
        self.api_key = api_key
        self._init_default_endpoints()

    def _init_default_endpoints(self) -> None:
        self._doc_configs = {
            (OTS_OWNER, InvoiceV3.__name__): DocumentConfig(
                document_type="invoice_v3",
                document_class=InvoiceV3,
                endpoints=[
                    StandardEndpoint(
                        url_name="invoices", version="3", api_key=self.api_key
                    )
                ],
            ),
            (OTS_OWNER, ReceiptV3.__name__): DocumentConfig(
                document_type="receipt_v3",
                document_class=ReceiptV3,
                endpoints=[
                    StandardEndpoint(
                        url_name="expense_receipts", version="3", api_key=self.api_key
                    )
                ],
            ),
            (OTS_OWNER, ReceiptV4.__name__): DocumentConfig(
                document_type="receipt_v3",
                document_class=ReceiptV4,
                endpoints=[
                    StandardEndpoint(
                        url_name="expense_receipts", version="4", api_key=self.api_key
                    )
                ],
            ),
            (OTS_OWNER, FinancialV1.__name__): DocumentConfig(
                document_type="financial_doc",
                document_class=FinancialV1,
                endpoints=[
                    StandardEndpoint(
                        url_name="invoices", version="3", api_key=self.api_key
                    ),
                    StandardEndpoint(
                        url_name="expense_receipts", version="3", api_key=self.api_key
                    ),
                ],
            ),
            (OTS_OWNER, PassportV1.__name__): DocumentConfig(
                document_type="passport_v1",
                document_class=PassportV1,
                endpoints=[
                    StandardEndpoint(
                        url_name="passport", version="1", api_key=self.api_key
                    )
                ],
            ),
            (OTS_OWNER, BankCheckV1.__name__): DocumentConfig(
                document_type="bank_check_v1",
                document_class=BankCheckV1,
                endpoints=[
                    StandardEndpoint(
                        url_name="bank_check", version="1", api_key=self.api_key
                    )
                ],
            ),
        }

    def add_endpoint(
        self,
        account_name: str,
        endpoint_name: str,
        version: str = "1",
        document_class: Type[Document] = CustomV1,
    ) -> "Client":
        """
        Add a custom endpoint, created using the Mindee API Builder.

        :param endpoint_name: The "API name" field in the "Settings" page of the API Builder
        :param account_name: Your organization's username on the API Builder
        :param version: If set, locks the version of the model to use.
            If not set, use the latest version of the model.
        :param document_class: A document class in which the response will be extracted.
            Must inherit from ``mindee.documents.base.Document``.
        """
        self._doc_configs[(account_name, endpoint_name)] = DocumentConfig(
            document_type=endpoint_name,
            document_class=document_class,
            endpoints=[
                CustomEndpoint(
                    owner=account_name,
                    url_name=endpoint_name,
                    version=version,
                    api_key=self.api_key,
                ),
            ],
        )
        return self

    def doc_from_path(
        self,
        input_path: str,
    ) -> DocumentClient:
        """
        Load a document from an absolute path, as a string.

        :param input_path: Path of file to open
        """
        input_doc = PathInput(input_path)
        return DocumentClient(
            input_doc=input_doc,
            doc_configs=self._doc_configs,
            raise_on_error=self.raise_on_error,
        )

    def doc_from_file(
        self,
        input_file: BinaryIO,
    ) -> DocumentClient:
        """
        Load a document from a normal Python file object/handle.

        :param input_file: Input file handle
        """
        input_doc = FileInput(
            input_file,
        )
        return DocumentClient(
            input_doc=input_doc,
            doc_configs=self._doc_configs,
            raise_on_error=self.raise_on_error,
        )

    def doc_from_b64string(
        self,
        input_string: str,
        filename: str,
    ) -> DocumentClient:
        """
        Load a document from a base64 encoded string.

        :param input_string: Input to parse as base64 string
        :param filename: The name of the file (without the path)
        """
        input_doc = Base64Input(
            input_string,
            filename,
        )
        return DocumentClient(
            input_doc=input_doc,
            doc_configs=self._doc_configs,
            raise_on_error=self.raise_on_error,
        )

    def doc_from_bytes(
        self,
        input_bytes: bytes,
        filename: str,
    ) -> DocumentClient:
        """
        Load a document from raw bytes.

        :param input_bytes: Raw byte input
        :param filename: The name of the file (without the path)
        """
        input_doc = BytesInput(
            input_bytes,
            filename,
        )
        return DocumentClient(
            input_doc=input_doc,
            doc_configs=self._doc_configs,
            raise_on_error=self.raise_on_error,
        )
