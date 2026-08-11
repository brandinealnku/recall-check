#!/usr/bin/env python3
"""Current consumer recall ingestion for RecallCheck.

FDA current recalls are sourced from FDA's official annual firm-issued recall XML.
USDA recalls and public-health alerts are sourced from the documented FSIS Recall
API v1. Each agency is isolated so a failed source retains only that agency's last
known-good records and freshness metadata.
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
WORKFLOW_VERSION = "0.4.1"
Fetcher = Callable[[str, dict[str, str]], tuple[Any, dict[str, str]]]


def fetch_text(url: str, headers: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "RecallCheck-data-refresh/0.4", **(headers or {})})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8", errors="replace"), dict(response.headers)


def canon(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.rsplit("}", 1)[-1].lower()).strip("_")


def flatten(element: ET.Element) -> dict[str, str]:
    fields: dict[str, list[str]] = {}
    for leaf in element.iter():
        if list(leaf):
            continue
        text = legacy.clean_text(leaf.text)
        if text:
            fields.setdefault(canon(leaf.tag), []).append(text)
    return {key: " | ".join(legacy.unique(values)) for key, values in fields.items()}


def first(record: dict[str, Any], *keys: str) -> str:
    """Read exact keys first, then Drupal/XML-prefixed variants such as field_*.

    Both the FDA XML export and FSIS API have changed field prefixes over time, so
    ingestion must match canonical suffixes rather than depend on one payload shape.
    """
    wanted = [canon(key) for key in keys]
    canonical = {canon(str(key)): legacy.clean_text(value) for key, value in record.items()}
    for key in wanted:
        value = canonical.get(key, "")
        if value:
            return value
    for desired in wanted:
        for actual, value in canonical.items():
            if value and (actual.endswith("_" + desired) or actual == desired):
                return value
    return ""


def clean_serialized_list(value: Any) -> str:
    """Turn FSIS stringified arrays into readable text without changing plain strings."""
    text = legacy.clean_text(value)
    if len(text) >= 2 and text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return ""
        parts = [part.strip().strip("'\"") for part in inner.split(",")]
        return ", ".join(part for part in parts if part)
    return text


def _looks_like_fda_record(record: dict[str, str]) -> bool:
    product = first(record, "product_description", "product", "description")
    date = first(record, "fda_publish_date", "publish_date", "company_announcement_date", "recall_date", "date")
    company = first(record, "company_name", "recalling_firm", "company")
    product_type = first(record, "product_type", "product_types", "category")
    return len(record) >= 3 and bool(product) and bool(date or company) and bool(product_type or date)


def parse_fda_xml(xml_text: str) -> list[dict[str, str]]:
    """Parse the FDA annual XML without assuming a fixed wrapper or field prefix.

    The FDA export can wrap rows in one or more container elements. We identify the
    smallest descendant elements that look like individual recall rows, which avoids
    flattening an entire document into one combined record.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise legacy.FdaRequestError(message=f"malformed FDA XML: {exc}") from None

    candidates: list[tuple[ET.Element, dict[str, str]]] = []
    for node in root.iter():
        record = flatten(node)
        if _looks_like_fda_record(record):
            candidates.append((node, record))

    candidate_ids = {id(node) for node, _ in candidates}
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for node, record in candidates:
        if any(id(desc) in candidate_ids for desc in list(node.iter())[1:]):
            continue
        key = (
            first(record, "fda_publish_date", "publish_date", "company_announcement_date", "recall_date", "date"),
            first(record, "company_name", "recalling_firm", "company"),
            first(record, "brand_name_s", "brand_names", "brand_name", "brand"),
            first(record, "product_description", "product", "description"),
        )
        if key not in seen:
            seen.add(key)
            records.append(record)

    if not records:
        raise legacy.FdaRequestError(message="FDA XML contained no usable recall records")
    return records


class FdaXmlLinkParser(HTMLParser):
    def __init__(self, year: int):
        super().__init__()
        self.year = str(year)
        self.href = ""
        self.matches: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self.href = dict(attrs).get("href") or ""

    def handle_data(self, data: str) -> None:
        text = legacy.clean_text(data)
        if self.href and self.year in text and "recall" in text.lower() and "xml" in text.lower():
            self.matches.append(self.href)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self.href = ""


def discover_fda_xml_url(year: int, fetcher: Fetcher = fetch_text) -> str:
    try:
        html, _ = fetcher(FDA_DATASETS_PAGE, {"Accept": "text/html"})
    except urllib.error.HTTPError as exc:
        raise legacy.FdaRequestError(status=exc.code, reason=str(exc.reason or ""), message=legacy.fda_error_message(exc, None)) from None
    except Exception as exc:
        raise legacy.FdaRequestError(message=str(exc)) from None
    parser = FdaXmlLinkParser(year)
    parser.feed(str(html))
    if not parser.matches:
        raise legacy.FdaRequestError(message=f"FDA data sets page did not expose the {year} recalls XML link")
    return urllib.parse.urljoin(FDA_DATASETS_PAGE, parser.matches[0])


def normalize_fda_announcement(record: dict[str, str]) -> dict[str, Any] | None:
    product_type = first(record, "product_type", "product_types", "category")
    if product_type and not re.search(r"(?i)\bfood\b|beverage", product_type):
        return None
    description = first(record, "product_description", "product", "description")
    if not description:
        return None
    brand = first(record, "brand_name_s", "brand_names", "brand_name", "brand")
    firm = first(record, "company_name", "recalling_firm", "company") or "Unknown"
    reason = first(record, "recall_reason_description", "reason_for_announcement", "reason_for_recall", "reason") or "See official notice"
    title = first(record, "title", "recall_title") or f"{firm} — {description[:120]}"
    publish_date = first(record, "fda_publish_date", "publish_date", "company_announcement_date", "recall_date", "date")
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
    extraction = legacy.extract_candidates(combined)
    identifiers = extraction["identifiers"]
    stable = official_url if official_url != FDA_RECALLS_PAGE else "|".join([publish_date, firm, brand, description])
    record_id = "FDA-ANN-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]
    return {
        "id": record_id,
        "sourceRecordId": record_id.removeprefix("FDA-"),
        "agency": "FDA",
        "type": "recall",
        "status": "terminated" if is_terminated else "current",
        "lifecycle": lifecycle,
        "timeline": timeline,
        "classification": "unknown",
        "title": title,
        "recallingFirm": firm,
        "productDescription": description,
        "brandNames": legacy.unique(([brand] if brand else []) + extraction["brandNames"]),
        "productNames": legacy.split_names(description or title),
        "upcs": [x for x in identifiers if len(x) in (8, 12, 13)],
        "gtins": [x for x in identifiers if len(x) == 14],
        "packageSizes": extraction["packageSizes"],
        "lotCodes": extraction["lotCodes"],
        "dateCodes": extraction["dateCodes"],
        "establishmentNumbers": [],
        "reason": reason,
        "distribution": first(record, "distribution", "distribution_pattern") or "See official notice",
        "recallDate": timeline["recallDate"],
        "officialUrl": official_url,
        "extraction": extraction["extraction"],
        "sourceRecord": record,
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


def _truthy(value: Any) -> bool:
    return legacy.clean_text(value).lower() in {"true", "1", "yes", "y", "active"}


def normalize_usda(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize the actual field_* keys returned by the FSIS Recall API v1."""
    title = first(record, "field_title", "title", "recall_title")
    products = first(record, "field_product_items", "product_items", "products", "product_description")
    summary = first(record, "field_summary", "summary", "description", "details")
    press_release = first(record, "field_press_release", "field_en_press_release", "press_release")
    details = legacy.clean_text(" ".join([summary, press_release]))
    number = first(record, "field_recall_number", "recall_number", "id") or "unknown"
    recall_type = clean_serialized_list(first(record, "field_recall_type", "recall_type", "status", "recall_status"))
    active_notice = first(record, "field_active_notice", "active_notice")
    closed_date = first(record, "field_closed_date", "closed_date", "termination_date")
    recall_date = first(record, "field_recall_date", "recall_date", "date")

    type_lower = recall_type.lower()
    active_flag = _truthy(active_notice)
    if active_flag or "active recall" in type_lower:
        lifecycle = legacy.normalize_lifecycle("active")
    elif closed_date or "closed recall" in type_lower or "closed" == type_lower:
        lifecycle = legacy.normalize_lifecycle("closed", closed_date)
    elif "public health alert" in type_lower:
        lifecycle = legacy.normalize_lifecycle("active" if active_flag else "unknown", closed_date)
    else:
        lifecycle = legacy.normalize_lifecycle(recall_type, closed_date)

    source_status = recall_type or ("Active notice" if active_flag else "Status not provided")
    lifecycle["sourceStatus"] = source_status
    if closed_date:
        lifecycle["terminationDate"] = legacy.parse_date(closed_date)

    classification = clean_serialized_list(first(record, "field_recall_classification", "field_recall_classification_2", "classification", "recall_classification")) or "unknown"
    reason = clean_serialized_list(first(record, "field_recall_reason", "reason", "reason_for_recall")) or clean_serialized_list(summary) or "See official notice"
    states = clean_serialized_list(first(record, "field_states", "states"))
    distribution = clean_serialized_list(first(record, "field_distro_list", "distribution")) or states or "See official notice"
    establishment = first(record, "field_establishment", "establishment", "company", "recalling_firm")
    url = first(record, "field_recall_url", "recall_url", "url", "official_url", "path")
    if url.startswith("/"):
        url = "https://www.fsis.usda.gov" + url
    if not url.startswith("https://www.fsis.usda.gov/"):
        url = "https://www.fsis.usda.gov/recalls"

    extraction = legacy.extract_candidates(products, details)
    alert_text = " ".join([title, recall_type, classification]).lower()
    timeline = legacy.normalize_timeline(recall_date)
    return {
        "id": f"USDA-{number}",
        "sourceRecordId": number,
        "agency": "USDA",
        "type": "public-health-alert" if "public health alert" in alert_text else "recall",
        "status": "active" if lifecycle["state"] == "active" else ("closed" if lifecycle["state"] == "closed" else "unknown"),
        "lifecycle": lifecycle,
        "timeline": timeline,
        "classification": classification,
        "title": title or f"USDA FSIS notice {number}",
        "recallingFirm": establishment or "Not listed",
        "productDescription": products or summary,
        "brandNames": extraction["brandNames"],
        "productNames": legacy.split_names(products or title),
        "upcs": [x for x in extraction["identifiers"] if len(x) in (8, 12, 13)],
        "gtins": [x for x in extraction["identifiers"] if len(x) == 14],
        "packageSizes": extraction["packageSizes"],
        "lotCodes": extraction["lotCodes"],
        "dateCodes": extraction["dateCodes"],
        "establishmentNumbers": legacy.unique(re.findall(r"(?i)\b(?:EST\.?|P)-?\s*\d+[A-Z]?\b", products + " " + details + " " + establishment)),
        "reason": reason,
        "distribution": distribution,
        "recallDate": timeline["recallDate"],
        "officialUrl": url,
        "extraction": extraction["extraction"],
        "sourceRecord": record,
        "searchText": legacy.clean_text(" ".join([title, products, details, establishment])).lower(),
    }


def fetch_usda(fetcher: Fetcher = legacy.fetch_json) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    url = USDA_ENDPOINT
    seen: set[str] = set()
    while url and url not in seen:
        seen.add(url)
        payload, headers = fetcher(url, {"Accept": "application/json"})
        records.extend(legacy._usda_records(payload))
        next_url = payload.get("next") if isinstance(payload, dict) else None
        if not next_url:
            match = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", ""))
            next_url = match.group(1) if match else None
        url = urllib.parse.urljoin(USDA_ENDPOINT, next_url) if next_url else ""
    if not records:
        raise ValueError("USDA returned no records")
    return [normalize_usda(record) for record in records]


def newest_recall_date(records: list[dict[str, Any]]) -> str:
    dates = [legacy.parse_date(r.get("recallDate") or r.get("timeline", {}).get("recallDate")) for r in records]
    return max((value for value in dates if value), default="")


def build_dataset(existing: dict[str, Any], fda_fetcher: Fetcher = fetch_text, usda_fetcher: Fetcher = legacy.fetch_json, now: str | None = None) -> dict[str, Any]:
    timestamp = now or legacy.utc_now()
    old = existing.get("recalls", []) if legacy.valid_existing(existing) else []
    old_health = existing.get("dataHealth", {}).get("sources", {}) if isinstance(existing, dict) else {}
    combined: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}
    warnings: list[str] = []

    for agency, loader in (("FDA", lambda: fetch_fda(fda_fetcher)), ("USDA", lambda: fetch_usda(usda_fetcher))):
        try:
            records = loader()
            combined.extend(records)
            sources[agency] = {
                "success": True,
                "checkedAt": timestamp,
                "retrievedAt": timestamp,
                "lastSuccessfulUpdate": timestamp,
                "newestRecallDate": newest_recall_date(records),
                "recordCount": len(records),
                "error": None,
            }
        except Exception as exc:
            retained = [r for r in old if r.get("agency") == agency and not str(r.get("id", "")).startswith("DEMO-")]
            combined.extend(retained)
            warnings.append(f"{agency} refresh failed; retained {len(retained)} last-known records")
            error = exc.diagnostic if isinstance(exc, legacy.FdaRequestError) else {"type": type(exc).__name__, "message": legacy.sanitize_fda_message(str(exc))}
            prior = old_health.get(agency, {}) if isinstance(old_health, dict) else {}
            sources[agency] = {
                "success": False,
                "checkedAt": timestamp,
                "retrievedAt": prior.get("retrievedAt"),
                "lastSuccessfulUpdate": prior.get("lastSuccessfulUpdate") or prior.get("retrievedAt"),
                "newestRecallDate": prior.get("newestRecallDate") or newest_recall_date(retained),
                "recordCount": len(retained),
                "error": error,
            }
            if agency == "FDA":
                print(f"FDA refresh failed: {legacy.format_fda_diagnostic(error)}")

    if not combined:
        raise RuntimeError("refusing to write an empty official dataset; existing file remains unchanged")

    counts = {agency: sum(r.get("agency") == agency for r in combined) for agency in ("FDA", "USDA")}
    successful_times = [v.get("lastSuccessfulUpdate") for v in sources.values() if v.get("lastSuccessfulUpdate")]
    return {
        "generatedAt": timestamp,
        "sources": [
            {"agency": "FDA", "name": "FDA Firm-Issued Recalls XML", "url": FDA_DATASETS_PAGE},
            {"agency": "USDA", "name": "USDA FSIS Recall API v1", "url": USDA_ENDPOINT},
        ],
        "dataHealth": {
            "workflowVersion": WORKFLOW_VERSION,
            "checkedAt": timestamp,
            "lastSuccessfulUpdate": max(successful_times, default=existing.get("dataHealth", {}).get("lastSuccessfulUpdate")),
            "sources": sources,
            "recordCountByAgency": counts,
            "recordsWithIdentifierCandidates": sum(bool(r.get("upcs") or r.get("gtins")) for r in combined),
            "warnings": warnings,
        },
        "recalls": list({r["id"]: r for r in combined}.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=OUTPUT)
    args = parser.parse_args()
    existing = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
    legacy.write_atomic(build_dataset(existing), args.output)


if __name__ == "__main__":
    main()
