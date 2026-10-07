"""
utils.py

Small utility functions shared by ingestion modules.

These helpers keep repeated low-level logic, such as hashing and timestamp
creation, out of the main ingestion flow.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    """
    Return the current UTC timestamp.

    Using timezone-aware UTC timestamps avoids confusion when the pipeline
    runs from different machines or time zones.
    """

    return datetime.now(timezone.utc)


def stable_json_dumps(value: Any) -> str:
    """
    Convert a Python object into a deterministic JSON string.

    Sorting keys makes hashes stable even if dictionary key order changes.
    """

    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def sha256_text(value: str) -> str:
    """
    Create a SHA-256 hash from text.

    Hashes are useful for request tracking, record identity, and change
    detection without storing sensitive full URLs.
    """

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    """
    Create a SHA-256 hash from a JSON-like Python object.
    """

    return sha256_text(stable_json_dumps(value))
