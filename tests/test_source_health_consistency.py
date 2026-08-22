import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "finalize_source_health", ROOT / "scripts" / "finalize_source_health.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def payload(success=True):
    return {
        "dataHealth": {
            "sources": {
                "FDA": {
                    "success": True,
                    "current": True,
                    "qualityStatus": "current",
                    "coverageComplete": True,
                    "coverageMethod": "official-fda-multi-surface-union-v1",
                },
                "USDA": {
                    "success": success,
                    "recordCount": 100,
                    "checkedAt": "2026-08-22T03:03:44Z",
                },
            }
        }
    }


def test_successful_usda_retrieval_is_canonical_current_state():
    result = MODULE.finalize(payload(True))
    usda = result["dataHealth"]["sources"]["USDA"]
    assert usda["current"] is True
    assert usda["qualityStatus"] == "current"
    assert usda["coverageComplete"] is True
    assert usda["coverageMethod"] == "primary-api"


def test_failed_usda_retrieval_cannot_claim_current_from_retained_records():
    result = MODULE.finalize(payload(False))
    usda = result["dataHealth"]["sources"]["USDA"]
    assert usda["recordCount"] == 100
    assert usda["current"] is False
    assert usda["qualityStatus"] == "unavailable"
    assert usda["coverageComplete"] is False
    assert usda["coverageMethod"] == "primary-api"
