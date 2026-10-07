"""
client.py

Adzuna API client for the Job Market Analytics Warehouse.

The client is responsible for:
1. Building safe Adzuna search requests
2. Calling the Adzuna REST API
3. Classifying API failures as retryable or non-retryable
4. Returning parsed JSON for successful responses

The client does not write to PostgreSQL. Database writes are handled by the
ingestion repository and loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from job_market.config import get_settings
from job_market.errors import (
    AdzunaNonRetryableError,
    AdzunaRateLimitError,
    AdzunaResponseFormatError,
    AdzunaRetryableError,
    MissingAdzunaCredentialsError,
)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"

RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


@dataclass(frozen=True)
class AdzunaSearchRequest:
    """
    Represents one Adzuna search request/page.

    Only non-secret request settings are stored here. API credentials are added
    inside the client when the HTTP request is made.
    """

    country_code: str
    page_number: int
    keyword: str
    location: str
    results_per_page: int


@dataclass(frozen=True)
class AdzunaSearchResponse:
    """
    Represents the response from one successful Adzuna API request/page.
    """

    status_code: int
    request_url: str
    safe_request_params: dict[str, Any]
    response_json: dict[str, Any]


class AdzunaClient:
    """
    Small HTTP client for the Adzuna Jobs API.
    """

    def __init__(self, timeout_seconds: int | None = None) -> None:
        """
        Initialize the Adzuna client.

        Args:
            timeout_seconds: Optional request timeout. If omitted, the value is
                read from project settings.
        """

        settings = get_settings()

        if not settings.adzuna_app_id or settings.adzuna_app_id.startswith("your_"):
            raise MissingAdzunaCredentialsError(
                "ADZUNA_APP_ID is missing or still uses the placeholder value."
            )

        if not settings.adzuna_app_key or settings.adzuna_app_key.startswith("your_"):
            raise MissingAdzunaCredentialsError(
                "ADZUNA_APP_KEY is missing or still uses the placeholder value."
            )

        self.app_id = settings.adzuna_app_id
        self.app_key = settings.adzuna_app_key
        self.timeout_seconds = timeout_seconds or settings.adzuna_timeout_seconds

    def search_jobs(self, request: AdzunaSearchRequest) -> AdzunaSearchResponse:
        """
        Search Adzuna jobs for one configured query and one page.

        Args:
            request: Non-secret Adzuna search parameters.

        Returns:
            AdzunaSearchResponse: Successful parsed API response.

        Raises:
            AdzunaRetryableError: Temporary network/server failure.
            AdzunaRateLimitError: HTTP 429 rate-limit response.
            AdzunaNonRetryableError: Permanent client/auth/config error.
            AdzunaResponseFormatError: Response JSON is invalid or unexpected.
        """

        url = f"{ADZUNA_BASE_URL}/{request.country_code.lower()}/search/{request.page_number}"

        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": request.keyword,
            "results_per_page": request.results_per_page,
        }

        if request.location:
            params["where"] = request.location

        safe_request_params = {
            "country_code": request.country_code.lower(),
            "page_number": request.page_number,
            "keyword": request.keyword,
            "location": request.location,
            "results_per_page": request.results_per_page,
            "app_id_present": bool(self.app_id),
        }

        try:
            response = requests.get(url, params=params, timeout=self.timeout_seconds)

        except requests.Timeout as exc:
            raise AdzunaRetryableError(
                f"Adzuna request timed out after {self.timeout_seconds} seconds."
            ) from exc

        except requests.RequestException as exc:
            raise AdzunaRetryableError(
                f"Temporary network error while calling Adzuna: {exc}"
            ) from exc

        if response.status_code == 429:
            raise AdzunaRateLimitError()

        if response.status_code in RETRYABLE_STATUS_CODES:
            raise AdzunaRetryableError(
                f"Adzuna returned retryable HTTP status {response.status_code}.",
                status_code=response.status_code,
            )

        if 400 <= response.status_code < 500:
            raise AdzunaNonRetryableError(
                f"Adzuna returned non-retryable HTTP status {response.status_code}. "
                f"Response body: {response.text[:500]}",
                status_code=response.status_code,
            )

        if not 200 <= response.status_code < 300:
            raise AdzunaRetryableError(
                f"Adzuna returned unexpected HTTP status {response.status_code}.",
                status_code=response.status_code,
            )

        try:
            response_json = response.json()
        except ValueError as exc:
            raise AdzunaResponseFormatError(
                "Adzuna returned a successful HTTP response, but the body was not valid JSON."
            ) from exc

        if not isinstance(response_json, dict):
            raise AdzunaResponseFormatError("Adzuna response JSON was not an object/dictionary.")

        return AdzunaSearchResponse(
            status_code=response.status_code,
            request_url=response.url,
            safe_request_params=safe_request_params,
            response_json=response_json,
        )
