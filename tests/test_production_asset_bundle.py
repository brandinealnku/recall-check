"""Regression contract for deploy-safe RecallCheck production assets."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_production_assets.py"
WRANGLER = (ROOT / "wrangler.jsonc").read_text()

spec = importlib.util.spec_from_file_location("production_assets", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProductionAssetBundleTests(unittest.TestCase):
    def test_wrangler_builds_generated_bundle(self):
        self.assertIn('"command": "python3 scripts/build_production_assets.py"', WRANGLER)
        self.assertIn('"directory": ".deploy"', WRANGLER)

    def test_bundle_preserves_all_records_and_stays_below_guardrail(self):
        source = json.loads((ROOT / "data" / "recalls.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "deploy"
            module.build(out)
            manifest = json.loads((out / "data" / "recalls-manifest.json").read_text())
            self.assertEqual(manifest["recordCount"], len(source["recalls"]))
            self.assertEqual(sum(c["records"] for c in manifest["chunks"]), len(source["recalls"]))
            self.assertFalse((out / "data" / "recalls.json").exists())
            self.assertTrue((out / "recall-data-loader.js").exists())
            self.assertTrue(all(c["bytes"] <= module.MAX_CHUNK_BYTES for c in manifest["chunks"]))
            self.assertTrue(all(p.stat().st_size < module.WARN_ASSET_BYTES for p in out.rglob("*") if p.is_file()))
            for page in out.rglob("*.html"):
                self.assertIn(module.LOADER_TAG, page.read_text())

    def test_loader_keeps_existing_recalls_url_contract(self):
        text = SCRIPT.read_text()
        self.assertIn('data\\/recalls\\.json', text)
        self.assertIn('data/recalls-manifest.json', text)
        self.assertIn('window.fetch=async function', text)
        self.assertIn('return {...m.dataset,recalls}', text)


if __name__ == "__main__":
    unittest.main()
