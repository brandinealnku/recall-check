#!/usr/bin/env python3
"""Current consumer recall ingestion for RecallCheck.

FDA current recalls are sourced from FDA's official annual firm-issued recall XML
rather than openFDA enforcement freshness. USDA remains sourced from the documented
FSIS Recall API v1. Each agency is isolated so one source cannot erase the other.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any, Callable

import refresh_recalls as legacy

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "recalls.json"
FDA_DATASETS_PAGE = "https://www.fda.gov/about-fda/open-government-fda-data-sets/recalls-data-sets"
FDA_RECALLS_PAGE = "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts"
USDA_ENDPOINT = legacy.USDA_ENDPOINT
WORKFLOW_VERSION = "0.3.0"
Fetcher = Callable[[str, dict[str, str]], tuple[Any, dict[str, str]]]


def fetch_text(url: str, headers: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "RecallCheck-data-refresh/0.3", **(headers or {})})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8", errors="replace"), dict(response.headers)


def canon(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", tag.rsplit("}", 1)[-1].lower()).strip("_")


def flatten(element: ET.Element) -> dict[str, str]:
    fields: dict[str, list[str]] = {}
    for leaf in element.iter():
        if list(leaf):
            continue
        text = legacy.clean_text(leaf.text)
        if text:
            fields.setdefault(canon(leaf.tag), []).append(text)
    return {key: " | ".join(legacy.unique(values)) for key, values in fields.items()}


def first(record: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = legacy.clean_text(record.get(key))
        if value:
            return value
    return ""


def parse_fda_xml(xml_text: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise legacy.FdaRequestError(message=f"malformed FDA XML: {exc}") from None
    candidates = list(root)
    if len(candidates) == 1 and len(list(candidates[0])) > 1:
        candidates = list(candidates[0])
    records = []
    for node in candidates:
        record = flatten(node)
        product = first(record, "product_description", "product", "description")
        company = first(record, "company_name", "recalling_firm", "company")
        date = first(record, "fda_publish_date", "publish_date", "date", "company_announcement_date", "recall_date")
        if len(record) >= 3 and product and (company or date):
            records.append(record)
    if not records:
        raise legacy.FdaRequestError(message="FDA XML contained no usable recall records")
    return records


class FdaXmlLinkParser(HTMLParser):
    def __init__(self, year: int):
        super().__init__(); self.year = str(year); self.href = ""; self.matches: list[str] = []
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a": self.href = dict(attrs).get("href") or ""
    def handle_data(self, data: str) -> None:
        text = legacy.clean_text(data)
        if self.href and self.year in text and "recall" in text.lower() and "xml" in text.lower():
            self.matches.append(self.href)
    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a": self.href = ""


def discover_fda_xml_url(year: int, fetcher: Fetcher = fetch_text) -> str:
    try:
        html, _ = fetcher(FDA_DATASETS_PAGE, {"Accept": "text/html"})
    except urllib.error.HTTPError as exc:
        raise legacy.FdaRequestError(status=exc.code, reason=str(exc.reason or ""), message=legacy.fda_error_message(exc, None)) from None
    except Exception as exc:
        raise legacy.FdaRequestError(message=str(exc)) from None
    parser = FdaXmlLinkParser(year); parser.feed(str(html))
    if not parser.matches:
        raise legacy.FdaRequestError(message=f"FDA data sets page did not expose the {year} recalls XML link")
    return urllib.parse.urljoin(FDA_DATASETS_PAGE, parser.matches[0])


def normalize_fda_announcement(record: dict[str, str]) -> dict[str, Any] | None:
    product_type = first(record, "product_type", "product_types", "category")
    if product_type and not re.search(r"(?i)\bfood\b|beverage", product_type):
        return None
    description = first(record, "product_description", "product", "description")
    brand = first(record, "brand_name_s", "brand_names", "brand_name", "brand")
    firm = first(record, "company_name", "recalling_firm", "company") or "Unknown"
    reason = first(record, "recall_reason_description", "reason_for_announcement", "reason_for_recall", "reason") or "See official notice"
    title = first(record, "title", "recall_title") or f"{firm} — {description[:120] or 'Food recall'}"
    publish_date = first(record, "fda_publish_date", "publish_date", "date", "company_announcement_date", "recall_date")
    terminated = first(record, "terminated_recall", "terminated", "recall_terminated")
    is_terminated = bool(terminated and terminated.lower() not in {"no", "false", "n", "0", "not terminated"})
    lifecycle = legacy.normalize_lifecycle("terminated" if is_terminated else "active")
    timeline = legacy.normalize_timeline(publish_date)
    official_url = first(record, "url", "link", "recall_url", "press_release_url", "detail_url")
    if official_url.startswith("/"):
        official_url = urllib.parse.urljoin("https://www.fda.gov", official_url)
    if not official_url.startswith("https://www.fda.gov/"):
        official_url = FDA_RECALLS_PAGE
    combined = " ".join([title, brand, description, reason, first(record, "excerpt", "summary")])
    extraction = legacy.extract_candidates(combined); identifiers = extraction["identifiers"]
    stable = official_url if official_url != FDA_RECALLS_PAGE else "|".join([publish_date, firm, brand, description])
    record_id = "FDA-ANN-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]
    return {
        "id": record_id, "sourceRecordId": record_id.removeprefix("FDA-"), "agency": "FDA", "type": "recall",
        "status": "terminated" if is_terminated else "current", "lifecycle": lifecycle, "timeline": timeline, "classification": "unknown",
        "title": title, "recallingFirm": firm, "productDescription": description,
        "brandNames": legacy.unique(([brand] if brand else []) + extraction["brandNames"]), "productNames": legacy.split_names(description or title),
        "upcs": [x for x in identifiers if len(x) in (8, 12, 13)], "gtins": [x for x in identifiers if len(x) == 14],
        "packageSizes": extraction["packageSizes"], "lotCodes": extraction["lotCodes"], "dateCodes": extraction["dateCodes"], "establishmentNumbers": [],
        "reason": reason, "distribution": first(record, "distribution", "distribution_pattern") or "See official notice", "recallDate": timeline["recallDate"],
        "officialUrl": official_url, "extraction": extraction["extraction"], "sourceRecord": record,
        "searchText": legacy.clean_text(" ".join([firm, brand, description, reason, title])).lower(),
    }


def fetch_fda(fetcher: Fetcher = fetch_text, year: int | None = None) -> list[dict[str, Any]]:
    year = year or dt.date.today().year
    xml_url = discover_fda_xml_url(year, fetcher)
    try:
        xml_text, _ = fetcher(xml_url, {"Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1"})
    except urllib.error.HTTPError as exc:
        raise legacy.FdaRequestError(status=exc.code, reason=str(exc.reason or ""), message=legacy.fda_error_message(exc, None)) from None
    except Exception as exc:
        raise legacy.FdaRequestError(message=str(exc)) from None
    records = [item for item in (normalize_fda_announcement(row) for row in parse_fda_xml(str(xml_text))) if item]
    if not records:
        raise legacy.FdaRequestError(message="FDA XML contained no food recall announcements")
    return records


def build_dataset(existing: dict[str, Any], fda_fetcher: Fetcher = fetch_text, usda_fetcher: Fetcher = legacy.fetch_json, now: str | None = None) -> dict[str, Any]:
    timestamp = now or legacy.utc_now(); old = existing.get("recalls", []) if legacy.valid_existing(existing) else []
    combined: list[dict[str, Any]] = []; sources: dict[str, Any] = {}; warnings: list[str] = []
    for agency, loader in (("FDA", lambda: fetch_fda(fda_fetcher)), ("USDA", lambda: legacy.fetch_usda(usda_fetcher))):
        try:
            records = loader(); combined.extend(records); sources[agency] = {"success": True, "retrievedAt": timestamp, "recordCount": len(records), "error": None}
        except Exception as exc:
            retained = [r for r in old if r.get("agency") == agency and not str(r.get("id", "")).startswith("DEMO-")]
            combined.extend(retained); warnings.append(f"{agency} refresh failed; retained {len(retained)} last-known records")
            error = exc.diagnostic if isinstance(exc, legacy.FdaRequestError) else {"type": type(exc).__name__, "message": legacy.sanitize_fda_message(str(exc))}
            sources[agency] = {"success": False, "retrievedAt": timestamp, "recordCount": len(retained), "error": error}
            if agency == "FDA": print(f"FDA refresh failed: {legacy.format_fda_diagnostic(error)}")
    if not combined:
        raise RuntimeError("refusing to write an empty official dataset; existing file remains unchanged")
    counts = {agency: sum(r.get("agency") == agency for r in combined) for agency in ("FDA", "USDA")}
    return {
        "generatedAt": timestamp,
        "sources": [
            {"agency": "FDA", "name": "FDA Firm-Issued Recalls XML", "url": FDA_DATASETS_PAGE},
            {"agency": "USDA", "name": "USDA FSIS Recall API v1", "url": USDA_ENDPOINT},
        ],
        "dataHealth": {
            "workflowVersion": WORKFLOW_VERSION,
            "lastSuccessfulUpdate": timestamp if any(v["success"] for v in sources.values()) else existing.get("dataHealth", {}).get("lastSuccessfulUpdate"),
            "sources": sources, "recordCountByAgency": counts,
            "recordsWithIdentifierCandidates": sum(bool(r.get("upcs") or r.get("gtins")) for r in combined), "warnings": warnings,
        },
        "recalls": list({r["id"]: r for r in combined}.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=pathlib.Path, default=OUTPUT); args = parser.parse_args()
    existing = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
    legacy.write_atomic(build_dataset(existing), args.output)


if __name__ == "__main__":
    main()
