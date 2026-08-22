from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_trust_consumer_and_status_writer_share_freshness_contract():
    trust = (ROOT / "trust-v4-1.js").read_text(encoding="utf-8")
    writer = (ROOT / "scripts" / "write_source_status.py").read_text(encoding="utf-8")
    assert "source.freshnessValidated===true" in trust
    assert 'compact["freshnessValidated"]' in writer
