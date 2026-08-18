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

snapshot = {
    "generatedAt": payload.get("generatedAt"),
    "checkedAt": health.get("checkedAt"),
    "workflowVersion": health.get("workflowVersion"),
    "warnings": health.get("warnings") or [],
    "sources": {},
}

for agency in ("FDA", "USDA"):
    source = sources.get(agency) or {}
    snapshot["sources"][agency] = {
        key: source.get(key)
        for key in (
            "success",
            "current",
            "qualityStatus",
            "recordCount",
            "checkedAt",
            "lastSuccessfulUpdate",
            "newestRecallDate",
            "authoritativeNewestRecallDate",
            "freshnessValidated",
            "freshnessValidatedAt",
            "freshnessLagDays",
            "validationMethod",
            "livePublicRowsSeen",
            "livePublicRowsAdded",
        )
        if key in source
    }

OUTPUT.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(snapshot, indent=2, sort_keys=True))
