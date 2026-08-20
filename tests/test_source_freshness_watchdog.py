import datetime as dt
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_source_freshness", ROOT / "scripts" / "check_source_freshness.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

NOW = dt.datetime(2026, 8, 19, 23, 30, tzinfo=dt.timezone.utc)


def payload(checked_at="2026-08-19T20:00:00Z"):
    return {
        "checkedAt": checked_at,
        "sources": {
            "FDA": {"success": True, "qualityStatus": "current", "checkedAt": checked_at},
            "USDA": {"success": True, "qualityStatus": "current", "checkedAt": checked_at},
        },
    }


def test_fresh_snapshot_passes():
    assert MODULE.evaluate(payload(), now=NOW, max_age_hours=8) == []


def test_old_snapshot_fails_even_if_sources_still_claim_current():
    failures = MODULE.evaluate(payload("2026-08-18T02:09:55Z"), now=NOW, max_age_hours=8)
    assert any("source-status snapshot" in item and "hours old" in item for item in failures)
    assert any("FDA source check" in item for item in failures)
    assert any("USDA source check" in item for item in failures)


def test_failed_source_fails_watchdog():
    data = payload()
    data["sources"]["FDA"]["success"] = False
    failures = MODULE.evaluate(data, now=NOW, max_age_hours=8)
    assert "FDA latest retrieval is not successful" in failures


def test_missing_quality_state_fails_watchdog():
    data = payload()
    del data["sources"]["USDA"]["qualityStatus"]
    failures = MODULE.evaluate(data, now=NOW, max_age_hours=8)
    assert "USDA has no qualityStatus" in failures


def test_watchdog_repairs_directly_instead_of_dispatching_another_workflow():
    workflow = (ROOT / ".github" / "workflows" / "data-freshness-watchdog.yml").read_text(encoding="utf-8")
    assert "python3 scripts/refresh_recalls_current_v4.py" in workflow
    assert "python3 scripts/write_source_status.py" in workflow
    assert "python3 scripts/check_source_freshness.py --max-age-hours 1" in workflow
    assert 'git commit -m "chore: refresh recall data"' in workflow
    assert "git push origin HEAD:main" in workflow
    assert "gh workflow run refresh-recalls.yml" not in workflow
    assert "contents: write" in workflow


def test_watchdog_validates_against_current_v4_contracts():
    workflow = (ROOT / ".github" / "workflows" / "data-freshness-watchdog.yml").read_text(encoding="utf-8")
    assert "python3 tests/test_fda_source_union.py" in workflow
    assert "python3 tests/test_fda_live_augmentation.py" in workflow
    assert "python3 tests/test_known_recall_fixtures.py" in workflow
    assert "python3 tests/test_source_quality.py" not in workflow


def test_v4_source_status_restores_explicit_usda_quality_state():
    writer = (ROOT / "scripts" / "write_source_status.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "data-freshness-watchdog.yml").read_text(encoding="utf-8")
    assert 'if agency == "USDA"' in writer
    assert 'normalized.setdefault("qualityStatus", "current" if success else "unavailable")' in writer
    assert 'normalized.setdefault("current", success)' in writer
    assert 'normalized.setdefault("coverageMethod", "primary-api")' in writer
    assert '"scripts/write_source_status.py"' in workflow
    assert '"scripts/refresh_recalls_current_v4.py"' in workflow
