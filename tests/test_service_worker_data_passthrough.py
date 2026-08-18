from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_service_worker_does_not_intercept_safety_data():
    sw = read("service-worker.js")
    assert 'url.pathname.includes("/data/")' in sw
    assert 'fetch(request, { cache: "no-store" })' not in sw
    block = sw.split('url.pathname.includes("/data/")', 1)[1].split("}", 1)[0]
    assert "return;" in block
    assert "respondWith" not in block

def test_source_status_fetch_bypasses_http_cache():
    trust = read("trust-v4-1.js")
    assert 'fetch(STATUS_URL, { cache: "no-store" })' in trust

if __name__ == "__main__":
    test_service_worker_does_not_intercept_safety_data()
    test_source_status_fetch_bypasses_http_cache()
    print("Service-worker data passthrough checks passed")
