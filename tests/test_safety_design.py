"""Static regression checks for the Version 0.8 safety-state contract."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.js").read_text()
CSS = (ROOT / "styles.css").read_text()
INDEX = (ROOT / "index.html").read_text()
REVIEW = (ROOT / "design-review.js").read_text()


class SafetyStateDesignTests(unittest.TestCase):
    def test_current_recall_and_verification_are_two_layers(self):
        self.assertIn('current_recall_details_required:{label:"Current recall"', APP)
        self.assertIn('tone:"critical"', APP)
        self.assertIn("package-verification package-verification--warning", APP)
        self.assertIn("This barcode is associated with a current recall", APP)

    def test_package_choices_and_outcomes_preserve_uncertainty(self):
        for copy in ("My package matches", "My package does not match", "I cannot find the code"):
            self.assertIn(copy, APP)
        self.assertIn("This does not guarantee the product is safe", APP)
        self.assertIn("Do not assume the product is unaffected", APP)

    def test_semantic_result_tones_are_distinct(self):
        for tone in ("critical", "warning", "neutral-result", "historical", "failure"):
            self.assertIn(f"--color-{tone}", CSS)
        self.assertNotIn("result--success", CSS)

    def test_no_match_is_not_a_safety_approval(self):
        self.assertIn("This is not a safety guarantee", APP)
        self.assertIn('tone:"neutral-result"', APP)
        self.assertNotRegex(APP, re.compile(r"safe to eat", re.I))

    def test_inline_svg_accessibility(self):
        self.assertIn('createElementNS("http://www.w3.org/2000/svg","svg")', APP)
        self.assertIn('setAttribute("aria-hidden","true")', APP)
        self.assertIn('setAttribute("focusable","false")', APP)

    def test_invalid_barcode_is_inline(self):
        self.assertIn("Check the barcode number", APP)
        self.assertIn('setAttribute("aria-invalid","true")', APP)
        self.assertIn('aria-describedby="barcode-help barcode-error"', INDEX)

    def test_all_sixteen_visual_fixtures_exist(self):
        fixture_ids = re.findall(r'^\s*\["([^"]+)"', REVIEW, re.MULTILINE)
        self.assertEqual(16, len(fixture_ids))
        self.assertEqual(16, len(set(fixture_ids)))

    def test_accessibility_media_and_focus_rules(self):
        self.assertIn("prefers-reduced-motion:reduce", CSS)
        self.assertIn("forced-colors:active", CSS)
        self.assertIn("scroll-margin-top", CSS)
        self.assertIn("@media(max-width:540px)", CSS)

    def test_version_and_ownership(self):
        self.assertIn("Version 0.8", INDEX)
        self.assertIn("RecallCheck", INDEX)
        self.assertIn("ITSBAD LLC", INDEX)
        self.assertIn("not endorsed by the FDA, USDA", INDEX)


if __name__ == "__main__":
    unittest.main()
