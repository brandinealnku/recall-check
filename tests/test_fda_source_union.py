import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("refresh_v4", SCRIPTS / "refresh_recalls_current_v4.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def rec(rid, surface, date, firm="Sun Noodle", product="Sura Tanmen noodles", state="active"):
    prefix = {"annualAnnouncements":"FDA-ANN-", "publicAlerts":"FDA-PUBLIC-", "enforcement":"FDA-"}[surface]
    return {
        "id": prefix + rid,
        "sourceRecordId": rid,
        "agency": "FDA",
        "recallDate": date,
        "timeline": {"recallDate": date},
        "recallingFirm": firm,
        "productDescription": product,
        "title": product,
        "officialUrl": "https://www.fda.gov/safety/recalls/example" if surface == "publicAlerts" else "https://www.accessdata.fda.gov/scripts/ires/index.cfm#/search/",
        "lifecycle": {"state": state, "isActionable": state == "active"},
        "status": "current" if state == "active" else state,
        "upcs": [], "gtins": [], "brandNames": [], "productNames": [product],
        "packageSizes": [], "lotCodes": [], "dateCodes": [], "establishmentNumbers": [],
        "sourceRecord": {"source": "FDA public recalls table"} if surface == "publicAlerts" else {},
    }


class FdaSourceUnionTests(unittest.TestCase):
    def test_cross_surface_records_are_deduplicated_and_provenance_is_preserved(self):
        rows = [
            rec("ann", "annualAnnouncements", "2026-08-06"),
            rec("public", "publicAlerts", "2026-08-06"),
            rec("F-100", "enforcement", "2026-08-05"),
        ]
        result = mod.dedupe_fda(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result[0]["sourceSurfaces"]), {"annualAnnouncements", "publicAlerts", "enforcement"})
        self.assertTrue(result[0]["officialUrl"].startswith("https://www.fda.gov/"))

    def test_all_three_official_surfaces_are_required_for_current_coverage(self):
        base = {
            "generatedAt": "2026-08-17T22:00:00Z",
            "dataHealth": {"checkedAt":"2026-08-17T22:00:00Z", "warnings": [], "sources": {
                "FDA": {"success": True, "recordCount": 1},
                "USDA": {"success": True, "current": True, "qualityStatus":"current", "recordCount":1, "checkedAt":"2026-08-17T22:00:00Z"},
            }},
            "recalls": [rec("ann", "annualAnnouncements", "2026-08-06"), {"id":"USDA-1","agency":"USDA","recallDate":"2026-08-08","timeline":{"recallDate":"2026-08-08"}}],
        }
        with patch.object(mod.v2, "_original_build_dataset", return_value=base), \
             patch.object(mod, "fetch_public", return_value=[rec("public", "publicAlerts", "2026-08-06")]), \
             patch.object(mod, "fetch_enforcement", return_value=[rec("F-100", "enforcement", "2026-08-05")]):
            result = mod.build_dataset({}, now="2026-08-17T22:00:00Z")
        fda = result["dataHealth"]["sources"]["FDA"]
        self.assertTrue(fda["current"])
        self.assertTrue(fda["coverageComplete"])
        self.assertEqual(fda["qualityStatus"], "current")
        self.assertEqual(set(fda["surfaces"]), set(mod.FDA_SURFACES))
        self.assertNotIn("authoritativeNewestRecallDate", fda)
        self.assertNotIn("freshnessLagDays", fda)

    def test_one_failed_surface_degrades_coverage_without_claiming_current(self):
        base = {
            "generatedAt": "2026-08-17T22:00:00Z",
            "dataHealth": {"checkedAt":"2026-08-17T22:00:00Z", "warnings": [], "sources": {
                "FDA": {"success": True, "recordCount": 1},
                "USDA": {"success": True, "current": True, "qualityStatus":"current", "recordCount":1, "checkedAt":"2026-08-17T22:00:00Z"},
            }},
            "recalls": [rec("ann", "annualAnnouncements", "2026-08-06"), {"id":"USDA-1","agency":"USDA","recallDate":"2026-08-08","timeline":{"recallDate":"2026-08-08"}}],
        }
        with patch.object(mod.v2, "_original_build_dataset", return_value=base), \
             patch.object(mod, "fetch_public", side_effect=RuntimeError("public table unavailable")), \
             patch.object(mod, "fetch_enforcement", return_value=[rec("F-100", "enforcement", "2026-08-05")]):
            result = mod.build_dataset({}, now="2026-08-17T22:00:00Z")
        fda = result["dataHealth"]["sources"]["FDA"]
        self.assertFalse(fda["current"])
        self.assertFalse(fda["coverageComplete"])
        self.assertEqual(fda["qualityStatus"], "degraded")
        self.assertFalse(fda["surfaces"]["publicAlerts"]["success"])
        self.assertTrue(any("FDA coverage is degraded" in w for w in result["dataHealth"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
