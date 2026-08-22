from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_consumer_freshness_contract_is_satisfied_by_source_status_writer():
    trust = (ROOT / "trust-v4-1.js").read_text(encoding="utf-8")
    writer = (ROOT / "scripts" / "write_source_status.py").read_text(encoding="utf-8")

    # trust-v4-1 still consumes this compatibility signal. If that consumer contract
    # changes, this test can be removed together with the compatibility projection.
    assert "freshnessValidated" in trust
    assert 'compact["freshnessValidated"]' in writer
    assert 'normalized.get("success") is True' in writer
    assert 'normalized.get("current") is True' in writer
    assert 'normalized.get("qualityStatus") == "current"' in writer
    assert 'normalized.get("coverageComplete") is True' in writer


def test_recall_json_is_configured_not_to_be_edge_cached():
    headers = (ROOT / "_headers").read_text(encoding="utf-8")
    assert "/data/*.json" in headers
    assert "Cache-Control: no-store" in headers
    assert "CDN-Cache-Control: no-store" in headers
