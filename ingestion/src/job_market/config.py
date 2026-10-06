"""
config.py

Central configuration module for the Job Market Analytics Warehouse.

This file loads environment variables from the project's .env file and exposes
them through a Settings object. Keeping configuration in one place avoids
hardcoding secrets and operational settings inside ingestion scripts.

Sprint 3 adds Adzuna reliability settings such as timeout, retry count,
backoff timing, and pause between requests.
"""

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


def find_project_root(start_path: Path | None = None) -> Path:
    """
    Find the project root by searching upward for pyproject.toml.

    Args:
        start_path: Optional path to start searching from. If not provided,
            the search starts from this file.

    Returns:
        Path: Project root directory.

    Raises:
        FileNotFoundError: If pyproject.toml cannot be found.
    """

    current_path = start_path or Path(__file__).resolve()

    for parent in [current_path.parent] + list(current_path.parents):
        if (parent / "pyproject.toml").exists():
            return parent

    raise FileNotFoundError(
        "Could not find project root. Expected pyproject.toml in a parent directory."
    )


PROJECT_ROOT = find_project_root()
ENV_FILE = PROJECT_ROOT / ".env"

# override=True makes the local .env file take priority over stale shell values.
load_dotenv(ENV_FILE, override=True)


def _get_int_env(name: str, default: int) -> int:
    """
    Read an integer environment variable with a safe default.

    Args:
        name: Environment variable name.
        default: Value used when the environment variable is missing.

    Returns:
        int: Parsed integer value.

    Raises:
        ValueError: If the value exists but is not a valid integer.
    """

    value = os.getenv(name)

    if value is None or value == "":
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer. Current value: {value}") from exc


def _get_float_env(name: str, default: float) -> float:
    """
    Read a floating-point environment variable with a safe default.

    Args:
        name: Environment variable name.
        default: Value used when the environment variable is missing.

    Returns:
        float: Parsed float value.

    Raises:
        ValueError: If the value exists but is not a valid number.
    """

    value = os.getenv(name)

    if value is None or value == "":
        return default

    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number. Current value: {value}") from exc


@dataclass(frozen=True)
class Settings:
    """
    Application settings loaded from environment variables.
    """

    app_env: str
    database_url: str

    adzuna_app_id: str | None
    adzuna_app_key: str | None

    adzuna_timeout_seconds: int
    adzuna_max_retries: int
    adzuna_retry_backoff_initial_seconds: float
    adzuna_retry_backoff_max_seconds: float
    adzuna_request_pause_seconds: float


def get_settings() -> Settings:
    """
    Read and validate application settings from environment variables.

    Returns:
        Settings: Validated project settings.

    Raises:
        ValueError: If required settings are missing or invalid.
    """

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. Copy .env.example to .env and fill in your database URL."
        )

    max_retries = _get_int_env("ADZUNA_MAX_RETRIES", 3)

    if max_retries < 0:
        raise ValueError("ADZUNA_MAX_RETRIES must be greater than or equal to 0.")

    timeout_seconds = _get_int_env("ADZUNA_TIMEOUT_SECONDS", 30)

    if timeout_seconds <= 0:
        raise ValueError("ADZUNA_TIMEOUT_SECONDS must be greater than 0.")

    backoff_initial = _get_float_env("ADZUNA_RETRY_BACKOFF_INITIAL_SECONDS", 5.0)
    backoff_max = _get_float_env("ADZUNA_RETRY_BACKOFF_MAX_SECONDS", 60.0)

    if backoff_initial <= 0:
        raise ValueError("ADZUNA_RETRY_BACKOFF_INITIAL_SECONDS must be greater than 0.")

    if backoff_max < backoff_initial:
        raise ValueError(
            "ADZUNA_RETRY_BACKOFF_MAX_SECONDS must be greater than or equal to "
            "ADZUNA_RETRY_BACKOFF_INITIAL_SECONDS."
        )

    request_pause = _get_float_env("ADZUNA_REQUEST_PAUSE_SECONDS", 1.0)

    if request_pause < 0:
        raise ValueError("ADZUNA_REQUEST_PAUSE_SECONDS must be greater than or equal to 0.")

    return Settings(
        app_env=os.getenv("APP_ENV", "dev"),
        database_url=database_url,
        adzuna_app_id=os.getenv("ADZUNA_APP_ID"),
        adzuna_app_key=os.getenv("ADZUNA_APP_KEY"),
        adzuna_timeout_seconds=timeout_seconds,
        adzuna_max_retries=max_retries,
        adzuna_retry_backoff_initial_seconds=backoff_initial,
        adzuna_retry_backoff_max_seconds=backoff_max,
        adzuna_request_pause_seconds=request_pause,
    )


def debug_config() -> None:
    """
    Print safe configuration details for debugging local setup issues.

    This intentionally masks DATABASE_URL because it contains a password.
    """

    settings = get_settings()

    masked_database_url = settings.database_url

    if "@" in masked_database_url:
        _, suffix = masked_database_url.split("@", maxsplit=1)
        masked_database_url = "***@" + suffix

    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"ENV_FILE: {ENV_FILE}")
    print(f"ENV_FILE_EXISTS: {ENV_FILE.exists()}")
    print(f"APP_ENV: {settings.app_env}")
    print(f"DATABASE_URL: {masked_database_url}")
    print(f"ADZUNA_TIMEOUT_SECONDS: {settings.adzuna_timeout_seconds}")
    print(f"ADZUNA_MAX_RETRIES: {settings.adzuna_max_retries}")
    print(
        "ADZUNA_RETRY_BACKOFF_INITIAL_SECONDS: "
        f"{settings.adzuna_retry_backoff_initial_seconds}"
    )
    print(
        "ADZUNA_RETRY_BACKOFF_MAX_SECONDS: "
        f"{settings.adzuna_retry_backoff_max_seconds}"
    )
    print(f"ADZUNA_REQUEST_PAUSE_SECONDS: {settings.adzuna_request_pause_seconds}")