"""Regression checks for RecallCheck V4.1.1 snack lookup and iPhone sizing."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text()
LOOKUP = (ROOT / "product-lookup-v4-1-1.js").read_text()
CSS = (ROOT / "v4-1-1-mobile.css").read_text()


class ProductLookupResilienceTests(unittest.TestCase):
    def test_v411_assets_are_loaded_and_cache_busted(self):
        self.assertIn('content="4.1.1-beta"', INDEX)
        self.assertIn('v4-1-1-mobile.css?v=4.1.1-beta', INDEX)
        self.assertIn('product-lookup-v4-1-1.js?v=4.1.1-beta', INDEX)
        self.assertIn('Version 4.1.1-beta', INDEX)

    def test_legacy_duplicate_result_indicator_is_not_loaded(self):
        self.assertNotIn('result-indicators.js', INDEX)

    def test_product_lookup_removes_mobile_preflight_header(self):
        self.assertIn('headers.delete("X-Requested-With")', LOOKUP)
        self.assertIn('headers.delete("x-requested-with")', LOOKUP)

    def test_product_identity_survives_directory_miss(self):
        self.assertIn('recallcheck.productIdentity.v1', LOOKUP)
        self.assertIn('recallcheck.recentChecks.v2', LOOKUP)
        self.assertIn('cachedProduct(requestedCode) || recentProduct(requestedCode)', LOOKUP)
        self.assertIn('previously identified on this device', LOOKUP)
        self.assertIn('cached Open Food Facts result', LOOKUP)

    def test_gtin_equivalents_are_preserved(self):
        self.assertIn('if (code.length === 12) set.add(`0${code}`)', LOOKUP)
        self.assertIn('if (code.length === 14 && code.startsWith("00")) set.add(code.slice(2))', LOOKUP)


class MobileResultSizingTests(unittest.TestCase):
    def test_result_svg_has_explicit_mobile_dimensions(self):
        self.assertIn('.result-banner>.icon', CSS)
        self.assertIn('width:2.1rem !important', CSS)
        self.assertIn('height:2.1rem !important', CSS)
        self.assertIn('grid-template-columns:2.25rem minmax(0,1fr)', CSS)

    def test_recent_checks_use_card_spacing(self):
        self.assertIn('.recent-checks-list-v21{display:grid;gap:.75rem}', CSS)
        self.assertIn('.recent-check-v21{', CSS)
        self.assertIn('border-radius:16px', CSS)
        self.assertIn('.recent-check-v21 .button{width:100%', CSS)

    def test_cached_legacy_indicator_is_defensively_hidden(self):
        self.assertIn('.result-status-indicator{display:none!important}', CSS)


if __name__ == "__main__":
    unittest.main()
