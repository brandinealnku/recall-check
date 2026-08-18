RecallCheck live-data fetch regression note

The service worker must not intercept safety-critical files under /data/. Recall/source JSON is fetched directly by the page, with source-status explicitly using cache: no-store. This avoids Safari service-worker cache-mode failures and prevents stale Cache Storage content from being treated as current recall information.
