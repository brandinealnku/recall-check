import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("refresh_v3", SCRIPTS / "refresh_recalls_current_v3.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


HTML = '''<table><thead><tr><th>Date</th><th>Brand Name(s)</th><th>Product Description</th><th>Product Type</th><th>Recall Reason Description</th><th>Company Name</th><th>Terminated Recall</th><th>Excerpt</th></tr></thead><tbody>
<tr><td>08/17/2026</td><td>Drug Brand</td><td>Drug product</td><td>Drugs</td><td>Label issue</td><td>Drug Co</td><td></td><td></td></tr>
<tr><td>08/06/2026</td><td>Sun Noodle</td><td><a href="/safety/recalls/example">Sura Tanmen noodles</a></td><td>Food & Beverages, Allergens</td><td>Contain undeclared Fish</td><td>Sun Noodle of Honolulu</td><td></td><td></td></tr>
<tr><td>08/04/2026</td><td>Blank Slate Creamery</td><td>Vegan frozen dessert sandwiches</td><td>Food & Beverages, Allergens</td><td>Undeclared egg allergen</td><td>Blank Slate Creamery</td><td></td><td></td></tr>
</tbody></table>'''


class FdaLiveAugmentationTests(unittest.TestCase):
    def test_only_food_rows_are_used(self):
        rows = mod.parse_public_food_rows(HTML)
        self.assertEqual([r["date"] for r in rows], ["2026-08-06", "2026-08-04"])
        self.assertEqual(rows[0]["brand"], "Sun Noodle")
        self.assertTrue(rows[0]["url"].startswith("https://www.fda.gov/"))

    def test_live_rows_advance_dataset_freshness(self):
        dataset = {
            "generatedAt": "2026-08-17T21:00:00Z",
            "dataHealth": {"checkedAt": "2026-08-17T21:00:00Z", "warnings": ["FDA data may be incomplete: old"] , "sources": {"FDA": {"success": True, "newestRecallDate": "2026-07-13"}}},
            "recalls": [{"id":"old","agency":"FDA","recallDate":"2026-07-13","recallingFirm":"Old","productDescription":"Old product","timeline":{"recallDate":"2026-07-13"}}],
        }
        def fetcher(url, headers):
            return HTML, {}
        result = mod.augment_fda(dataset, fetcher)
        fda = result["dataHealth"]["sources"]["FDA"]
        self.assertEqual(fda["newestRecallDate"], "2026-08-06")
        self.assertEqual(fda["authoritativeNewestRecallDate"], "2026-08-06")
        self.assertTrue(fda["current"])
        self.assertEqual(fda["qualityStatus"], "current")
        self.assertGreaterEqual(fda["livePublicRowsAdded"], 2)


if __name__ == "__main__":
    unittest.main()
