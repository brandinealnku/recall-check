#!/usr/bin/env python3
"""Compatibility entrypoint for FDA XML field naming variations."""
from __future__ import annotations

import refresh_recalls_current as current


def fuzzy_first(record: dict[str, str], *keys: str) -> str:
    """Read exact keys first, then common Drupal/XML-prefixed variants."""
    for key in keys:
        value = current.legacy.clean_text(record.get(key))
        if value:
            return value
    for desired in keys:
        for actual, raw in record.items():
            if actual.endswith("_" + desired) or actual.endswith(desired) or desired in actual:
                value = current.legacy.clean_text(raw)
                if value:
                    return value
    return ""


# Functions in refresh_recalls_current resolve `first` from their module globals at
# call time, so this keeps the tested ingestion logic intact while accepting the
# prefixed field names used by FDA's downloadable XML export.
current.first = fuzzy_first


if __name__ == "__main__":
    current.main()
