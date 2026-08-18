from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text()
LOADER = (ROOT / "scanner-privacy-loader.js").read_text()

assert 'src="https://cdn.jsdelivr.net/npm/@zxing/browser@0.1.5/umd/zxing-browser.min.js"' not in INDEX
assert 'scanner-privacy-loader.js' in INDEX
assert 'document.createElement("script")' in LOADER
assert 'scanner_library_blocked' in LOADER
assert 'BrowserMultiFormatReader' in LOADER
print("Safari private browsing compatibility checks passed")
