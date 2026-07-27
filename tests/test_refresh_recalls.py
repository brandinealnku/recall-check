import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import refresh_recalls as rr

FIXTURES = json.loads((pathlib.Path(__file__).parent / "fixtures" / "official-recall-fixtures.json").read_text())


class NormalizationTests(unittest.TestCase):
    def test_fda_normalization_and_narrative_extraction(self):
        item = rr.normalize_fda(FIXTURES["fda"][0])
        self.assertEqual(item["sourceRecordId"], "F-1417-2024")
        self.assertEqual(item["upcs"], ["012345678905", "036602301972"])
        self.assertIn("L2407A", item["lotCodes"])
        self.assertTrue(item["dateCodes"])
        self.assertEqual(item["extraction"]["method"], "labeled-narrative-regex-v1")
        self.assertEqual(item["sourceRecord"]["recall_number"], "F-1417-2024")

    def test_recall_without_barcode(self):
        self.assertFalse(rr.normalize_fda(FIXTURES["fda"][1])["upcs"])

    def test_usda_normalization_and_public_health_alert(self):
        recall = rr.normalize_usda(FIXTURES["usda"][0])
        alert = rr.normalize_usda(FIXTURES["usda"][1])
        self.assertEqual(recall["gtins"], ["00012345678905"])
        self.assertEqual(recall["officialUrl"], FIXTURES["usda"][0]["url"])
        self.assertEqual(alert["type"], "public-health-alert")
        self.assertEqual(alert["upcs"], ["737628064502"])

    def test_fda_pagination(self):
        old_size, old_max = rr.PAGE_SIZE, rr.MAX_FDA_RECORDS
        rr.PAGE_SIZE, rr.MAX_FDA_RECORDS = 2, 10
        calls = []
        def fetch(url, _headers):
            calls.append(url)
            skip = int(url.split("skip=")[1].split("&")[0])
            page = FIXTURES["fda"] if skip == 0 else [FIXTURES["fda"][0]]
            return {"meta":{"results":{"total":3}}, "results":page}, {}
        try:
            self.assertEqual(len(rr.fetch_fda(fetch)), 3)
            self.assertEqual(len(calls), 2)
        finally:
            rr.PAGE_SIZE, rr.MAX_FDA_RECORDS = old_size, old_max

    def test_malformed_upstream(self):
        with self.assertRaises(ValueError): rr.fetch_fda(lambda _u, _h: ({"results":"bad"}, {}))
        with self.assertRaises(ValueError): rr.fetch_usda(lambda _u, _h: ({"unexpected":[]}, {}))

    def test_one_agency_failure_retains_other_success(self):
        def fetch(url, _headers):
            if "api.fda.gov" in url: return {"meta":{"results":{"total":1}}, "results":[FIXTURES["fda"][0]]}, {}
            raise OSError("USDA unavailable")
        existing = {"generatedAt":"2024-01-01T00:00:00Z", "dataHealth":{}, "recalls":[]}
        result = rr.build_dataset(existing, fetch, "2026-01-01T00:00:00Z")
        self.assertEqual(result["dataHealth"]["recordCountByAgency"], {"FDA":1, "USDA":0})
        self.assertTrue(result["dataHealth"]["sources"]["FDA"]["success"])
        self.assertFalse(result["dataHealth"]["sources"]["USDA"]["success"])


if __name__ == "__main__": unittest.main()
