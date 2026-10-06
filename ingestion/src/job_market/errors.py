"""
errors.py

Custom exception classes for the Job Market Analytics Warehouse.

Sprint 3 uses these exceptions to classify Adzuna API failures into retryable
and non-retryable errors. This helps the ingestion pipeline decide whether to
try again or fail fast.
"""


class JobMarketError(Exception):
    """
    Base exception for project-specific errors.
    """


class AdzunaError(JobMarketError):
    """
    Base exception for Adzuna API-related errors.
    """


class MissingAdzunaCredentialsError(AdzunaError):
    """
    Raised when ADZUNA_APP_ID or ADZUNA_APP_KEY is missing.
    """


class AdzunaRetryableError(AdzunaError):
    """
    Raised for temporary Adzuna/API/network errors that may succeed on retry.

    Examples:
        - network timeout
        - HTTP 500
        - HTTP 502
        - HTTP 503
        - HTTP 504
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.is_retryable = True


class AdzunaRateLimitError(AdzunaRetryableError):
    """
    Raised when Adzuna returns HTTP 429 rate-limit response.
    """

    def __init__(self, message: str = "Adzuna API rate limit reached.") -> None:
        super().__init__(message, status_code=429)


class AdzunaNonRetryableError(AdzunaError):
    """
    Raised for errors that should not be retried.

    Examples:
        - invalid credentials
        - bad request
        - unauthorized request
        - unsupported country code
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.is_retryable = False


class AdzunaResponseFormatError(AdzunaError):
    """
    Raised when the Adzuna response structure is not what the loader expects.
    """