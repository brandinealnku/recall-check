#!/usr/bin/env python3
"""Finalize canonical FDA/USDA health metadata in data/recalls.json.

RecallCheck has one source-health contract. Consumer UI and the compact
source-status snapshot must both derive from the same metadata stored in
recalls.json. This module fills the USDA quality fields that the v4 FDA union
pipeline intentionally no longer receives from the retired v2 quality wrapper.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECALLS = ROOT / "data" / "recalls.json"


def finalize(payload: dict[str, Any]) -> dict[str, Any]:
    health = payload.setdefault("dataHealth", {})
    sources = health.setdefault("sources", {})
    usda = sources.setdefault("USDA", {})

    success = usda.get("success") is True
    usda["current"] = success
    usda["qualityStatus"] = "current" if success else "unavailable"
    usda["coverageComplete"] = success
    usda["coverageMethod"] = "primary-api"

    # A failed retrieval may retain last-known records, but retained records must
    # never turn a failed source check into a current coverage claim.
    if not success:
        usda["current"] = False
        usda["coverageComplete"] = False

    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recalls", default=str(DEFAULT_RECALLS))
    args = parser.parse_args()
    path = Path(args.recalls)
    payload = json.loads(path.read_text(encoding="utf-8"))
    finalize(payload)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
