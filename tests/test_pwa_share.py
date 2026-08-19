from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_manifest_is_standalone():
    manifest = read("manifest.webmanifest")
    assert '"display": "standalone"' in manifest
    assert '"start_url": "./"' in manifest

def test_service_worker_never_caches_recall_data():
    sw = read("service-worker.js")
    assert "CACHE_NAME" in sw
    assert 'url.origin !== self.location.origin' in sw
    assert 'url.pathname.includes("/data/")' in sw
    block = sw.split('url.pathname.includes("/data/")', 1)[1].split("}", 1)[0]
    assert "return;" in block
    assert "respondWith" not in block
    assert 'request.mode === "navigate"' in sw

def test_install_and_share_are_contextual():
    js = read("pwa-share.js")
    assert "beforeinstallprompt" in js
    assert "navigator.share" in js
    assert "navigator.clipboard.writeText" in js
    assert "Keep RecallCheck handy" in js
    assert "completedChecks()" in js
    assert "checks < 2" in js
    assert "Share this recall" in js
    assert "Share RecallCheck" in js
    assert 'document.querySelector(".hero-assurance")' not in js

def test_ios_instructions_are_minimal():
    js = read("pwa-share.js")
    assert "Tap <strong>Share</strong> in Safari." in js
    assert "Tap <strong>Add to Home Screen</strong>." in js
    assert "Open Share menu" not in js
    assert "Apple requires" not in js

def test_pwa_assets_are_loaded_directly_not_by_scanner_loader():
    index = read("index.html")
    loader = read("scanner-privacy-loader.js")
    assert "pwa-share.css?v=1.0.1" in index
    assert "pwa-share.js?v=1.0.1" in index
    assert "pwa-share.css" not in loader
    assert "pwa-share.js" not in loader
    assert "ZXING_URL" in loader

def test_legacy_install_card_is_suppressed():
    css = read("pwa-share.css")
    assert "#install-prompt{display:none!important}" in css

if __name__ == "__main__":
    test_manifest_is_standalone()
    test_service_worker_never_caches_recall_data()
    test_install_and_share_are_contextual()
    test_ios_instructions_are_minimal()
    test_pwa_assets_are_loaded_directly_not_by_scanner_loader()
    test_legacy_install_card_is_suppressed()
    print("Contextual PWA/share regression checks passed")
