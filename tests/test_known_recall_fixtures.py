"""Known-recall fixtures that catch silent source regressions before deployment."""
from datetime import date
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data" / "recalls.json").read_text())
RECALLS = DATA.get("recalls", [])


def recall_date(record):
    value = (record.get("timeline") or {}).get("recallDate") or record.get("recallDate") or record.get("date")
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


class KnownRecallCoverageTests(unittest.TestCase):
    def test_fda_contains_august_17_2026_or_newer_record(self):
        cutoff = date(2026, 8, 17)
        matches = [r for r in RECALLS if r.get("agency") == "FDA" and recall_date(r) and recall_date(r) >= cutoff]
        self.assertTrue(matches, "FDA coverage regressed: expected at least one Aug. 17, 2026 or newer FDA record")

    def test_usda_contains_august_8_2026_or_newer_record(self):
        cutoff = date(2026, 8, 8)
        matches = [r for r in RECALLS if r.get("agency") in {"USDA", "USDA FSIS"} and recall_date(r) and recall_date(r) >= cutoff]
        self.assertTrue(matches, "USDA coverage regressed: expected at least one Aug. 8, 2026 or newer USDA FSIS record")

    def test_recent_records_retain_official_provenance(self):
        recent = [r for r in RECALLS if recall_date(r) and recall_date(r) >= date(2026, 8, 8)]
        self.assertTrue(recent, "No recent recall fixtures are available")
        for record in recent[:20]:
            self.assertTrue(record.get("officialUrl") or record.get("sourceUrl"), f"Recent recall {record.get('id')} is missing official provenance")


if __name__ == "__main__":
    unittest.main()
