"""Regression contract for RecallCheck's production deployment path."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/deploy-production.yml").read_text()


class ProductionDeployContractTests(unittest.TestCase):
    def test_deploys_only_after_successful_main_ci(self):
        self.assertIn("workflow_run:", WORKFLOW)
        self.assertIn("Test RecallCheck site", WORKFLOW)
        self.assertIn("workflow_run.conclusion == 'success'", WORKFLOW)
        self.assertIn("workflow_run.head_branch == 'main'", WORKFLOW)
        self.assertIn("ref: ${{ github.event.workflow_run.head_sha }}", WORKFLOW)

    def test_cloudflare_deploy_is_explicit(self):
        self.assertIn("CLOUDFLARE_API_TOKEN", WORKFLOW)
        self.assertIn("CLOUDFLARE_ACCOUNT_ID", WORKFLOW)
        self.assertIn("wrangler@4 deploy", WORKFLOW)

    def test_production_is_commit_verifiable(self):
        self.assertIn("deployment.json", WORKFLOW)
        self.assertIn("recallcheck.itsbadlabs.com/deployment.json", WORKFLOW)
        self.assertIn("EXPECTED_SHA", WORKFLOW)
        self.assertIn("Production verification failed", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
