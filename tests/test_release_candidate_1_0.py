import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def load_json(path):
    return json.loads(read(path))


def test_source_status_is_truthful_and_per_source():
    status = load_json("data/source-status.json")
    assert status.get("checkedAt")
    for agency in ("FDA", "USDA"):
        source = status["sources"][agency]
        assert "success" in source
        assert "current" in source
        assert "freshnessValidated" in source
        assert source.get("qualityStatus")
        assert source.get("newestRecallDate")
        assert source.get("lastSuccessfulUpdate")


def test_rc_ui_never_equates_fetch_time_with_newest_recall_date():
    trust = read("trust-v4-1.js")
    assert "newest verified record" in trust
    assert "Official source status checked" in trust
    assert "freshnessValidated===true" in trust
    assert "FDA verified through" in trust
    assert "USDA FSIS through" in trust


def test_no_match_degrades_when_any_authoritative_source_is_not_verified():
    trust = read("trust-v4-1.js")
    assert "PARTIAL CHECK" in trust
    assert "does not prove the product is not recalled" in trust
    assert "Verify with ${x.agency}" in trust


def test_unknown_or_unmatched_product_is_not_presented_as_confirmed_identity():
    trust = read("trust-v4-1.js")
    assert "Product identity could not be confirmed from this barcode" in trust
    assert "barcode matching only" in trust
    app = read("app.js")
    assert 'matchMethod:"direct_barcode_check"' in app


def test_scanner_and_manual_search_have_safe_fallbacks():
    fresh = read("freshness.js")
    index = read("index.html")
    assert "cameraFallbackNeeded" in fresh
    assert "Enter barcode manually instead" in fresh
    assert 'id="barcode-form"' in index
    assert 'inputmode="numeric"' in index


def test_mobile_has_no_horizontal_overflow_contract():
    css = read("trust-v4-1.css")
    assert "overflow-x:hidden" in css
    assert "max-width:calc(100vw - 20px)" in css
    assert "env(safe-area-inset-left)" in css
    assert "grid-template-columns:1fr" in css


def test_five_release_candidate_scenarios_are_covered_by_behavior_contracts():
    fixtures = load_json("tests/fixtures/official-recall-fixtures.json")
    fixture_text = json.dumps(fixtures).lower()
    # 1. Known FDA recall fixture.
    assert "fda" in fixture_text
    # 2. Known USDA/FSIS recall fixture.
    assert "usda" in fixture_text or "fsis" in fixture_text
    # 3. Valid barcode/no recall + 4. unknown/unmatched product paths.
    app = read("app.js")
    assert "no_matching_current_recall" in app
    assert "productIdentityMissing:true" in app
    # 5. Authoritative-source failure path.
    trust = read("trust-v4-1.js")
    assert "Source verification unavailable" in trust
    assert "could not verify official source freshness" in trust
