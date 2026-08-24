# RecallCheck production deployment

Production is deployed by Cloudflare's native Git integration from the `main` branch using `npx wrangler deploy`.

Wrangler runs `python3 scripts/build_production_assets.py` before deployment. That build creates `.deploy/`, excludes the oversized source `data/recalls.json`, preserves every recall record in bounded production chunks, injects the transparent recall-data compatibility loader into HTML pages, and fails if any production asset reaches 18 MiB.

The canonical source dataset remains `data/recalls.json` in the repository for refresh, validation, and QA. It is not uploaded as a single Cloudflare asset.
