"""Static regression checks for the Version 0.8 safety-state contract."""
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

    def test_premium_semantic_tokens_and_review_fixture(self):
        for token in ("--surface-page", "--surface-raised", "--surface-inset",
                      "--text-primary", "--text-secondary", "--brand-primary-hover",
                      "--state-critical", "--state-warning", "--state-historical",
                      "--state-information", "--state-failure", "--border-subtle",
                      "--duration-fast", "--content-narrow"):
            self.assertIn(token, CSS)
        for component in ("Actions and form controls", "Product confirmation",
                          "Safety result states", "Scanner shell"):
            self.assertIn(component, DESIGN_SYSTEM)

    def test_design_avoids_template_dependencies_and_effects(self):
        combined = (CSS + INDEX + DESIGN_SYSTEM).lower()
        for forbidden in ("backdrop-filter", "fonts.googleapis.com", "font-awesome",
                          "bootstrap.min", "tailwind", "sparkle", "decorative-blob"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()

class ResponsiveHeaderTests(unittest.TestCase):
    def test_header_uses_three_primary_links_and_secondary_more_menu(self):
        primary = re.search(r'<ul class="primary-nav">(.*?)<li class="more-item">', INDEX, re.S).group(1)
        self.assertEqual(3, len(re.findall(r'<a ', primary)))
        for label in ("Scan", "Current recalls", "How it works"):
            self.assertIn(f">{label}</a>", primary)
        secondary = re.search(r'<ul class="secondary-nav">(.*?)</ul>', INDEX, re.S).group(1)
        for label in ("Privacy", "Methodology", "About ITSBAD LLC", "Beta: How results work"):
            self.assertIn(f">{label}</a>", secondary)

    def test_navigation_switches_before_links_wrap(self):
        self.assertIn("@media(max-width:960px)", CSS)
        self.assertRegex(CSS, r'(?s)@media\(max-width:960px\).*?\.menu-button\{display:block\}')
        self.assertIn('.site-header nav[data-open="true"]{display:block}', CSS)
        self.assertIn("white-space:nowrap", CSS)
        self.assertIn("word-break:normal", CSS)
        self.assertIn("overflow-wrap:normal", CSS)

    def test_navigation_accessibility_hooks(self):
        self.assertIn('aria-expanded="false" aria-controls="site-nav"', INDEX)
        self.assertIn('aria-current="page"', INDEX)
        self.assertIn('close(true)', (ROOT / "discovery.js").read_text())
        self.assertIn('event.target.closest("a")', (ROOT / "discovery.js").read_text())

    def test_header_is_single_fixed_height_row_and_320_safe(self):
        self.assertIn("height:4rem;min-height:4rem;max-height:4rem", CSS)
        self.assertIn("width:100%;max-height:calc(100vh - 4rem);overflow-y:auto", CSS)
        self.assertNotIn("Beta: how results work</span>", INDEX)
