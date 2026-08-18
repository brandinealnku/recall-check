"""Static regression checks for the RecallCheck V3 safety and responsive design contract."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.js").read_text()
CSS = (ROOT / "recallcheck-v3.css").read_text()
RESPONSIVE = (ROOT / "recallcheck-v3-responsive.css").read_text()
INDEX = (ROOT / "index.html").read_text()
DISCOVERY = (ROOT / "discovery.js").read_text()
V3 = (ROOT / "recallcheck-v3.js").read_text()
PAGES = [
    (ROOT / "recalls.html").read_text(),
    (ROOT / "recall.html").read_text(),
    (ROOT / "how-recalls-work.html").read_text(),
    (ROOT / "privacy.html").read_text(),
    (ROOT / "methodology.html").read_text(),
]

class SafetyStateDesignTests(unittest.TestCase):
    def test_current_recall_and_verification_are_two_layers(self):
        self.assertIn('current_recall_details_required:{label:"CURRENT RECALL"', APP)
        self.assertIn('tone:"critical"', APP)
        self.assertIn("package-verification package-verification--warning", APP)
        self.assertIn("This barcode is linked to a current recall", APP)

    def test_package_choices_preserve_uncertainty(self):
        for copy in ("My package matches", "My package does not match", "I cannot find the code"):
            self.assertIn(copy, APP)
        self.assertIn("This does not guarantee the product is safe", APP)
        self.assertNotRegex(APP, re.compile(r"safe to eat", re.I))

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

    def test_accessibility_media_and_focus_rules(self):
        self.assertIn("prefers-reduced-motion:reduce", CSS)
        self.assertIn("forced-colors:active", CSS)
        self.assertIn("scroll-margin-top", CSS)
        self.assertIn("min-width:44px", CSS)
        self.assertIn("prefers-reduced-motion: reduce", RESPONSIVE)

    def test_version_and_ownership(self):
        self.assertIn("Version 3.1.0-beta", INDEX)
        self.assertIn("RecallCheck", INDEX)
        self.assertIn("ITSBAD LLC", INDEX)
        self.assertIn("not endorsed by FDA, USDA", INDEX)

class ConsolidationTests(unittest.TestCase):
    def test_home_uses_v3_design_system_and_responsive_layer(self):
        self.assertIn('recallcheck-v3.css?v=3.0.0-beta', INDEX)
        self.assertIn('recallcheck-v3-responsive.css?v=3.1.0-beta', INDEX)
        for legacy in ("styles.css", "brand.css", "mobile-polish.css", "v2-1.css", "consumer-ux.css", "v2-3.css", "v2-4.css"):
            self.assertNotIn(f'href="{legacy}', INDEX)

    def test_all_primary_pages_use_v3_responsive_system(self):
        for page in PAGES:
            self.assertIn('recallcheck-v3.css?v=3.0.0-beta', page)
            self.assertIn('recallcheck-v3-responsive.css?v=3.1.0-beta', page)
            self.assertIn("Version 3.1.0-beta", page)

    def test_primary_pages_share_header_navigation(self):
        for page in [INDEX, *PAGES]:
            self.assertIn('aria-label="RecallCheck by ITSBAD Labs home"', page)
            self.assertIn('aria-expanded="false" aria-controls="site-nav"', page)

    def test_responsive_matrix_covers_phone_tablet_desktop(self):
        for width in (959, 767, 479, 359):
            self.assertIn(f"max-width: {width}px", RESPONSIVE)
        self.assertIn("min-width: 768px", RESPONSIVE)
        self.assertIn("min-width: 1100px", RESPONSIVE)
        self.assertIn("overflow-x: clip", RESPONSIVE)
        self.assertIn("grid-template-columns: 1fr", RESPONSIVE)

    def test_current_recall_context_explains_source_and_quality(self):
        self.assertIn("Newest displayed current record", V3)
        self.assertIn("Source coverage note", V3)
        self.assertIn("authoritativeNewestRecallDate", V3)
        self.assertIn("data-current-list-summary", (ROOT / "recalls.html").read_text())
        self.assertIn("data-recent-summary", INDEX)

    def test_v3_avoids_template_dependencies_and_effects(self):
        combined = (CSS + RESPONSIVE + INDEX).lower()
        for forbidden in ("backdrop-filter", "font-awesome", "bootstrap.min", "tailwind", "sparkle", "decorative-blob"):
            self.assertNotIn(forbidden, combined)

class ContentContractTests(unittest.TestCase):
    def test_privacy_discloses_local_recent_checks(self):
        privacy = (ROOT / "privacy.html").read_text()
        self.assertIn("local storage", privacy)
        self.assertIn("up to six recent checks", privacy)
        self.assertNotIn("Session history exists only in JavaScript memory", privacy)

    def test_methodology_preserves_no_match_limit(self):
        methodology = (ROOT / "methodology.html").read_text()
        self.assertIn("A no-match result is not a safety guarantee", methodology)
        self.assertIn("up to six recent checks", methodology)

    def test_how_it_works_has_scan_compare_verify(self):
        how = (ROOT / "how-recalls-work.html").read_text()
        for label in ("Scan", "Compare", "Verify"):
            self.assertIn(label, how)
        for state in ("Recall found", "Check your package", "No current recall match found", "Older recall found"):
            self.assertIn(state, how)

    def test_navigation_accessibility_hooks(self):
        self.assertIn('close(true)', DISCOVERY)
        self.assertIn('event.target.closest("a")', DISCOVERY)

if __name__ == "__main__":
    unittest.main()
