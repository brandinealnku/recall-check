"""Static regression checks for RecallCheck safety, trust, and responsive UX."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.js").read_text()
CSS = (ROOT / "recallcheck-v3.css").read_text()
RESPONSIVE = (ROOT / "recallcheck-v3-responsive.css").read_text()
TRUST_CSS = (ROOT / "trust-v4-1.css").read_text()
TRUST_JS = (ROOT / "trust-v4-1.js").read_text()
INDEX = (ROOT / "index.html").read_text()
DISCOVERY = (ROOT / "discovery.js").read_text()
V3 = (ROOT / "recallcheck-v3.js").read_text()
FRESHNESS = (ROOT / "freshness.js").read_text()
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
        self.assertIn("Match the package, not only the barcode", TRUST_JS)

    def test_no_match_is_not_a_safety_approval(self):
        self.assertIn("We didn\'t find this barcode in the FDA or USDA recall data checked.", APP)
        self.assertIn("cannot guarantee that a product is safe", INDEX)
        self.assertIn("No match found, but official coverage is incomplete", TRUST_JS)
        self.assertIn("UNABLE TO FULLY VERIFY", TRUST_JS)

    def test_accessibility_media_and_focus_rules(self):
        self.assertIn("prefers-reduced-motion:reduce", CSS)
        self.assertIn("forced-colors:active", CSS)
        self.assertIn("scroll-margin-top", CSS)
        self.assertIn("min-width:44px", CSS)
        self.assertIn("prefers-reduced-motion: reduce", RESPONSIVE)
        self.assertIn("forced-colors:active", TRUST_CSS)

    def test_version_and_ownership(self):
        self.assertIn('meta name="version" content="1.0"', INDEX)
        self.assertNotIn("Version 4.1.2-beta", INDEX)
        self.assertIn("ITSBAD LLC", INDEX)
        self.assertIn("not endorsed by FDA, USDA", INDEX)

class ResultSimplificationTests(unittest.TestCase):
    def test_one_consumer_facing_about_check_disclosure(self):
        self.assertIn('el("details", null, "about-check")', TRUST_JS)
        self.assertIn('el("summary", "About this check")', TRUST_JS)
        self.assertIn("Recall records last refreshed", TRUST_JS)
        self.assertIn("Product information", TRUST_JS)
        self.assertIn("Sources checked", TRUST_JS)

    def test_old_overlapping_trust_sections_are_removed(self):
        self.assertIn('result.querySelector(".trust-summary")?.remove()', TRUST_JS)
        self.assertIn('result.querySelector(".transparency")?.remove()', TRUST_JS)
        self.assertIn('result.querySelector(".result-provenance")?.remove()', TRUST_JS)
        self.assertIn('result.querySelector(".trust-verification-card")?.remove()', TRUST_JS)
        self.assertNotIn("Which official sources were checked?", TRUST_JS)
        self.assertNotIn("Sources checked for this result", TRUST_JS)

    def test_no_match_hides_irrelevant_fields(self):
        self.assertIn("if (!noMatch)", TRUST_JS)
        self.assertIn("Official recall status", TRUST_JS)
        self.assertIn("Package verification", TRUST_JS)
        self.assertNotIn('addFact(facts, "Barcode match"', TRUST_JS)

    def test_technical_provenance_is_progressively_disclosed(self):
        self.assertIn('el("summary", "Technical details")', TRUST_JS)
        self.assertIn("surfaceEntries(state)", TRUST_JS)
        self.assertIn("Recall matching", TRUST_JS)
        self.assertIn("Open ${state.agency} official recalls", TRUST_JS)

    def test_mobile_result_inset_is_explicit(self):
        self.assertIn(".about-check{margin:1rem", TRUST_CSS)
        self.assertIn(".about-check{margin:1rem .9rem}", TRUST_CSS)
        self.assertIn(".about-check-body{padding:0 .9rem .9rem}", TRUST_CSS)
        self.assertIn("grid-template-columns:1fr", TRUST_CSS)

    def test_runtime_source_health_uses_coverage_state(self):
        self.assertIn("coverageStatus || source.qualityStatus", TRUST_JS)
        self.assertIn("source.current === true", TRUST_JS)
        self.assertIn("Official source coverage needs attention", TRUST_JS)
        self.assertIn("Official sources current", TRUST_JS)

    def test_v412_assets_are_cache_busted(self):
        self.assertIn('trust-v4-1.css?v=4.1.2-beta', INDEX)
        self.assertIn('trust-v4-1.js?v=4.1.2-beta', INDEX)

class ConsolidationTests(unittest.TestCase):
    def test_home_uses_v3_design_system_and_responsive_layer(self):
        self.assertIn('recallcheck-v3.css?v=3.0.0-beta', INDEX)
        self.assertIn('recallcheck-v3-responsive.css?v=3.3.0-beta', INDEX)
        self.assertIn('freshness.js?v=3.3.1-coverage', INDEX)
        for legacy in ("styles.css", "brand.css", "mobile-polish.css", "v2-1.css", "consumer-ux.css", "v2-3.css", "v2-4.css"):
            self.assertNotIn(f'href="{legacy}', INDEX)

    def test_primary_pages_share_header_navigation(self):
        for page in [INDEX, *PAGES]:
            self.assertIn('aria-label="RecallCheck by ITSBAD Labs home"', page)
            self.assertIn('aria-expanded="false" aria-controls="site-nav"', page)

    def test_responsive_matrix_covers_phone_tablet_desktop(self):
        for width in (959, 767, 479, 359):
            self.assertIn(f"max-width: {width}px", RESPONSIVE)
        self.assertIn("min-width: 768px", RESPONSIVE)
        self.assertIn("min-width: 1100px", RESPONSIVE)
        self.assertIn("overflow-x:hidden", RESPONSIVE)

    def test_mobile_width_is_pinned_to_visual_viewport(self):
        self.assertIn("width:100vw; min-width:100vw; max-width:100vw", RESPONSIVE)
        self.assertIn("width:100dvw; min-width:100dvw; max-width:100dvw", RESPONSIVE)
        self.assertNotIn("width: calc(100% + var(--gutter))", RESPONSIVE)

    def test_current_recall_context_explains_source_and_quality(self):
        self.assertIn("Newest displayed current record", V3)
        self.assertIn("Source coverage note", V3)
        self.assertIn("official-fda-multi-surface-union-v1", FRESHNESS)
        self.assertNotIn("official listing newest", FRESHNESS)

    def test_v3_avoids_template_dependencies_and_effects(self):
        combined = (CSS + RESPONSIVE + INDEX).lower()
        for forbidden in ("backdrop-filter", "font-awesome", "bootstrap.min", "tailwind", "sparkle", "decorative-blob"):
            self.assertNotIn(forbidden, combined)

class ContentContractTests(unittest.TestCase):
    def test_privacy_discloses_local_recent_checks(self):
        privacy = (ROOT / "privacy.html").read_text()
        self.assertIn("local storage", privacy)
        self.assertIn("up to six recent checks", privacy)

    def test_methodology_preserves_no_match_limit(self):
        methodology = (ROOT / "methodology.html").read_text()
        self.assertIn("A no-match result is not a safety guarantee", methodology)
        self.assertIn("up to six recent checks", methodology)

    def test_navigation_accessibility_hooks(self):
        self.assertIn('close(true)', DISCOVERY)
        self.assertIn('event.target.closest("a")', DISCOVERY)

if __name__ == "__main__":
    unittest.main()
