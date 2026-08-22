from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_source_status_writer_remains_refresh_trigger():
    workflow = (ROOT / ".github" / "workflows" / "refresh-recalls.yml").read_text(encoding="utf-8")
    watchdog = (ROOT / ".github" / "workflows" / "data-freshness-watchdog.yml").read_text(encoding="utf-8")
    assert '"scripts/write_source_status.py"' in workflow
    assert '"scripts/write_source_status.py"' in watchdog
