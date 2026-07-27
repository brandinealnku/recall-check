#!/usr/bin/env python3
"""RecallCheck 0.2 official recall ingestion (standard library only).

FDA and USDA are fetched independently. A failed agency retains that agency's last
known-good official records; demo data is never read or written by this module.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "recalls.json"
FDA_ENDPOINT = "https://api.fda.gov/food/enforcement.json"
USDA_ENDPOINT = "https://www.fsis.usda.gov/fsis/api/recall/v/1"
WORKFLOW_VERSION = "0.2.0"
RECENT_RECALL_DAYS = int(os.environ.get("RECENT_RECALL_DAYS", "180"))
PAGE_SIZE = 1000
MAX_FDA_RECORDS = 5000
FDA_DIAGNOSTIC_LIMIT = 240

JsonFetcher = Callable[[str, dict[str, str]], tuple[Any, dict[str, str]]]


class FdaRequestError(RuntimeError):
    """An openFDA failure containing only diagnostics safe to persist and log."""

    def __init__(self, *, status: int | None = None, reason: str = "", message: str = "", offset: int = 0, api_key_supplied: bool = False, supplied_key: str | None = None):
        self.diagnostic = {
            "httpStatus": status,
            "httpReason": sanitize_fda_message(reason, supplied_key)[:80],
            "message": sanitize_fda_message(message, supplied_key),
            "paginationOffset": offset,
            "apiKeySupplied": api_key_supplied,
        }
        super().__init__(format_fda_diagnostic(self.diagnostic))


def sanitize_fda_message(value: Any, supplied_key: str | None = None) -> str:
    """Return a short error description without URLs, keys, or key-like fields."""
    text = clean_text(value)
    if supplied_key:
        text = text.replace(supplied_key, "[REDACTED]")
    text = re.sub(r'''(?ix)["']?(api[_-]?key|authorization|token|secret)["']?\s*[=:]\s*["']?[^\s,;}"']+''', r"\1=[REDACTED]", text)
    text = re.sub(r"(?i)https?://\S+", "[URL REMOVED]", text)
    return text[:FDA_DIAGNOSTIC_LIMIT]


def fda_error_message(error: urllib.error.HTTPError, supplied_key: str | None) -> str:
    try:
        raw = error.read(4096).decode("utf-8", errors="replace")
    except Exception:
        raw = ""
    try:
        payload = json.loads(raw)
        candidate = payload.get("error", payload) if isinstance(payload, dict) else payload
        if isinstance(candidate, dict):
            candidate = candidate.get("message") or candidate.get("detail") or candidate.get("code") or ""
        raw = candidate if isinstance(candidate, str) else ""
    except (json.JSONDecodeError, TypeError):
        pass
    return sanitize_fda_message(raw or error.reason or "openFDA request failed", supplied_key)


def format_fda_diagnostic(diagnostic: dict[str, Any]) -> str:
    status = diagnostic.get("httpStatus")
    prefix = f"HTTP {status}" if status is not None else "openFDA error"
    detail = diagnostic.get("message") or diagnostic.get("httpReason") or "request failed"
    return f"{prefix} — {detail} (offset {diagnostic.get('paginationOffset', 0)}, apiKeySupplied={str(bool(diagnostic.get('apiKeySupplied'))).lower()})"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_json(url: str, headers: dict[str, str] | None = None) -> tuple[Any, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "RecallCheck-data-refresh/0.2", **(headers or {})})
    with urllib.request.urlopen(request, timeout=90) as response:
        if "json" not in (response.headers.get("Content-Type") or "").lower():
            raise ValueError("upstream response was not JSON")
        return json.load(response), dict(response.headers)


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))


def parse_date(value: Any) -> str:
    text = clean_text(value)
    for pattern, fmt in ((r"\d{8}", "%Y%m%d"), (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"), (r"\d{1,2}/\d{1,2}/\d{4}", "%m/%d/%Y")):
        if re.fullmatch(pattern, text):
            try:
                return dt.datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                pass
    return ""


def normalize_lifecycle(status: Any, termination_date: Any = None) -> dict[str, Any]:
    """Map agency lifecycle text without treating absent or novel values as active."""
    source = clean_text(status)
    value = source.lower()
    if value in {"ongoing", "active", "open", "current"}:
        state = "active"
    elif value in {"terminated"}:
        state = "terminated"
    elif value in {"completed", "closed"}:
        state = "closed"
    else:
        state = "unknown"
    return {
        "state": state,
        "isActionable": state == "active",
        "sourceStatus": source,
        "terminationDate": parse_date(termination_date),
    }


def normalize_timeline(recall_date: Any, today: dt.date | None = None) -> dict[str, Any]:
    normalized = parse_date(recall_date)
    age = max(0, ((today or dt.date.today()) - dt.date.fromisoformat(normalized)).days) if normalized else 0
    return {"recallDate": normalized, "ageDaysAtRefresh": age, "isRecent": bool(normalized) and age <= RECENT_RECALL_DAYS}


def extract_candidates(*parts: Any) -> dict[str, Any]:
    """Conservative narrative extraction; every value retains method/confidence."""
    text = " ".join(clean_text(part) for part in parts if part)
    identifiers: list[str] = []
    for match in re.finditer(r"(?i)\b(?:UPC|GTIN|EAN)(?:\s*(?:number|no\.?|code))?\s*[:#-]?\s*((?:\d[\s-]*){8,14})\b", text):
        value = re.sub(r"\D", "", match.group(1))
        if len(value) in (8, 12, 13, 14): identifiers.append(value)
    lots = [clean_text(m.group(1)).strip(".,;") for m in re.finditer(r"(?i)\b(?:lot|lot code)\s*(?:no\.?|number|code)?\s*[:#-]\s*([A-Z0-9][A-Z0-9 ./-]{1,30})", text)]
    dates = [clean_text(m.group(0)).strip(".,;") for m in re.finditer(r"(?i)\b(?:best|use|sell|freeze)[ -]?by\s*(?:date)?\s*[:#-]?\s*[A-Z0-9][A-Z0-9, /-]{3,30}", text)]
    sizes = [clean_text(m.group(0)) for m in re.finditer(r"(?i)\b\d+(?:\.\d+)?\s*(?:fl\.?\s*)?(?:oz|ounce|ounces|lb|pound|pounds|g|kg|ml|liter|liters)\b", text)]
    brands = [clean_text(m.group(1)).strip(".,;") for m in re.finditer(r"(?i)\bbrand(?: name)?\s*[:#-]\s*([A-Z0-9][A-Z0-9 '&.-]{1,50})", text)]
    return {
        "identifiers": unique(identifiers), "lotCodes": unique(lots), "dateCodes": unique(dates), "packageSizes": unique(sizes), "brandNames": unique(brands),
        "extraction": {
            "method": "labeled-narrative-regex-v1", "confidence": "high" if identifiers else ("medium" if lots or dates or sizes else "none"),
            "fields": {"identifiers": len(identifiers), "lotCodes": len(lots), "dateCodes": len(dates), "packageSizes": len(sizes), "brandNames": len(brands)}
        }
    }


def split_names(description: str) -> list[str]:
    chunks = re.split(r"[;\n]|\s{2,}", clean_text(description))
    return unique([chunk[:160] for chunk in chunks[:8] if len(chunk) >= 3])


def normalize_fda(record: dict[str, Any]) -> dict[str, Any]:
    description = clean_text(record.get("product_description"))
    code_info = clean_text(record.get("code_info"))
    extraction = extract_candidates(description, code_info, record.get("more_code_info"))
    identifiers = extraction["identifiers"]
    recall_number = clean_text(record.get("recall_number")) or "unknown"
    firm = clean_text(record.get("recalling_firm")) or "Unknown"
    lifecycle = normalize_lifecycle(record.get("status"), record.get("termination_date"))
    timeline = normalize_timeline(record.get("recall_initiation_date"))
    return {
        "id": f"FDA-{recall_number}", "sourceRecordId": recall_number, "agency": "FDA", "type": "recall",
        "status": (clean_text(record.get("status")) or "unknown").lower(), "lifecycle": lifecycle, "timeline": timeline, "classification": clean_text(record.get("classification")) or "unknown",
        "title": f"{firm} — {description[:120] or 'Food recall'}", "recallingFirm": firm, "productDescription": description,
        "brandNames": extraction["brandNames"], "productNames": split_names(description), "upcs": [x for x in identifiers if len(x) in (8, 12, 13)],
        "gtins": [x for x in identifiers if len(x) == 14], "packageSizes": extraction["packageSizes"], "lotCodes": extraction["lotCodes"],
        "dateCodes": unique(extraction["dateCodes"] + ([code_info] if code_info and not extraction["lotCodes"] and not extraction["dateCodes"] else [])),
        "establishmentNumbers": [], "reason": clean_text(record.get("reason_for_recall")) or "Not provided",
        "distribution": clean_text(record.get("distribution_pattern")) or "Not provided", "recallDate": timeline["recallDate"],
        "officialUrl": "https://www.accessdata.fda.gov/scripts/ires/index.cfm#/search/", "extraction": extraction["extraction"],
        "sourceRecord": record, "searchText": clean_text(" ".join([firm, description, code_info])).lower()
    }


def normalize_usda(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize fields returned by the documented FSIS Recall API v1."""
    title = clean_text(record.get("title") or record.get("recall_title"))
    products = clean_text(record.get("product_items") or record.get("products") or record.get("product_description"))
    details = clean_text(record.get("summary") or record.get("description") or record.get("details"))
    extraction = extract_candidates(products, details)
    number = clean_text(record.get("recall_number") or record.get("field_recall_number") or record.get("id")) or "unknown"
    url = clean_text(record.get("url") or record.get("official_url") or record.get("path"))
    if url.startswith("/"): url = "https://www.fsis.usda.gov" + url
    if not url.startswith("https://www.fsis.usda.gov/"): url = "https://www.fsis.usda.gov/recalls"
    alert_text = " ".join([title, clean_text(record.get("recall_type")), details]).lower()
    source_status = record.get("status") or record.get("recall_status") or record.get("closed_date")
    lifecycle = normalize_lifecycle(source_status, record.get("termination_date") or record.get("closed_date"))
    # Some FSIS payload shapes publish only a closure date, not a status label.
    if not (record.get("status") or record.get("recall_status")) and record.get("closed_date"):
        lifecycle["state"] = "closed"
        lifecycle["isActionable"] = False
    timeline = normalize_timeline(record.get("recall_date") or record.get("date"))
    return {
        "id": f"USDA-{number}", "sourceRecordId": number, "agency": "USDA",
        "type": "public-health-alert" if "public health alert" in alert_text else "recall",
        "status": (clean_text(source_status) or "unknown").lower(), "lifecycle": lifecycle, "timeline": timeline,
        "classification": clean_text(record.get("classification") or record.get("recall_classification")) or "unknown",
        "title": title or f"USDA FSIS notice {number}", "recallingFirm": clean_text(record.get("company") or record.get("recalling_firm")) or "Not listed",
        "productDescription": products or details, "brandNames": extraction["brandNames"], "productNames": split_names(products or title),
        "upcs": [x for x in extraction["identifiers"] if len(x) in (8, 12, 13)], "gtins": [x for x in extraction["identifiers"] if len(x) == 14],
        "packageSizes": extraction["packageSizes"], "lotCodes": extraction["lotCodes"], "dateCodes": extraction["dateCodes"],
        "establishmentNumbers": unique(re.findall(r"(?i)\b(?:EST\.?|P)-?\s*\d+[A-Z]?\b", products + " " + details)),
        "reason": clean_text(record.get("reason") or record.get("reason_for_recall")) or details or "See official notice",
        "distribution": clean_text(record.get("distribution") or record.get("states")) or "See official notice",
        "recallDate": timeline["recallDate"], "officialUrl": url,
        "extraction": extraction["extraction"], "sourceRecord": record, "searchText": clean_text(" ".join([title, products, details])).lower()
    }


def fetch_fda(fetcher: JsonFetcher = fetch_json, key: str | None = None) -> list[dict[str, Any]]:
    today = dt.date.today()
    start = (today - dt.timedelta(days=730)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    records: list[dict[str, Any]] = []
    skip = 0
    while skip < MAX_FDA_RECORDS:
        params = {"search": f"recall_initiation_date:[{start}+TO+{end}]", "limit": str(PAGE_SIZE), "skip": str(skip)}
        if key: params["api_key"] = key
        try:
            query = urllib.parse.urlencode(params).replace("%2BTO%2B", "+TO+")
            payload, _ = fetcher(FDA_ENDPOINT + "?" + query, {})
        except urllib.error.HTTPError as exc:
            raise FdaRequestError(status=exc.code, reason=str(exc.reason or ""), message=fda_error_message(exc, key), offset=skip, api_key_supplied=bool(key), supplied_key=key) from None
        except FdaRequestError:
            raise
        except Exception as exc:
            raise FdaRequestError(message=str(exc), offset=skip, api_key_supplied=bool(key), supplied_key=key) from None
        page = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(page, list): raise FdaRequestError(message="malformed FDA response: results is not a list", offset=skip, api_key_supplied=bool(key), supplied_key=key)
        records.extend(page)
        total = int(payload.get("meta", {}).get("results", {}).get("total", len(records)))
        if not page or len(records) >= total or len(page) < PAGE_SIZE: break
        skip += PAGE_SIZE
    if not records: raise FdaRequestError(message="FDA returned no records", offset=skip, api_key_supplied=bool(key), supplied_key=key)
    return [normalize_fda(record) for record in records]


def _usda_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list): return payload
    if isinstance(payload, dict):
        for key in ("results", "data", "recalls"):
            if isinstance(payload.get(key), list): return payload[key]
    raise ValueError("malformed USDA response: record list not found")


def fetch_usda(fetcher: JsonFetcher = fetch_json) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    url = USDA_ENDPOINT
    seen: set[str] = set()
    while url and url not in seen:
        seen.add(url); payload, headers = fetcher(url, {"Accept": "application/json"}); records.extend(_usda_records(payload))
        next_url = payload.get("next") if isinstance(payload, dict) else None
        if not next_url:
            match = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", "")); next_url = match.group(1) if match else None
        url = urllib.parse.urljoin(USDA_ENDPOINT, next_url) if next_url else ""
    if not records: raise ValueError("USDA returned no records")
    return [normalize_usda(record) for record in records]


def valid_existing(payload: Any) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("generatedAt"), str) and isinstance(payload.get("recalls"), list) and isinstance(payload.get("dataHealth"), dict)


def build_dataset(existing: dict[str, Any], fetcher: JsonFetcher = fetch_json, now: str | None = None) -> dict[str, Any]:
    timestamp = now or utc_now(); old = existing.get("recalls", []) if valid_existing(existing) else []
    combined: list[dict[str, Any]] = []; sources: dict[str, Any] = {}; warnings: list[str] = []
    for agency, loader in (("FDA", lambda: fetch_fda(fetcher, os.environ.get("OPENFDA_API_KEY"))), ("USDA", lambda: fetch_usda(fetcher))):
        try:
            records = loader(); combined.extend(records); sources[agency] = {"success": True, "retrievedAt": timestamp, "recordCount": len(records), "error": None}
        except Exception as exc:
            retained = [r for r in old if r.get("agency") == agency and not str(r.get("id", "")).startswith("DEMO-")]
            combined.extend(retained); warning = f"{agency} refresh failed; retained {len(retained)} last-known records"
            warnings.append(warning)
            error = exc.diagnostic if isinstance(exc, FdaRequestError) else {"type": type(exc).__name__, "message": sanitize_fda_message(str(exc))}
            sources[agency] = {"success": False, "retrievedAt": timestamp, "recordCount": len(retained), "error": error}
            if agency == "FDA": print(f"openFDA refresh failed: {format_fda_diagnostic(error)}")
    if not combined: raise RuntimeError("refusing to write an empty official dataset; existing file remains unchanged")
    counts = {agency: sum(r.get("agency") == agency for r in combined) for agency in ("FDA", "USDA")}
    with_ids = sum(bool(r.get("upcs") or r.get("gtins")) for r in combined)
    return {
        "generatedAt": timestamp, "sources": [
            {"agency": "FDA", "name": "openFDA Food Enforcement", "url": "https://open.fda.gov/apis/food/enforcement/"},
            {"agency": "USDA", "name": "USDA FSIS Recall API v1", "url": USDA_ENDPOINT}],
        "dataHealth": {"workflowVersion": WORKFLOW_VERSION, "lastSuccessfulUpdate": timestamp if any(v["success"] for v in sources.values()) else existing.get("dataHealth", {}).get("lastSuccessfulUpdate"), "sources": sources, "recordCountByAgency": counts, "recordsWithIdentifierCandidates": with_ids, "warnings": warnings},
        "recalls": list({r["id"]: r for r in combined}.values())
    }


def write_atomic(output: dict[str, Any], destination: pathlib.Path = OUTPUT) -> None:
    if not valid_existing(output): raise ValueError("generated dataset failed schema validation")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as handle:
        json.dump(output, handle, indent=2, ensure_ascii=False); handle.write("\n"); temporary = pathlib.Path(handle.name)
    json.loads(temporary.read_text(encoding="utf-8")); temporary.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=pathlib.Path, default=OUTPUT); args = parser.parse_args()
    existing = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
    write_atomic(build_dataset(existing), args.output)


if __name__ == "__main__": main()
