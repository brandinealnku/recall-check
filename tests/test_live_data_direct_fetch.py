from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_service_worker_bypasses_data_requests():
    sw = read("service-worker.js")
    marker = 'if (url.pathname.includes("/data/") || /(?:recalls|source-status)\\.json$/i.test(url.pathname)) {'
    assert marker in sw
    block = sw.split(marker, 1)[1].split("}", 1)[0]
    assert "return;" in block
    assert "respondWith" not in block

if __name__ == "__main__":
    test_service_worker_bypasses_data_requests()
    print("Direct live-data fetch regression check passed")
