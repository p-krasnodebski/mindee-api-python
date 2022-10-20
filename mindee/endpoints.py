import os
from typing import Dict, Optional

import requests

from mindee.input.sources import InputSource
from mindee.logger import logger
from mindee.versions import __version__, get_platform, python_version

MINDEE_API_URL = "https://api.mindee.net/v1"
MINDEE_API_KEY_NAME = "MINDEE_API_KEY"

PLATFORM = get_platform()
USER_AGENT = f"mindee-api-python@v{__version__} python-v{python_version} {PLATFORM}"

OTS_OWNER = "mindee"

INVOICE_VERSION = "3"
INVOICE_URL_NAME = "invoices"

RECEIPT_VERSION = "3"
RECEIPT_URL_NAME = "expense_receipts"

PASSPORT_VERSION = "1"
PASSPORT_URL_NAME = "passport"

BANK_CHECK_VERSION = "1"
BANK_CHECK_URL_NAME = "bank_check"


class Endpoint:
    """Generic API endpoint for a product."""

    owner: str
    url_name: str
    version: str
    key_name: str
    api_key: str = ""
    _url_root: str

    def __init__(
        self,
        owner: str,
        url_name: str,
        version: str,
        key_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Generic API endpoint for a product.

        :param owner: owner of the product
        :param url_name: name of the product as it appears in the URL
        :param version: interface version
        :param key_name: where to find the key in envvars
        """
        self.owner = owner
        self.url_name = url_name
        self.version = version
        self.key_name = key_name or url_name
        if api_key:
            self.api_key = api_key
        else:
            self.set_api_key_from_env()

        self._url_root = (
            f"{MINDEE_API_URL}/products/{self.owner}/{self.url_name}/v{self.version}"
        )

    @property
    def base_headers(self) -> Dict[str, str]:
        """Base headers to send with all API requests."""
        return {
            "Authorization": f"Token {self.api_key}",
            "User-Agent": USER_AGENT,
        }

    def set_api_key_from_env(self) -> None:
        """Set the endpoint's API key from an environment variable, if present."""
        env_key = os.getenv(MINDEE_API_KEY_NAME, "")
        if env_key:
            self.api_key = env_key
            logger.debug("Set API key from environment")

    def predict_req_post(
        self,
        input_source: InputSource,
        include_words: bool = False,
        close_file: bool = True,
    ) -> requests.Response:
        """
        Make a request to POST a document for prediction.

        :param input_source: Input object
        :param include_words: Include raw OCR words in the response
        :param close_file: Whether to `close()` the file after parsing it.
        :return: requests response
        """
        files = {"document": input_source.read_contents(close_file)}
        data = {}
        if include_words:
            data["include_mvision"] = "true"

        response = requests.post(
            f"{self._url_root}/predict",
            files=files,
            headers=self.base_headers,
            data=data,
        )
        return response


class CustomEndpoint(Endpoint):
    def training_req_post(
        self, input_source: InputSource, close_file: bool = True
    ) -> requests.Response:
        """
        Make a request to POST a document for training.

        :param input_source: Input object
        :return: requests response
        :param close_file: Whether to `close()` the file after parsing it.
        """
        files = {"document": input_source.read_contents(close_file)}
        params = {"training": True, "with_candidates": True}

        response = requests.post(
            f"{self._url_root}/predict",
            files=files,
            headers=self.base_headers,
            params=params,
        )
        return response

    def training_async_req_post(
        self, input_source: InputSource, close_file: bool = True
    ) -> requests.Response:
        """
        Make a request to POST a document for training without processing.

        :param input_source: Input object
        :return: requests response
        :param close_file: Whether to `close()` the file after parsing it.
        """
        files = {"document": input_source.read_contents(close_file)}
        params = {"training": True, "async": True}

        response = requests.post(
            f"{self._url_root}/predict",
            files=files,
            headers=self.base_headers,
            params=params,
        )
        return response

    def document_req_get(self, document_id: str) -> requests.Response:
        """
        Make a request to GET annotations for a document.

        :param document_id: ID of the document
        """
        params = {
            "include_annotations": True,
            "include_candidates": True,
            "global_orientation": True,
        }
        response = requests.get(
            f"{self._url_root}/documents/{document_id}",
            headers=self.base_headers,
            params=params,
        )
        return response

    def documents_req_post(self, page_n: int = 1) -> requests.Response:
        """
        Make a request to GET info on all documents.

        :param page_n: Page number
        """
        params = {
            "page": page_n,
        }
        response = requests.get(
            f"{self._url_root}/documents",
            headers=self.base_headers,
            params=params,
        )
        return response

    def annotations_req_post(
        self, document_id: str, annotations: dict
    ) -> requests.Response:
        """
        Make a request to POST annotations for a document.

        :param document_id: ID of the document to annotate
        :param annotations: Annotations object
        :return: requests response
        """
        response = requests.post(
            f"{self._url_root}/documents/{document_id}/annotations",
            headers=self.base_headers,
            json=annotations,
        )
        return response

    def annotations_req_put(
        self, document_id: str, annotations: dict
    ) -> requests.Response:
        """
        Make a request to PUT annotations for a document.

        :param document_id: ID of the document to annotate
        :param annotations: Annotations object
        :return: requests response
        """
        response = requests.put(
            f"{self._url_root}/documents/{document_id}/annotations",
            headers=self.base_headers,
            json=annotations,
        )
        return response


class InvoiceEndpoint(Endpoint):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            owner=OTS_OWNER,
            url_name=INVOICE_URL_NAME,
            version=INVOICE_VERSION,
            key_name="invoice",
            api_key=api_key,
        )


class ReceiptEndpoint(Endpoint):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            owner=OTS_OWNER,
            url_name=RECEIPT_URL_NAME,
            version=RECEIPT_VERSION,
            key_name="receipt",
            api_key=api_key,
        )


class PassportEndpoint(Endpoint):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            owner=OTS_OWNER,
            url_name=PASSPORT_URL_NAME,
            version=PASSPORT_VERSION,
            api_key=api_key,
        )


class BankCheckEndpoint(Endpoint):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            owner=OTS_OWNER,
            url_name=BANK_CHECK_URL_NAME,
            version=BANK_CHECK_VERSION,
            api_key=api_key,
        )


class HTTPException(RuntimeError):
    """An exception relating to HTTP calls."""
