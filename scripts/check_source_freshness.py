#!/usr/bin/env python3
"""Fail when RecallCheck's published source snapshot is too old.

Used by CI/watchdog automation so a missed refresh cannot silently leave stale
FDA/USDA status marked as current.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS = ROOT / "data" / "source-status.json"


def parse_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def evaluate(payload: dict, *, now: dt.datetime, max_age_hours: float) -> list[str]:
    failures: list[str] = []
    sources = payload.get("sources") or {}
    snapshot_checked = parse_time(payload.get("checkedAt") or payload.get("generatedAt"))
    if snapshot_checked is None:
        failures.append("source-status snapshot has no valid checkedAt/generatedAt")
    elif now - snapshot_checked > dt.timedelta(hours=max_age_hours):
        age = (now - snapshot_checked).total_seconds() / 3600
        failures.append(f"source-status snapshot is {age:.1f} hours old")

    for agency in ("FDA", "USDA"):
        source = sources.get(agency) or {}
        checked = parse_time(source.get("checkedAt") or source.get("lastSuccessfulUpdate"))
        if checked is None:
            failures.append(f"{agency} has no valid checkedAt/lastSuccessfulUpdate")
            continue
        age = (now - checked).total_seconds() / 3600
        if age > max_age_hours:
            failures.append(f"{agency} source check is {age:.1f} hours old")
        if source.get("success") is not True:
            failures.append(f"{agency} latest retrieval is not successful")
        if not source.get("qualityStatus"):
            failures.append(f"{agency} has no qualityStatus")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", default=str(DEFAULT_STATUS))
    parser.add_argument("--max-age-hours", type=float, default=8.0)
    args = parser.parse_args()

    payload = json.loads(Path(args.status).read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)
    failures = evaluate(payload, now=now, max_age_hours=args.max_age_hours)
    if failures:
        print("STALE")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("FRESH")
    print(f"checkedAt={payload.get('checkedAt') or payload.get('generatedAt')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
