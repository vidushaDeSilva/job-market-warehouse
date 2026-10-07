"""
test_utils.py

Small unit tests for shared utility functions.

These tests are intentionally lightweight so GitHub Actions can quickly verify
that the Python package imports correctly and core deterministic helpers work.
"""

from datetime import timezone

from job_market.utils import sha256_json, sha256_text, stable_json_dumps, utc_now


def test_utc_now_returns_timezone_aware_datetime() -> None:
    """
    utc_now should return a timezone-aware UTC datetime.
    """

    value = utc_now()

    assert value.tzinfo is not None
    assert value.tzinfo == timezone.utc


def test_stable_json_dumps_is_deterministic() -> None:
    """
    JSON hashing depends on stable key ordering.
    """

    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}

    assert stable_json_dumps(left) == stable_json_dumps(right)


def test_sha256_text_is_deterministic() -> None:
    """
    The same input text should always produce the same hash.
    """

    assert sha256_text("job-market") == sha256_text("job-market")


def test_sha256_json_is_deterministic_for_key_order() -> None:
    """
    JSON hash should not change just because dictionary key order changed.
    """

    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}

    assert sha256_json(left) == sha256_json(right)
