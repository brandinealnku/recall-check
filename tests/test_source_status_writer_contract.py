from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_writer_projects_freshness_for_legacy_consumer():
    text = (ROOT / "scripts" / "write_source_status.py").read_text(encoding="utf-8")
    assert 'compact["freshnessValidated"]' in text
    assert 'normalized.get("success") is True' in text
    assert 'normalized.get("current") is True' in text
    assert 'normalized.get("qualityStatus") == "current"' in text
    assert 'normalized.get("coverageComplete") is True' in text
