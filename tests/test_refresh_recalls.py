import json
import io
import pathlib
import sys
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest import mock

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
        self.assertEqual(item["lifecycle"]["state"], "active")
        self.assertTrue(item["lifecycle"]["isActionable"])
        self.assertEqual(item["timeline"]["recallDate"], "2024-07-15")

    def test_lifecycle_normalization_is_conservative(self):
        expectations = {
            "Ongoing": ("active", True), "Completed": ("closed", False),
            "Terminated": ("terminated", False), "unexpected": ("unknown", False),
            None: ("unknown", False),
        }
        for source, expected in expectations.items():
            with self.subTest(source=source):
                lifecycle = rr.normalize_lifecycle(source, "20250712")
                self.assertEqual((lifecycle["state"], lifecycle["isActionable"]), expected)
                self.assertEqual(lifecycle["terminationDate"], "2025-07-12")

    def test_timeline_age_does_not_change_active_lifecycle(self):
        timeline = rr.normalize_timeline("20240101", rr.dt.date(2026, 7, 27))
        self.assertFalse(timeline["isRecent"])
        self.assertGreater(timeline["ageDaysAtRefresh"], rr.RECENT_RECALL_DAYS)
        self.assertEqual(rr.normalize_lifecycle("active")["state"], "active")

    def test_recall_without_barcode(self):
        self.assertFalse(rr.normalize_fda(FIXTURES["fda"][1])["upcs"])

    def test_usda_normalization_and_public_health_alert(self):
        recall = rr.normalize_usda(FIXTURES["usda"][0])
        alert = rr.normalize_usda(FIXTURES["usda"][1])
        self.assertEqual(recall["gtins"], ["00012345678905"])
        self.assertEqual(recall["officialUrl"], FIXTURES["usda"][0]["url"])
        self.assertEqual(alert["type"], "public-health-alert")
        self.assertEqual(alert["upcs"], ["737628064502"])
        self.assertEqual(recall["lifecycle"]["state"], "unknown")
        self.assertFalse(recall["lifecycle"]["isActionable"])

    def test_usda_closed_date_without_status_is_closed(self):
        record = {**FIXTURES["usda"][0], "closed_date": "07/12/2025"}
        item = rr.normalize_usda(record)
        self.assertEqual(item["lifecycle"]["state"], "closed")
        self.assertEqual(item["lifecycle"]["sourceStatus"], "07/12/2025")
        self.assertEqual(item["lifecycle"]["terminationDate"], "2025-07-12")

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

    def test_fda_success_without_key_uses_bounded_documented_range(self):
        calls = []
        def fetch(url, _headers):
            calls.append(url)
            return {"meta":{"results":{"total":1}}, "results":[FIXTURES["fda"][0]]}, {}
        with mock.patch.object(rr.dt, "date", wraps=rr.dt.date) as date:
            date.today.return_value = rr.dt.date(2026, 7, 27)
            self.assertEqual(len(rr.fetch_fda(fetch)), 1)
        self.assertEqual(calls[0], "https://api.fda.gov/food/enforcement.json?search=recall_initiation_date%3A%5B20240727+TO+20260727%5D&limit=1000&skip=0")
        self.assertNotIn("api_key", calls[0])
        self.assertNotIn("99991231", calls[0])

    def test_fda_success_with_encoded_key(self):
        calls = []
        key = "synthetic key+/never-log"
        def fetch(url, _headers):
            calls.append(url)
            return {"results":[FIXTURES["fda"][0]]}, {}
        self.assertEqual(len(rr.fetch_fda(fetch, key)), 1)
        self.assertIn("api_key=synthetic+key%2B%2Fnever-log", calls[0])
        self.assertNotIn(key, calls[0])

    def test_fda_http_errors_are_structured(self):
        for status, reason in ((400, "Bad Request"), (403, "Forbidden"), (429, "Too Many Requests")):
            with self.subTest(status=status):
                body = io.BytesIO(json.dumps({"error":{"message":"invalid search syntax"}}).encode())
                error = urllib.error.HTTPError("secret-url", status, reason, {}, body)
                with self.assertRaises(rr.FdaRequestError) as raised:
                    rr.fetch_fda(lambda _u, _h, error=error: (_ for _ in ()).throw(error))
                self.assertEqual(raised.exception.diagnostic["httpStatus"], status)
                self.assertEqual(raised.exception.diagnostic["httpReason"], reason)
                self.assertEqual(raised.exception.diagnostic["message"], "invalid search syntax")

    def test_malformed_upstream(self):
        with self.assertRaises(rr.FdaRequestError): rr.fetch_fda(lambda _u, _h: ({"results":"bad"}, {}))
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

    def test_fda_failure_does_not_discard_usda_success_or_prior_fda(self):
        key = "SYNTHETIC-API-KEY-DO-NOT-EXPOSE"
        def fetch(url, _headers):
            if "api.fda.gov" in url:
                body = io.BytesIO(json.dumps({"error":{"message":f"bad api_key={key} at https://example.test/?api_key={key}"}}).encode())
                raise urllib.error.HTTPError(url, 403, "Forbidden", {"Authorization": key}, body)
            return [FIXTURES["usda"][0]], {}
        prior = rr.normalize_fda(FIXTURES["fda"][1])
        existing = {"generatedAt":"2024-01-01T00:00:00Z", "dataHealth":{}, "recalls":[prior]}
        output = io.StringIO()
        with mock.patch.dict(rr.os.environ, {"OPENFDA_API_KEY": key}), redirect_stdout(output):
            result = rr.build_dataset(existing, fetch, "2026-01-01T00:00:00Z")
        encoded = json.dumps(result)
        diagnostic = result["dataHealth"]["sources"]["FDA"]["error"]
        self.assertEqual(result["dataHealth"]["recordCountByAgency"], {"FDA":1, "USDA":1})
        self.assertEqual(diagnostic["httpStatus"], 403)
        self.assertTrue(diagnostic["apiKeySupplied"])
        self.assertLessEqual(len(diagnostic["message"]), 240)
        self.assertNotIn(key, output.getvalue())
        self.assertNotIn(key, encoded)

    def test_synthetic_key_never_appears_in_exception(self):
        key = "SYNTHETIC-SECRET-123"
        body = io.BytesIO(json.dumps({"error":{"message":f"token=another-secret api_key={key} https://example.test/{key}"}}).encode())
        error = urllib.error.HTTPError(f"https://example.test/?api_key={key}", 400, "Bad Request", {"X-Key":key}, body)
        with self.assertRaises(rr.FdaRequestError) as raised:
            rr.fetch_fda(lambda _u, _h: (_ for _ in ()).throw(error), key)
        rendered = str(raised.exception) + json.dumps(raised.exception.diagnostic)
        self.assertNotIn(key, rendered)
        self.assertNotIn("another-secret", rendered)
        self.assertNotIn("https://", rendered)


if __name__ == "__main__": unittest.main()
