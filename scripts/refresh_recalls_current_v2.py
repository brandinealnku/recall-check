#!/usr/bin/env python3
"""Compatibility entrypoint plus independent source-quality validation.

The primary FDA ingestion remains the official annual firm-issued recalls XML. After
that ingestion succeeds, this wrapper independently reads FDA's public recalls table
and compares the newest listed food recall with the newest FDA record in RecallCheck.
A successful HTTP retrieval is therefore no longer treated as proof that the data is
current.
"""
from __future__ import annotations

import datetime as dt
import re
from html.parser import HTMLParser
from typing import Any

import refresh_recalls_current as current


WORKFLOW_VERSION = "0.5.0"


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


class FdaRecallTableParser(HTMLParser):
    """Extract rows from FDA's public Recalls, Market Withdrawals & Safety Alerts table."""

    def __init__(self) -> None:
        super().__init__()
        self.in_row = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name == "tr":
            self.in_row = True
            self.row = []
        elif self.in_row and name in {"td", "th"}:
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            text = current.legacy.clean_text(data)
            if text:
                self.cell_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if self.in_row and self.in_cell and name in {"td", "th"}:
            self.row.append(current.legacy.clean_text(" ".join(self.cell_parts)))
            self.cell_parts = []
            self.in_cell = False
        elif self.in_row and name == "tr":
            if self.row:
                self.rows.append(self.row)
            self.row = []
            self.in_row = False
            self.in_cell = False


def _iso_date(value: str) -> str:
    text = current.legacy.clean_text(value)
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return current.legacy.parse_date(text)


def newest_fda_public_food_date(html: str) -> str:
    """Return the newest food recall date visible in FDA's public recall table."""
    parser = FdaRecallTableParser()
    parser.feed(str(html))
    dates: list[str] = []
    for row in parser.rows:
        combined = " | ".join(row)
        if not re.search(r"(?i)\bFood\s*&\s*Beverages\b|\bFoodborne Illness\b|\bAllergens\b", combined):
            continue
        date_cell = next((cell for cell in row if re.fullmatch(r"\d{2}/\d{2}/\d{4}", cell.strip())), "")
        parsed = _iso_date(date_cell)
        if parsed:
            dates.append(parsed)
    if not dates:
        raise ValueError("FDA public recalls page contained no identifiable food recall rows")
    return max(dates)


def fetch_fda_public_newest_food_date(fetcher=current.fetch_text) -> str:
    html, _headers = fetcher(current.FDA_RECALLS_PAGE, {"Accept": "text/html"})
    return newest_fda_public_food_date(str(html))


def _lag_days(dataset_date: str, authority_date: str) -> int | None:
    try:
        dataset = dt.date.fromisoformat(dataset_date)
        authority = dt.date.fromisoformat(authority_date)
    except (TypeError, ValueError):
        return None
    return max(0, (authority - dataset).days)


def apply_source_quality(dataset: dict[str, Any], fda_fetcher=current.fetch_text) -> dict[str, Any]:
    """Annotate source health with current/stale/unverified quality semantics."""
    health = dataset.setdefault("dataHealth", {})
    health["workflowVersion"] = WORKFLOW_VERSION
    sources = health.setdefault("sources", {})
    warnings = health.setdefault("warnings", [])

    usda = sources.get("USDA")
    if isinstance(usda, dict):
        usda["freshnessValidated"] = bool(usda.get("success"))
        usda["current"] = bool(usda.get("success"))
        usda["qualityStatus"] = "current" if usda.get("success") else "unavailable"
        usda["validationMethod"] = "primary-api"

    fda = sources.get("FDA")
    if not isinstance(fda, dict):
        return dataset
    fda["validationMethod"] = "public-recall-list-vs-annual-xml"
    if not fda.get("success"):
        fda["freshnessValidated"] = False
        fda["current"] = False
        fda["qualityStatus"] = "unavailable"
        return dataset

    try:
        authority_date = fetch_fda_public_newest_food_date(fda_fetcher)
        dataset_date = current.legacy.parse_date(fda.get("newestRecallDate"))
        lag = _lag_days(dataset_date, authority_date)
        fda["freshnessValidated"] = True
        fda["freshnessValidatedAt"] = health.get("checkedAt") or dataset.get("generatedAt")
        fda["authoritativeNewestRecallDate"] = authority_date
        fda["freshnessLagDays"] = lag
        is_current = bool(dataset_date and authority_date and dataset_date >= authority_date)
        fda["current"] = is_current
        fda["qualityStatus"] = "current" if is_current else "stale"
        if not is_current:
            warning = (
                "FDA data may be incomplete: RecallCheck newest FDA record "
                f"{dataset_date or 'unknown'}; FDA public listing newest food recall {authority_date}"
            )
            if warning not in warnings:
                warnings.append(warning)
    except Exception as exc:
        fda["freshnessValidated"] = False
        fda["current"] = False
        fda["qualityStatus"] = "unverified"
        fda["qualityError"] = {
            "type": type(exc).__name__,
            "message": current.legacy.sanitize_fda_message(str(exc)),
        }
        warning = "FDA freshness could not be independently validated against the public recall listing"
        if warning not in warnings:
            warnings.append(warning)
    return dataset


# Functions in refresh_recalls_current resolve `first` and `build_dataset` from their
# module globals at call time. Keep the tested ingestion logic intact while adding
# field-name compatibility and a separate quality layer.
current.first = fuzzy_first
_original_build_dataset = current.build_dataset


def build_dataset_with_quality(existing, fda_fetcher=current.fetch_text, usda_fetcher=current.legacy.fetch_json, now=None):
    dataset = _original_build_dataset(existing, fda_fetcher, usda_fetcher, now)
    return apply_source_quality(dataset, fda_fetcher)


current.build_dataset = build_dataset_with_quality


if __name__ == "__main__":
    current.main()
