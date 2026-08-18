from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_manifest_is_standalone():
    manifest = read("manifest.webmanifest")
    assert '"display": "standalone"' in manifest
    assert '"start_url": "./"' in manifest

def test_service_worker_exists_and_is_same_origin_only():
    sw = read("service-worker.js")
    assert "CACHE_NAME" in sw
    assert 'url.origin !== self.location.origin' in sw
    assert 'request.mode === "navigate"' in sw

def test_install_and_share_actions_exist():
    js = read("pwa-share.js")
    assert "beforeinstallprompt" in js
    assert "navigator.share" in js
    assert "navigator.clipboard.writeText" in js
    assert "Add to Home Screen" in js
    assert "Install RecallCheck" in js
    assert "Share RecallCheck" in js

def test_mobile_utilities_bootstrap_same_origin():
    loader = read("scanner-privacy-loader.js")
    assert 'link.href = "pwa-share.css"' in loader
    assert 'script.src = "pwa-share.js"' in loader

if __name__ == "__main__":
    test_manifest_is_standalone()
    test_service_worker_exists_and_is_same_origin_only()
    test_install_and_share_actions_exist()
    test_mobile_utilities_bootstrap_same_origin()
    print("PWA/share regression checks passed")
