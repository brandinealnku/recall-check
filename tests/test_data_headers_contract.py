from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_data_json_is_never_cached_by_cloudflare_pages():
    text = (ROOT / "_headers").read_text(encoding="utf-8")
    assert "/data/*.json" in text
    assert "Cache-Control: no-store" in text
    assert "CDN-Cache-Control: no-store" in text
