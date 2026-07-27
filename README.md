# RecallCheck 0.2

**Scan it. Check it. Protect your household.** RecallCheck is a mobile-first GitHub Pages prototype that identifies packaged food through Open Food Facts and deterministically compares it with cached official FDA and USDA recall records. It is an experimental testing tool—not a production safety or medical system.

## Scope and architecture

Version 0.2 provides opt-in ZXing camera scanning, manual GTIN entry, live official checks, an isolated fictional Demo Mode, data-health reporting, matching explanations, lot/date confirmation, a browser test page, and PWA fundamentals. It deliberately does **not** add accounts, alerts, OCR, uploads, or pantry management.

There is no runtime server, build step, database, analytics, cookie, or browser API key. Relative first-party URLs support both `USERNAME.github.io/REPOSITORY/` and custom domains.

```text
.
├── .github/workflows/refresh-recalls.yml
├── assets/icons/{README.md,recallcheck.svg}
├── data/{recalls.json,demo-recalls.json,demo-products.json}
├── scripts/refresh_recalls.py
├── tests/fixtures/official-recall-fixtures.json
├── tests/test_refresh_recalls.py
├── app.js
├── index.html
├── manifest.webmanifest
├── styles.css
├── sw.js
├── tests.html
└── tests.js
```

### Live Check versus Demo Mode

* **Live Check** reads only `data/recalls.json`. That file is reserved for records retrieved from official openFDA and FSIS endpoints. When neither official source has usable data, Live Check reports data unavailability and never reports a no-match conclusion.
* **Demo Mode** reads fictional products from `data/demo-products.json` and fictional recalls from `data/demo-recalls.json`. Demo records are visibly labeled and never passed to the official matching path.
* `tests/fixtures/` contains reduced historical official-record shapes for automated normalization tests. Fixtures are never loaded by the application or refresh output.

## Official data ingestion

### FDA

`scripts/refresh_recalls.py` calls the [openFDA Food Enforcement API](https://open.fda.gov/apis/food/enforcement/), retrieves active/recent records from the previous two years, follows `limit`/`skip` pagination, and caps a run defensively. It preserves every original field in `sourceRecord`. Conservative labeled-narrative extraction collects UPC/GTIN candidates, lot/date codes, package sizes, and product-name fragments. Each normalized record includes extraction method, confidence, and field counts. Narrative extraction is only a candidate-generation aid; it is not proof of package identity.

### USDA FSIS

The isolated USDA loader calls the documented FSIS Recall API v1 at `https://www.fsis.usda.gov/fsis/api/recall/v/1`, accepts documented list responses and common JSON wrappers, follows body or HTTP `Link` pagination, and normalizes recalls and public-health alerts. It preserves the complete source object, source record number, establishment numbers, and official `fsis.usda.gov` URL. A USDA failure cannot discard successful FDA data, and no demo record is retained as official data.

### Failure and data-health behavior

FDA and USDA are fetched independently. A failed source retains only its last-known official records; if both fail and there is a valid existing dataset, the script refuses an empty replacement. Output is written to a temporary file, parsed again, and atomically replaced. `dataHealth` records:

* workflow version and generated timestamp;
* last successful update;
* per-source retrieval time, success/failure, retained count, and safe error type;
* counts by agency and records with identifier candidates;
* warnings, including partial-source coverage.

The expandable **Official data status** panel shows source counts, age, warnings, stale status after eight days, and one-agency coverage. The committed repository snapshot intentionally has zero official records and says that the first refresh is required; it does not present demo data as live data.

## Matching methodology and safety rules

1. Normalize spaces/hyphens without deleting meaningful middle digits and accept GTIN lengths 8, 12, 13, and 14.
2. Validate GS1 check digits while permitting an explicit user override.
3. Generate zero-padded equivalent UPC-A/GTIN-13/GTIN-14 representations.
4. Rank exact identifiers, equivalent identifiers, then brand/name/package-size similarity.
5. Exact/equivalent identifiers may establish a product-level match. If any lot/date restrictions exist, the result remains `possible_match_details_required` until a printed package value matches.
6. Similarity alone **never** produces `confirmed_match`; it produces manual review.
7. Product-service failure still performs a direct official identifier search. Recall-data failure never produces `no_matching_recall`.

Every possible/confirmed result has **Why am I seeing this?**, including match method, matched fields, exact/equivalent barcode status, similarity use, unresolved lot/date details, reason, and source record identifier.

## Product information, privacy, and security

Open Food Facts API v2 is community maintained and is never treated as a recall authority. Requests select only needed fields, use a timeout, and handle missing, malformed, limited, or unavailable responses separately from recall-data health.

Camera access starts only after a scan action. ZXing processes frames locally; images are not uploaded or saved. Tracks stop after detection, close, Escape, stop, manual fallback, fatal error, page hiding, or navigation. Barcodes remain only in memory. There are no accounts, tracking, ads, cookies, or local storage. External content is rendered through DOM APIs and `textContent`; external links use `noopener noreferrer`. The CSP allows the pinned scanner CDN, local assets, and Open Food Facts only where required.

## PWA behavior

`manifest.webmanifest` uses relative `start_url`/`scope` and a local maskable SVG icon. The service worker precaches the static shell and Demo Mode JSON for offline use. Official `data/recalls.json` is deliberately network-handled rather than indefinitely cached, and cross-origin Open Food Facts responses are never cached. Installability still depends on browser criteria and HTTPS; GitHub Pages supplies HTTPS.

## Local development and automated tests

Do not use a `file://` URL. Fetch and camera APIs require an HTTP origin, and camera access generally requires HTTPS or localhost.

```bash
cd /path/to/recall-check
python3 -m http.server 8000
```

Open `http://localhost:8000/`; open `http://localhost:8000/tests.html` for the Node-free browser suite.

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m json.tool data/recalls.json >/dev/null
python3 -m json.tool data/demo-recalls.json >/dev/null
python3 -m json.tool data/demo-products.json >/dev/null
python3 -m json.tool tests/fixtures/official-recall-fixtures.json >/dev/null
python3 -m py_compile scripts/refresh_recalls.py
node --check app.js && node --check tests.js && node --check sw.js
```

Remove the leading `+` characters if copying commands from a rendered diff; in the repository file they are shown to distinguish command lines visually.

## Version 0.2 manual test plan

1. Confirm Live Check shows official source health and, on this unrefreshed snapshot, refuses a no-match conclusion.
2. Run every Demo Mode card offline after one online load; confirm all results say fictional Demo Mode.
3. For the lot demo, enter `L2407A`, an incorrect code, and **I cannot find it**.
4. Inspect **Why am I seeing this?** for exact, equivalent, fuzzy, and lot-restricted fixture scenarios.
5. Enter valid, invalid-length, and invalid-check-digit barcodes and test Enter/override behavior.
6. Grant and deny camera permission; exit through detection, Stop, close, Escape, manual fallback, tab hiding, and navigation; confirm the camera indicator stops.
7. Temporarily make Open Food Facts unavailable and confirm direct official identifier matching still runs.
8. Temporarily make one source fail during a fixture refresh; confirm the other source remains usable and the status panel warns about partial coverage.
9. Test at 320 CSS pixels, keyboard-only, reduced motion, and with a screen reader.
10. Install the PWA where supported, go offline, and confirm the shell and demos work while Live Check does not claim fresh official data.

## GitHub Pages deployment

1. Push files to the `main` branch.
2. Open **Settings → Pages**.
3. Under **Build and deployment**, select **Deploy from a branch**.
4. Choose **main** and **/ (root)**, then **Save**.
5. Wait for deployment and open `https://USERNAME.github.io/REPOSITORY/` or the custom domain.
6. Replace the footer repository placeholder before public use.

## Optional openFDA key and refresh workflow

Pages requires no key. To raise Actions API limits, open **Settings → Secrets and variables → Actions → New repository secret**, name it exactly `OPENFDA_API_KEY`, add the value, and save. The key exists only in the workflow environment; it is never logged, generated into JSON, or delivered to browsers.

Run manually through **Actions → Refresh recall data → Run workflow**. It also runs weekly. Troubleshooting:

* Read source status warnings in the failed run; exception types do not include secret request URLs.
* Confirm official endpoints and Actions outbound networking are available.
* A malformed/empty response intentionally fails or retains prior official records.
* Validate locally with a disposable `--output` path only if network access is intended.
* Never copy demo records into `data/recalls.json` to make a refresh appear successful.

## Known data-quality limitations

Recall narratives may omit, group, punctuate, or ambiguously label UPC/GTIN, lot, date, brand, and size information. Regex extraction is conservative but cannot understand attachments or label images. Some FSIS records may evolve fields over time. Open Food Facts may be incomplete. The committed live cache has no successful refresh because the execution environment could not reach official endpoints; run the workflow before evaluating real record coverage. A barcode match is not a safety determination, and many recalls publish no barcode.

## Future production hardening

Consider managed backend ingestion, database normalization, more frequent refreshes, reliable attachment extraction, OCR, GS1 data, retailer receipt integrations, pantry monitoring/alerts, observability, data-quality review, legal/safety/privacy review, automated cross-browser testing, and human review of uncertain matches. These remain out of scope.

## Disclaimer, attribution, and license

> RecallCheck is an experimental prototype and does not replace official FDA, USDA, manufacturer, retailer, or healthcare guidance. Recall information can change, and some recalls may not include a barcode.

RecallCheck is not endorsed by FDA, USDA, Open Food Facts, or any company. Code is MIT licensed; source data remains subject to its source terms.
