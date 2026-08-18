import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import refresh_recalls_current_v2 as quality


PUBLIC_ROWS = """
<table>
<thead><tr><th>Date</th><th>Brand Name(s)</th><th>Product Description</th><th>Product Type</th><th>Recall Reason Description</th></tr></thead>
<tbody>
<tr><td>08/17/2026</td><td>DeviceBrand</td><td>Diagnostic kit</td><td>Medical Devices</td><td>Label issue mentioning allergens</td></tr>
<tr><td>08/06/2026</td><td>Sun Noodle</td><td>Noodles</td><td>Food &amp; Beverages, Allergens</td><td>Undeclared fish</td></tr>
<tr><td>08/05/2026</td><td>DrugBrand</td><td>Medicine</td><td>Drugs</td><td>Foodborne illness study reference</td></tr>
<tr><td>08/01/2026</td><td>Ukrops</td><td>Baked foods</td><td>Food &amp; Beverages</td><td>Foreign material</td></tr>
</tbody></table>
"""


class SourceQualityTests(unittest.TestCase):
    def dataset(self, newest="2026-07-13"):
        return {
            "generatedAt": "2026-08-17T18:55:00Z",
            "dataHealth": {
                "checkedAt": "2026-08-17T18:55:00Z",
                "warnings": [],
                "sources": {
                    "FDA": {
                        "success": True,
                        "checkedAt": "2026-08-17T18:55:00Z",
                        "lastSuccessfulUpdate": "2026-08-17T18:55:00Z",
                        "newestRecallDate": newest,
                        "recordCount": 10,
                    },
                    "USDA": {
                        "success": True,
                        "checkedAt": "2026-08-17T18:55:00Z",
                        "lastSuccessfulUpdate": "2026-08-17T18:55:00Z",
                        "newestRecallDate": "2026-08-08",
                        "recordCount": 5,
                    },
                },
            },
            "recalls": [{"id": "FDA-1", "agency": "FDA"}, {"id": "USDA-1", "agency": "USDA"}],
        }

    def test_public_listing_extracts_newest_food_date_only(self):
        self.assertEqual(quality.newest_fda_public_food_date(PUBLIC_ROWS), "2026-08-06")

    def test_non_food_row_with_newer_date_cannot_become_authority_date(self):
        self.assertNotEqual(quality.newest_fda_public_food_date(PUBLIC_ROWS), "2026-08-17")

    def test_stale_fda_is_flagged_even_when_retrieval_succeeded(self):
        data = quality.apply_source_quality(
            self.dataset("2026-07-13"),
            lambda _url, _headers: (PUBLIC_ROWS, {}),
        )
        fda = data["dataHealth"]["sources"]["FDA"]
        self.assertTrue(fda["success"])
        self.assertFalse(fda["current"])
        self.assertEqual(fda["qualityStatus"], "stale")
        self.assertTrue(fda["freshnessValidated"])
        self.assertEqual(fda["authoritativeNewestRecallDate"], "2026-08-06")
        self.assertEqual(fda["freshnessLagDays"], 24)
        self.assertTrue(data["dataHealth"]["warnings"])

    def test_current_fda_passes_quality_validation(self):
        data = quality.apply_source_quality(
            self.dataset("2026-08-06"),
            lambda _url, _headers: (PUBLIC_ROWS, {}),
        )
        fda = data["dataHealth"]["sources"]["FDA"]
        self.assertTrue(fda["current"])
        self.assertEqual(fda["qualityStatus"], "current")
        self.assertEqual(fda["freshnessLagDays"], 0)

    def test_validation_failure_is_not_reported_as_current(self):
        def fail(_url, _headers):
            raise OSError("validator unavailable")

        data = quality.apply_source_quality(self.dataset(), fail)
        fda = data["dataHealth"]["sources"]["FDA"]
        self.assertTrue(fda["success"])
        self.assertFalse(fda["current"])
        self.assertFalse(fda["freshnessValidated"])
        self.assertEqual(fda["qualityStatus"], "unverified")

    def test_usda_direct_api_success_is_current(self):
        data = quality.apply_source_quality(
            self.dataset("2026-08-06"),
            lambda _url, _headers: (PUBLIC_ROWS, {}),
        )
        usda = data["dataHealth"]["sources"]["USDA"]
        self.assertTrue(usda["current"])
        self.assertEqual(usda["qualityStatus"], "current")
        self.assertEqual(usda["validationMethod"], "primary-api")


if __name__ == "__main__":
    unittest.main()
