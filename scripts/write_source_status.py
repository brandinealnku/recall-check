#!/usr/bin/env python3
"""Write a compact, auditable source-status snapshot from data/recalls.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECALLS = ROOT / "data" / "recalls.json"
OUTPUT = ROOT / "data" / "source-status.json"

payload = json.loads(RECALLS.read_text(encoding="utf-8"))
health = payload.get("dataHealth") or {}
sources = health.get("sources") or {}
recalls = payload.get("recalls") or []

snapshot = {
    "generatedAt": payload.get("generatedAt"),
    "checkedAt": health.get("checkedAt"),
    "workflowVersion": health.get("workflowVersion"),
    "warnings": health.get("warnings") or [],
    "sources": {},
}

for agency in ("FDA", "USDA"):
    source = sources.get(agency) or {}
    normalized = dict(source)

    # The v4 FDA union intentionally bypasses the retired v2 FDA quality wrapper.
    # USDA still comes directly from the FSIS API, so a successful retrieval is the
    # authoritative quality signal for that source. Preserve that explicit state in
    # source-status even when the base dataset did not add the old wrapper fields.
    if agency == "USDA":
        success = source.get("success") is True
        normalized.setdefault("current", success)
        normalized.setdefault("qualityStatus", "current" if success else "unavailable")
        normalized.setdefault("coverageComplete", success)
        normalized.setdefault("coverageMethod", "primary-api")

    snapshot["sources"][agency] = {
        key: normalized.get(key)
        for key in (
            "success",
            "current",
            "qualityStatus",
            "recordCount",
            "checkedAt",
            "lastSuccessfulUpdate",
            "newestRecallDate",
            "coverageComplete",
            "coverageMethod",
            "surfaces",
        )
        if key in normalized
    }

# Keep a small human-auditable sample of FDA records and the official surfaces that
# contributed to each normalized record. This is diagnostic metadata, not a second
# recall database.
fda_records = [item for item in recalls if item.get("agency") == "FDA"]
fda_records.sort(
    key=lambda item: str(item.get("recallDate") or (item.get("timeline") or {}).get("recallDate") or ""),
    reverse=True,
)
snapshot["fdaSample"] = [
    {
        "id": item.get("id"),
        "date": item.get("recallDate") or (item.get("timeline") or {}).get("recallDate"),
        "brandNames": item.get("brandNames") or [],
        "product": item.get("productDescription") or item.get("title"),
        "reason": item.get("reason"),
        "officialUrl": item.get("officialUrl"),
        "sourceSurfaces": item.get("sourceSurfaces") or [],
    }
    for item in fda_records[:20]
]

OUTPUT.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(snapshot, indent=2, sort_keys=True))
