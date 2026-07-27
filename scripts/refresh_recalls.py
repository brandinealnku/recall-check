#!/usr/bin/env python3
"""Refresh normalized FDA records while conservatively retaining USDA and demo records."""
from __future__ import annotations
import datetime as dt
import json
import os
import pathlib
import re
import tempfile
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "recalls.json"
FDA_ENDPOINT = "https://api.fda.gov/food/enforcement.json"

def digits(text: str) -> list[str]:
    return sorted(set(re.findall(r"(?<!\d)\d{8,14}(?!\d)", text or "")))

def normalize_fda(record: dict) -> dict:
    description = record.get("product_description", "")
    codes = " ".join([description, record.get("code_info", "")])
    recall_number = record.get("recall_number", "unknown")
    return {
        "id": f"FDA-{recall_number}", "agency": "FDA", "type": "recall",
        "status": (record.get("status") or "unknown").lower(),
        "classification": record.get("classification") or "unknown",
        "title": f"{record.get('recalling_firm') or 'Food recall'} — {description[:120]}",
        "recallingFirm": record.get("recalling_firm") or "Unknown",
        "productDescription": description, "brandNames": [], "productNames": [],
        "upcs": digits(codes), "gtins": [], "packageSizes": [],
        "lotCodes": [], "dateCodes": [record.get("code_info")] if record.get("code_info") else [],
        "establishmentNumbers": [], "reason": record.get("reason_for_recall") or "Not provided",
        "distribution": record.get("distribution_pattern") or "Not provided",
        "recallDate": parse_date(record.get("recall_initiation_date", "")),
        "officialUrl": "https://www.accessdata.fda.gov/scripts/ires/index.cfm#/search/",
        "sourceRecord": record,
        "searchText": " ".join(str(v) for v in [record.get("recalling_firm", ""), description, codes]).lower()
    }

def parse_date(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}" if re.fullmatch(r"\d{8}", value or "") else ""

def fetch_fda() -> list[dict]:
    start = (dt.date.today() - dt.timedelta(days=730)).strftime("%Y%m%d")
    params = {"search": f"recall_initiation_date:[{start}+TO+99991231]", "limit": "1000"}
    key = os.environ.get("OPENFDA_API_KEY")
    if key: params["api_key"] = key
    request = urllib.request.Request(FDA_ENDPOINT + "?" + urllib.parse.urlencode(params), headers={"User-Agent": "RecallCheck-data-refresh/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    records = payload.get("results")
    if not isinstance(records, list) or not records:
        raise RuntimeError("FDA returned no records; retaining the existing dataset")
    return [normalize_fda(item) for item in records]

def fetch_usda(existing: list[dict]) -> list[dict]:
    """No stable documented FSIS JSON API is assumed; retain audited USDA records."""
    return [item for item in existing if item.get("agency") == "USDA"]

def main() -> None:
    current = json.loads(OUTPUT.read_text(encoding="utf-8"))
    existing = current.get("recalls", [])
    fda = fetch_fda()
    retained = fetch_usda(existing) + [item for item in existing if str(item.get("id", "")).startswith("DEMO-")]
    deduped = {item["id"]: item for item in fda + retained}
    if not fda or not deduped:
        raise RuntimeError("Refusing to replace valid data with an empty dataset")
    output = {"generatedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "datasetLabel": "Cached FDA records with retained USDA/demo records", "sources": current["sources"], "recalls": list(deduped.values())}
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=OUTPUT.parent, delete=False) as handle:
        json.dump(output, handle, indent=2, ensure_ascii=False); handle.write("\n"); temporary = pathlib.Path(handle.name)
    json.loads(temporary.read_text(encoding="utf-8"))
    temporary.replace(OUTPUT)

if __name__ == "__main__": main()
