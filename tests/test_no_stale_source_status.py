import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_snapshot_is_canonical_when_present():
    snapshot = json.loads((ROOT / "data" / "source-status.json").read_text(encoding="utf-8"))
    for agency in ("FDA", "USDA"):
        source = snapshot["sources"][agency]
        # Existing checked-in data may predate this patch until the post-merge refresh,
        # but whenever the compatibility field is present it must reflect canonical state.
        if "freshnessValidated" in source:
            expected = bool(
                source.get("success") is True
                and source.get("current") is True
                and source.get("qualityStatus") == "current"
                and source.get("coverageComplete") is True
            )
            assert source["freshnessValidated"] is expected
