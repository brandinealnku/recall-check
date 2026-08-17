"""Static regression checks for the RecallCheck V2.1 safety-state contract."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.js").read_text()
CSS = (ROOT / "styles.css").read_text()
INDEX = (ROOT / "index.html").read_text()
REVIEW = (ROOT / "design-review.js").read_text()
DESIGN_SYSTEM = (ROOT / "design-system.html").read_text()


class SafetyStateDesignTests(unittest.TestCase):
    def test_current_recall_and_verification_are_two_layers(self):
        self.assertIn('current_recall_details_required:{label:"CURRENT RECALL"', APP)
        self.assertIn('tone:"critical"', APP)
        self.assertIn("package-verification package-verification--warning", APP)
        self.assertIn("This barcode is linked to a current recall", APP)

    def test_package_choices_and_outcomes_preserve_uncertainty(self):
        for copy in ("My package matches", "My package does not match", "I cannot find the code"):
            self.assertIn(copy, APP)
        self.assertIn("This does not guarantee the product is safe", APP)
        self.assertIn("Do not assume the product is unaffected", APP)

    def test_semantic_result_tones_are_distinct(self):
        for tone in ("danger", "warning", "historical", "info"):
            self.assertIn(f"--{tone}", CSS)
        for result_class in ("critical", "warning", "neutral-result", "historical", "failure"):
            self.assertIn(f".result--{result_class}", CSS)
        self.assertNotIn("result--success", CSS)

    def test_no_match_is_not_a_safety_approval(self):
        self.assertIn("We didn\'t find this barcode in the FDA or USDA recall data checked.", APP)
        self.assertIn("not a food-safety guarantee", INDEX)
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
        self.assertRegex(CSS, r"prefers-reduced-motion:\s*reduce")
        self.assertRegex(CSS, r"forced-colors:\s*active")
        self.assertIn("scroll-margin-top", CSS)
        self.assertRegex(CSS, r"@media\s*\(max-width:\s*640px\)")

    def test_version_and_ownership(self):
        self.assertIn("Version 2.1.1-beta", INDEX)
        self.assertIn("RecallCheck", INDEX)
        self.assertIn("ITSBAD LLC", INDEX)
        self.assertIn("not endorsed by FDA, USDA", INDEX)

    def test_restrained_service_tokens_and_review_fixture(self):
        for token in ("--ink", "--muted", "--brand", "--line", "--neutral", "--danger", "--warning", "--historical", "--info", "--focus", "--task", "--reading", "--wide"):
            self.assertIn(token, CSS)
        for component in ("Actions and form controls", "Product confirmation", "Safety result states", "Scanner shell"):
            self.assertIn(component, DESIGN_SYSTEM)

    def test_design_avoids_template_dependencies_and_effects(self):
        combined = (CSS + INDEX + DESIGN_SYSTEM).lower()
        for forbidden in ("backdrop-filter", "font-awesome", "bootstrap.min", "tailwind", "sparkle", "decorative-blob"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()

class ResponsiveHeaderTests(unittest.TestCase):
    def test_header_keeps_primary_task_navigation_concise(self):
        primary = re.search(r'<ul class="primary-nav">(.*?)<li class="more-item">', INDEX, re.S).group(1)
        self.assertEqual(2, len(re.findall(r'<a ', primary)))
        for label in ("Current recalls", "How it works"):
            self.assertIn(f">{label}</a>", primary)
        secondary = re.search(r'<ul class="secondary-nav">(.*?)</ul>', INDEX, re.S).group(1)
        for label in ("Privacy", "Methodology"):
            self.assertIn(f">{label}</a>", secondary)

    def test_navigation_switches_before_links_wrap(self):
        self.assertRegex(CSS, r"@media\s*\(max-width:\s*960px\)")
        self.assertRegex(CSS, r'(?s)@media\s*\(max-width:\s*960px\).*?\.menu-button\s*\{\s*display:\s*block')
        self.assertRegex(CSS, r'\.site-header nav\[data-open="true"\]\s*\{\s*display:\s*block')
        self.assertRegex(CSS, r"white-space:\s*nowrap")

    def test_navigation_accessibility_hooks(self):
        self.assertIn('aria-expanded="false" aria-controls="site-nav"', INDEX)
        self.assertIn('aria-label="RecallCheck by ITSBAD Labs home"', INDEX)
        self.assertIn('close(true)', (ROOT / "discovery.js").read_text())
        self.assertIn('event.target.closest("a")', (ROOT / "discovery.js").read_text())

    def test_header_is_single_fixed_height_row_and_320_safe(self):
        self.assertRegex(CSS, r"\.site-header\s*\{[^}]*min-height:\s*4\.5rem")
        self.assertRegex(CSS, r"(?s)@media\s*\(max-width:\s*960px\).*?\.site-header nav\s*\{[^}]*position:\s*absolute")
        self.assertNotIn("Beta: how results work</span>", INDEX)
