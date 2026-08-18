#!/usr/bin/env python3
"""RecallCheck FDA source-of-truth pipeline v0.7.

FDA coverage is built from three official surfaces with different publication timing:
1. annual firm-issued recall announcements XML,
2. FDA's public Recalls, Market Withdrawals & Safety Alerts table, and
3. openFDA Food Enforcement (Recall Enterprise System) records.

No single newest date is treated as authoritative for all FDA recalls. Each surface is
retrieved and reported independently, then records are normalized, merged, and
deduplicated. FDA is only marked current when every required surface was reached in
this refresh. A failed surface leaves the union available but marks coverage degraded.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from typing import Any

import refresh_recalls_current_v3 as v3

v2 = v3.v2
current = v3.current
legacy = v3.legacy
WORKFLOW_VERSION = "0.7.0"
FDA_SURFACES = ("annualAnnouncements", "publicAlerts", "enforcement")


def record_date(record: dict[str, Any]) -> str:
    return legacy.parse_date(record.get("recallDate") or record.get("timeline", {}).get("recallDate"))


def newest(records: list[dict[str, Any]]) -> str:
    return max((record_date(item) for item in records if record_date(item)), default="")


def compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", legacy.clean_text(value).lower()).strip()


def tokens(value: Any) -> set[str]:
    return {part for part in compact(value).split() if len(part) > 2 and part not in {"the", "and", "with", "food", "foods", "product", "products"}}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def same_recall(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Conservative cross-surface duplicate test.

    FDA announcement and enforcement dates can differ, so date is a bounded signal,
    not the primary identifier. We require a strong firm/product relationship.
    """
    if a.get("id") == b.get("id"):
        return True
    firm_a, firm_b = tokens(a.get("recallingFirm")), tokens(b.get("recallingFirm"))
    product_a = tokens(a.get("productDescription") or a.get("title"))
    product_b = tokens(b.get("productDescription") or b.get("title"))
    if jaccard(firm_a, firm_b) < 0.5 or jaccard(product_a, product_b) < 0.6:
        return False
    da, db = record_date(a), record_date(b)
    if not da or not db:
        return True
    try:
        return abs((dt.date.fromisoformat(da) - dt.date.fromisoformat(db)).days) <= 45
    except ValueError:
        return False


def surface_for(record: dict[str, Any]) -> str:
    rid = str(record.get("id", ""))
    source = str(record.get("sourceRecord", {}).get("source", "")) if isinstance(record.get("sourceRecord"), dict) else ""
    if rid.startswith("FDA-PUBLIC-") or "public recalls table" in source.lower():
        return "publicAlerts"
    if rid.startswith("FDA-ANN-"):
        return "annualAnnouncements"
    return "enforcement"


def source_ref(record: dict[str, Any], surface: str | None = None) -> dict[str, str]:
    return {
        "surface": surface or surface_for(record),
        "sourceRecordId": legacy.clean_text(record.get("sourceRecordId")),
        "url": legacy.clean_text(record.get("officialUrl")),
    }


def merge_records(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """Merge corroborating official records without inventing fields."""
    out = dict(primary)
    refs = list(out.get("sourceReferences") or [source_ref(primary)])
    candidate_ref = source_ref(secondary)
    if candidate_ref not in refs:
        refs.append(candidate_ref)
    out["sourceReferences"] = refs
    out["sourceSurfaces"] = legacy.unique([r.get("surface", "") for r in refs])

    for key in ("upcs", "gtins", "brandNames", "productNames", "packageSizes", "lotCodes", "dateCodes", "establishmentNumbers"):
        out[key] = legacy.unique(list(out.get(key) or []) + list(secondary.get(key) or []))

    # Prefer a direct FDA.gov detail URL over a generic search page.
    secondary_url = legacy.clean_text(secondary.get("officialUrl"))
    primary_url = legacy.clean_text(out.get("officialUrl"))
    if secondary_url.startswith("https://www.fda.gov/") and (not primary_url.startswith("https://www.fda.gov/") or primary_url == current.FDA_RECALLS_PAGE):
        out["officialUrl"] = secondary_url

    # A documented closed/terminated state is definitive. Otherwise preserve active
    # when at least one official surface explicitly reports it.
    states = {str((item.get("lifecycle") or {}).get("state", "unknown")) for item in (primary, secondary)}
    if "terminated" in states:
        out["lifecycle"] = legacy.normalize_lifecycle("terminated")
        out["status"] = "terminated"
    elif "closed" in states:
        out["lifecycle"] = legacy.normalize_lifecycle("closed")
        out["status"] = "closed"
    elif "active" in states:
        out["lifecycle"] = legacy.normalize_lifecycle("active")
        out["status"] = "current"
    return out


def dedupe_fda(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Prefer public alert records for consumer-facing titles/links, then enforcement,
    # then annual announcements; merge corroborating metadata into that record.
    priority = {"publicAlerts": 3, "enforcement": 2, "annualAnnouncements": 1}
    ordered = sorted(records, key=lambda r: (priority.get(surface_for(r), 0), record_date(r)), reverse=True)
    merged: list[dict[str, Any]] = []
    for item in ordered:
        item = dict(item)
        item["sourceReferences"] = [source_ref(item)]
        item["sourceSurfaces"] = [surface_for(item)]
        match_index = next((i for i, existing in enumerate(merged) if same_recall(existing, item)), None)
        if match_index is None:
            merged.append(item)
        else:
            merged[match_index] = merge_records(merged[match_index], item)
    return sorted(merged, key=record_date, reverse=True)


def surface_status(*, success: bool, records: list[dict[str, Any]], checked_at: str, error: Exception | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": success,
        "checkedAt": checked_at,
        "recordCount": len(records),
        "newestRecallDate": newest(records),
    }
    if error is not None:
        result["error"] = {"type": type(error).__name__, "message": legacy.sanitize_fda_message(str(error))}
    return result


def fetch_public(text_fetcher=current.fetch_text) -> list[dict[str, Any]]:
    html, _ = text_fetcher(current.FDA_RECALLS_PAGE, {"Accept": "text/html"})
    rows = v3.parse_public_food_rows(str(html))
    if not rows:
        raise ValueError("FDA public recall table returned no usable Food & Beverages rows")
    return [v3.normalize_public_row(row) for row in rows]


def fetch_enforcement(json_fetcher=legacy.fetch_json) -> list[dict[str, Any]]:
    return legacy.fetch_fda(json_fetcher, os.environ.get("OPENFDA_API_KEY"))


def build_dataset(existing: dict[str, Any], text_fetcher=current.fetch_text, json_fetcher=legacy.fetch_json, now: str | None = None) -> dict[str, Any]:
    timestamp = now or legacy.utc_now()

    # Base pipeline independently retrieves annual FDA announcements and USDA FSIS.
    dataset = v2._original_build_dataset(existing, text_fetcher, json_fetcher, timestamp)
    health = dataset.setdefault("dataHealth", {})
    health["workflowVersion"] = WORKFLOW_VERSION
    health["checkedAt"] = timestamp
    sources = health.setdefault("sources", {})
    fda_health = sources.setdefault("FDA", {})
    warnings = health.setdefault("warnings", [])

    base_fda = [r for r in dataset.get("recalls", []) if r.get("agency") == "FDA"]
    non_fda = [r for r in dataset.get("recalls", []) if r.get("agency") != "FDA"]
    annual_success = fda_health.get("success") is True
    annual_records = [r for r in base_fda if surface_for(r) == "annualAnnouncements"] or base_fda

    surfaces: dict[str, Any] = {
        "annualAnnouncements": surface_status(success=annual_success, records=annual_records, checked_at=timestamp),
    }
    if not annual_success and fda_health.get("error"):
        surfaces["annualAnnouncements"]["error"] = fda_health.get("error")

    public_records: list[dict[str, Any]] = []
    try:
        public_records = fetch_public(text_fetcher)
        surfaces["publicAlerts"] = surface_status(success=True, records=public_records, checked_at=timestamp)
    except Exception as exc:
        surfaces["publicAlerts"] = surface_status(success=False, records=[], checked_at=timestamp, error=exc)

    enforcement_records: list[dict[str, Any]] = []
    try:
        enforcement_records = fetch_enforcement(json_fetcher)
        surfaces["enforcement"] = surface_status(success=True, records=enforcement_records, checked_at=timestamp)
    except Exception as exc:
        surfaces["enforcement"] = surface_status(success=False, records=[], checked_at=timestamp, error=exc)

    fda_union = dedupe_fda(annual_records + public_records + enforcement_records)
    if not fda_union:
        # Preserve last-known FDA records if all current source surfaces failed.
        fda_union = [r for r in existing.get("recalls", []) if r.get("agency") == "FDA"]

    all_surfaces_ok = all(bool(surfaces.get(name, {}).get("success")) for name in FDA_SURFACES)
    any_surface_ok = any(bool(surfaces.get(name, {}).get("success")) for name in FDA_SURFACES)
    quality = "current" if all_surfaces_ok else ("degraded" if any_surface_ok and fda_union else "unavailable")

    fda_health.clear()
    fda_health.update({
        "success": any_surface_ok,
        "checkedAt": timestamp,
        "lastSuccessfulUpdate": timestamp if any_surface_ok else existing.get("dataHealth", {}).get("sources", {}).get("FDA", {}).get("lastSuccessfulUpdate"),
        "recordCount": len(fda_union),
        "newestRecallDate": newest(fda_union),
        "current": all_surfaces_ok,
        "qualityStatus": quality,
        "coverageComplete": all_surfaces_ok,
        "coverageMethod": "official-fda-multi-surface-union-v1",
        "surfaces": surfaces,
        "error": None if any_surface_ok else {"type": "CoverageUnavailable", "message": "No FDA source surface completed successfully"},
    })

    # Remove obsolete single-authority fields and warnings. Different FDA surfaces
    # have different publication timing and none is a complete universal clock.
    for obsolete in ("authoritativeNewestRecallDate", "freshnessLagDays", "freshnessValidated", "freshnessValidatedAt", "validationMethod", "livePublicRowsSeen", "livePublicRowsAdded", "qualityError"):
        fda_health.pop(obsolete, None)
    warnings[:] = [w for w in warnings if not str(w).startswith("FDA data may be incomplete:") and "FDA freshness" not in str(w)]
    if not all_surfaces_ok:
        failed = [name for name in FDA_SURFACES if not surfaces.get(name, {}).get("success")]
        warnings.append("FDA coverage is degraded: unavailable source surface(s): " + ", ".join(failed))

    dataset["recalls"] = sorted(non_fda + fda_union, key=record_date, reverse=True)
    health["recordCountByAgency"] = {
        "FDA": len(fda_union),
        "USDA": sum(r.get("agency") == "USDA" for r in non_fda),
    }
    dataset["sources"] = [
        {"agency": "FDA", "name": "FDA official multi-source coverage", "url": current.FDA_RECALLS_PAGE},
        {"agency": "USDA", "name": "USDA FSIS Recall API v1", "url": legacy.USDA_ENDPOINT},
    ]
    return dataset


current.build_dataset = build_dataset


if __name__ == "__main__":
    current.main()
