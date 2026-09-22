"""Canonical JSON for material-change deep-equal (PLAN Justin R4)."""

from __future__ import annotations

import json
from typing import Any


def canonical_json(value: Any) -> str:
    """UTF-8, object keys sorted recursively, no insignificant whitespace.

    Numbers remain JSON numbers (not strings). Used only for ``value_struct``
    material-change comparison — ignore confidence/TTL/salience/stub_hash.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def value_struct_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True iff value_structs are materially the same (canonical deep-equal)."""
    return canonical_json(a) == canonical_json(b)
