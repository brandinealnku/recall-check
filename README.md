# RecallCheck 0.4

**Is this food recalled?** RecallCheck is a calm, mobile-first consumer tool that identifies packaged food through Open Food Facts and compares it with cached official FDA and USDA recall records. It is an independent beta—not a safety guarantee, production safety system, or medical system.

## Scope and architecture

RecallCheck is created and operated by **ITSBAD LLC**. RecallCheck remains the primary product identity; compact maker text in the header and hero, an About subsection, metadata, and ownership/disclaimer text provide supporting company attribution.

Version 0.4 adds privacy-conscious result feedback. Version 0.3 added a focused scan-first home screen, accessible three-step lookup progress, product confirmation and correction, six explicit consumer result states, package-code guidance, repeat-check actions, clearer coverage reporting, and a secondary fictional Demo Mode. It deliberately does **not** add accounts, alerts, OCR, uploads, or pantry management.

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

`scripts/refresh_recalls.py` calls `https://api.fda.gov/food/enforcement.json` with a bounded two-year search ending on the current date: `search=recall_initiation_date:[YYYYMMDD+TO+YYYYMMDD]&limit=1000&skip=0`. The visible `+TO+` syntax follows openFDA's documented range format; subsequent pages increment `skip`. An optional URL-encoded `api_key` is appended. The former unbounded `99991231` end date is not used. It preserves every original field in `sourceRecord`. Conservative labeled-narrative extraction collects UPC/GTIN candidates, lot/date codes, package sizes, and product-name fragments. Each normalized record includes extraction method, confidence, and field counts. Narrative extraction is only a candidate-generation aid; it is not proof of package identity.

### USDA FSIS

The isolated USDA loader calls the documented FSIS Recall API v1 at `https://www.fsis.usda.gov/fsis/api/recall/v/1`, accepts documented list responses and common JSON wrappers, follows body or HTTP `Link` pagination, and normalizes recalls and public-health alerts. It preserves the complete source object, source record number, establishment numbers, and official `fsis.usda.gov` URL. A USDA failure cannot discard successful FDA data, and no demo record is retained as official data.

### Failure and data-health behavior

FDA and USDA are fetched independently. A failed source retains only its last-known official records; if both fail and there is a valid existing dataset, the script refuses an empty replacement. Output is written to a temporary file, parsed again, and atomically replaced. `dataHealth` records:

* workflow version and generated timestamp;
* last successful update;
* per-source retrieval time, success/failure, retained count, and secret-safe structured diagnostics;
* counts by agency and records with identifier candidates;
* warnings, including partial-source coverage.

The expandable **Recall data coverage** panel gives plain-language agency availability and update time. Nested technical details retain source counts, structured errors, age, warnings, and partial coverage. The committed repository snapshot intentionally has zero official records and says that the first refresh is required; it does not present demo data as live data.

## Matching methodology and safety rules

1. Normalize spaces/hyphens without deleting meaningful middle digits and accept GTIN lengths 8, 12, 13, and 14.
2. Validate GS1 check digits while permitting an explicit user override.
3. Generate zero-padded equivalent UPC-A/GTIN-13/GTIN-14 representations.
4. Rank exact identifiers, equivalent identifiers, then brand/name/package-size similarity.
5. Exact/equivalent identifiers may establish a current product-level match only when lifecycle permits it. Lot/date restrictions produce `current_recall_details_required`; closed or terminated exact records produce `historical_exact_match`.
6. Similarity alone **never** confirms a barcode. Active, strongly corroborated similarity requires manual review; inactive similarity is secondary `historical_similar_record` information.
7. Product-service failure still performs a direct official identifier search. Recall-data failure never produces `no_matching_current_recall`.

Every possible/confirmed result has **Why am I seeing this?**, including match method, matched fields, exact/equivalent barcode status, similarity use, unresolved lot/date details, reason, and source record identifier.

## Product information, privacy, and security

Open Food Facts API v2 is community maintained and is never treated as a recall authority. Requests select only needed fields, use a timeout, and handle missing, malformed, limited, or unavailable responses separately from recall-data health.

Camera access starts only after a scan action. ZXing processes frames locally; images are not uploaded or saved. Tracks stop after detection, close, Escape, stop, manual fallback, fatal error, page hiding, or navigation. Barcodes remain only in memory. There are no accounts, tracking, ads, cookies, or local storage. External content is rendered through DOM APIs and `textContent`; external links use `noopener noreferrer`. The CSP allows the pinned scanner CDN, local assets, and Open Food Facts only where required.

## Result feedback and privacy

Feedback appears only after a completed result, including clearly labeled fictional Demo Mode results. Helpful and Confusing choices expand an accessible follow-up form; reasons are optional, Confusing allows a trimmed 750-character comment, and selection/focus states are conveyed programmatically. A successful endpoint response shows confirmation and **Check another product**, which clears the in-memory feedback state. Feedback is never stored in local or session storage and is not behavioral analytics.

Configure the documented object near the top of `app.js`; never place credentials in browser code:

```js
feedback: {
  mode: "disabled", // "endpoint", "email", or "disabled"
  endpoint: "https://feedback-provider.example/recallcheck",
  email: "CONFIGURE_FEEDBACK_EMAIL",
  timeout: 8000
}
```

The repository defaults to **disabled**, because no verified ITSBAD LLC feedback address or endpoint is available. Disabled mode acknowledges a choice locally and accurately says it was not transmitted. Email mode exposes **Send feedback to ITSBAD LLC** only after the placeholder is replaced with a confirmed address. Endpoint mode requires a valid HTTPS URL, performs one JSON POST with an eight-second timeout, omits credentials/referrer, prevents concurrent/duplicate submission, and never retries automatically. If endpoint delivery fails, users can retry, use a configured email fallback, or continue. Hosting and receiving services may process network information such as an IP address as part of delivery; RecallCheck does not claim anonymity.

Only these fields are constructed: `feedback`, optional allow-listed `reason`, optional trimmed `comment`, `resultState`, coarse current/historical `classification`, `agencyCoverage`, coarse `matchCategory`, `applicationVersion`, browser language, ISO `submissionTimestamp`, and `isDemo`. The payload and email deliberately exclude barcode/GTIN, product or brand name, recall title or record, lot/date/package/establishment codes, camera data/images, location, user agent, API keys, and query secrets. Users are warned not to type personal, medical, or sensitive information. No name, contact, purchase, medical, photo, or location field exists.

A configured endpoint must independently validate the allow-list and types, reject oversized bodies, rate-limit abuse, protect stored feedback, use HTTPS, and allow only expected origins where practical. Client checks are not a security boundary. Review the endpoint provider's network/privacy handling before enabling it. RecallCheck adds no analytics, pixels, fingerprinting, tracking requests, cookies, account, or database; only feedback that a user intentionally sends leaves through the configured transport.

### Feedback manual checks

Exercise current, historical, no-match, product-not-found, partial-coverage, and fictional Demo results with both choices. Verify each structured reason, empty and 750-character comments, endpoint success/timeout/error, confirmed email fallback, disabled mode, duplicate clicks, and **Check another product** reset. Complete the flow by keyboard at 320/375 CSS pixels and 200% zoom. Inspect requests, mailto URLs, console, and both Web Storage APIs to confirm no product identifier or prior response is present and no analytics request occurs. Use synthetic fixture identifiers only.

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

## Version 0.4 manual test plan

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

* Read the concise openFDA Actions diagnostic or source status. FDA failures show only HTTP status/reason, a sanitized message (at most 240 characters), pagination offset, and whether a key was supplied.
* Diagnostics redact the supplied key and key-like fields, remove URLs, and never include the full keyed request URL or secret-bearing headers.
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

## Current and historical matching

RecallCheck evaluates official identifiers before product metadata. Exact UPCs and equivalent
UPC/GTIN representations are ranked by official lifecycle state; active exact matches take
precedence, while closed or terminated identifiers are explicitly historical. Missing or
unrecognized agency statuses remain unknown and require manual review rather than being assumed
active or historical. Recall age is displayed and used as context, but does not override an
official active status.

Similarity discovery is a separate fallback stage. Generic category terms (including “eggs,”
“milk,” and “food”) carry no product-name weight. A candidate must score at least 70, match at
least two fields, and include either an exact normalized brand or distinctive product-name
overlap. Brand contributes 40 points, distinctive name overlap up to 45, and package size 15;
therefore brand or size alone cannot qualify. Similarity never confirms a specific barcode.
Inactive similarity records appear only as secondary historical information beneath the primary
no-current-recall result.

## Version 0.5 package-date checking

RecallCheck keeps the recall determination and package-date determination independent. Ordinary UPC-A, UPC-E, EAN-8, and EAN-13 symbols identify a trade item and are **not** described as containing expiration dates. Where the scanner exposes them, Code 128/GS1-128, Data Matrix/GS1 DataMatrix, QR/GS1 QR, and ZXing-supported DataBar symbols are accepted. The normalized scan retains its value only for the active result.

The local parser supports GS1 AIs `01` (GTIN), `10` (lot), `11` (production), `13` (packaging), `15` (best before), `16` (sell by), `17` (expiration/use by), and `21` (serial), including parenthesized element strings, FNC1/group separators, unparenthesized scanner output, and GS1 Digital Link paths/query attributes. Dates are six-digit `YYMMDD` values. A deterministic consumer-goods window accepts exactly one year from ten years before through thirty years after the user's current year; multiple candidates are ambiguous. Allowed day `00` values are conservatively normalized to month end. Invalid or implausible dates are rejected rather than guessed.

When no encoded date exists, the result offers a privacy-preserving printed-date action, manual date input, or skip. This static build deliberately does not bundle unreliable OCR: the camera/confirmation entry point explains the limitation and falls back to manual entry without capturing or uploading an image. Manual dates are date-only local calendar values and are cleared with the active result. Best-before dates are quality guidance, sell-by dates are inventory guidance, and production/packaging dates are never evaluated as expiration dates. Use-by and expiration results avoid unconditional safety claims. Infant formula is identified only from strong “infant/baby” plus “formula” product/category indicators and receives stronger past-use-by guidance.

No barcode, date, lot, product/recall identifier, image, camera frame, API key, or personal information is persisted. RecallCheck uses no local/session storage, accounts, cookies, analytics, or runtime backend. Feedback remains restricted to non-identifying result context and never contains the actual package date. Fictional Version 0.5 scenarios remain isolated in `data/demo-products.json`; official `data/recalls.json` and ingestion logic are unchanged.
