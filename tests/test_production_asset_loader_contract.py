"""Static contract for the transparent chunked recall-data loader."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = (ROOT / "scripts" / "build_production_assets.py").read_text()


class ProductionAssetLoaderContractTests(unittest.TestCase):
    def test_existing_recalls_url_is_intercepted_transparently(self):
        self.assertIn('data\\/recalls\\.json', BUILDER)
        self.assertIn('data/recalls-manifest.json', BUILDER)
        self.assertIn('window.fetch = async function', BUILDER)
        self.assertIn('return { ...manifest.dataset, recalls }', BUILDER)

    def test_source_monolith_is_excluded_and_chunks_are_bounded(self):
        self.assertIn('MAX_CHUNK_BYTES = 8 * 1024 * 1024', BUILDER)
        self.assertIn('WARN_ASSET_BYTES = 18 * 1024 * 1024', BUILDER)
        self.assertIn('Monolithic data/recalls.json must never be included', BUILDER)


if __name__ == "__main__":
    unittest.main()
