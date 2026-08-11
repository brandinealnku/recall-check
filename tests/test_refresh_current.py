import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import refresh_recalls_current as rr

HTML = '<a href="/media/191968/download?attachment=">2026 Recalls (XML)</a>'
XML = '''<Recalls><Recall><Date>07/30/2026</Date><Brand_Name_s>GreenWise</Brand_Name_s><Product_Description>Organic Frozen Blueberries, 10 oz, UPC 012345678905</Product_Description><Product_Type>Food &amp; Beverages</Product_Type><Recall_Reason_Description>Possible E. coli contamination</Recall_Reason_Description><Company_Name>Publix</Company_Name><URL>https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/example</URL><Terminated_Recall>No</Terminated_Recall></Recall><Recall><Date>07/30/2026</Date><Brand_Name_s>DrugBrand</Brand_Name_s><Product_Description>Drug</Product_Description><Product_Type>Drugs</Product_Type><Company_Name>DrugCo</Company_Name></Recall></Recalls>'''
USDA = {
    "recall_number": "023-2026",
    "recall_date": "08/01/2026",
    "title": "USDA fixture",
    "product_items": "10-lb case; GTIN 00012345678905; EST. 51205",
    "summary": "fixture",
    "url": "https://www.fsis.usda.gov/recalls-alerts/example",
}


class CurrentFeedTests(unittest.TestCase):
    def fetch_fda_fixture(self, url, _headers):
        return (HTML, {}) if "recalls-data-sets" in url else (XML, {})

    def test_discovery_and_food_filter(self):
        records = rr.fetch_fda(self.fetch_fda_fixture, 2026)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["recallDate"], "2026-07-30")
        self.assertEqual(records[0]["upcs"], ["012345678905"])
        self.assertTrue(records[0]["lifecycle"]["isActionable"])

    def test_both_agencies_are_kept(self):
        result = rr.build_dataset(
            {"generatedAt": "old", "dataHealth": {}, "recalls": []},
            self.fetch_fda_fixture,
            lambda _u, _h: ([USDA], {}),
            "2026-08-11T12:00:00Z",
        )
        self.assertEqual(result["dataHealth"]["recordCountByAgency"], {"FDA": 1, "USDA": 1})
        self.assertTrue(result["dataHealth"]["sources"]["FDA"]["success"])
        self.assertTrue(result["dataHealth"]["sources"]["USDA"]["success"])
        self.assertEqual(result["sources"][0]["name"], "FDA Firm-Issued Recalls XML")

    def test_usda_failure_does_not_erase_fda(self):
        result = rr.build_dataset(
            {"generatedAt": "old", "dataHealth": {}, "recalls": []},
            self.fetch_fda_fixture,
            lambda _u, _h: (_ for _ in ()).throw(OSError("down")),
            "2026-08-11T12:00:00Z",
        )
        self.assertEqual(result["dataHealth"]["recordCountByAgency"], {"FDA": 1, "USDA": 0})
        self.assertFalse(result["dataHealth"]["sources"]["USDA"]["success"])


if __name__ == "__main__":
    unittest.main()
