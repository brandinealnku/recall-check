# RecallCheck

**Scan it. Check it. Protect your household.** RecallCheck is a mobile-first, static GitHub Pages prototype that identifies packaged food through Open Food Facts and compares it with a local, normalized FDA/USDA recall cache. It is a testing prototype—not a production safety or medical system.

## Prototype scope and architecture

The page offers opt-in camera scanning (pinned ZXing Browser), manual entry, deterministic recall matching, lot/date confirmation, official links, and offline-capable local demonstrations. HTML provides semantic UI, CSS provides a responsive design system, and an IIFE in `app.js` owns in-memory state and exposes pure matching helpers as `window.RecallCheck` for tests. There is no runtime server, build step, database, account, analytics, cookie, or browser API key.

All first-party paths are relative, so deployment works at a repository subpath or custom domain. GitHub Pages serves the static files. Open Food Facts is called directly only for a live lookup; demo products and recall data are local JSON.

```text
.
├── .github/workflows/refresh-recalls.yml
├── assets/icons/README.md
├── data/demo-products.json
├── data/recalls.json
├── scripts/refresh_recalls.py
├── .gitignore
├── LICENSE
├── README.md
├── app.js
├── index.html
├── styles.css
├── tests.html
└── tests.js
```

## Data sources and integrity

* **Product information:** [Open Food Facts](https://world.openfoodfacts.org/) API v2, a community-maintained source. Its records can be absent or incomplete and are never treated as authoritative recall evidence.
* **FDA recalls:** [openFDA Food Enforcement](https://open.fda.gov/apis/food/enforcement/), normalized by the refresh script.
* **USDA notices:** [USDA FSIS recalls and alerts](https://www.fsis.usda.gov/recalls). Because this prototype does not assume an undocumented stable FSIS JSON API, `fetch_usda()` is isolated and retains existing audited USDA records instead of inventing or deleting them.

The committed dataset contains conspicuously labeled, fictional demonstration records—not claims about real companies. Each keeps a `sourceRecord` audit object. The refresh script keeps existing demo and USDA records, requires a non-empty FDA response, validates a temporary JSON file, and atomically replaces the cache only after validation. Always follow linked government notices.

## Matching model

1. Remove spaces/hyphens while retaining all meaningful digits; accept GTIN lengths 8, 12, 13, and 14.
2. Validate the GS1 check digit and let a user deliberately continue after a warning.
3. Generate equivalent zero-padded UPC-A/GTIN-13/GTIN-14 variants.
4. Prefer exact/equivalent identifiers. Otherwise score normalized brand, product-name token overlap, and package size.
5. Classify deterministic results as confirmed, details-required, manual review, no match, unidentified product, separate data/service failures, or invalid barcode.

An exact product barcode does not prove that a particular package is included. If a record lists lots or dates, RecallCheck initially asks for the printed code and only promotes an exact code match to “Recall match found.” Codes commonly appear near a seal, nutrition panel, bottom, or cap. “I cannot find it” directs the user to the official notice rather than making a safety inference.

## Privacy and security

Camera access begins only after the scan button is pressed. ZXing processes video in the browser; frames are not uploaded or saved. Camera tracks stop on detection, close, manual fallback, fatal errors, page hiding, or navigation. Barcodes and recall data remain in memory for the session. There are no trackers, advertisements, accounts, cookies, or local storage. A restrictive CSP permits the pinned jsDelivr script, Open Food Facts requests/images, and local assets. External links use `noopener noreferrer`.

External data is rendered through DOM APIs and `textContent`, never unsanitized `innerHTML`. The optional openFDA key exists only in the Actions environment.

## Run and test locally

Do not open `index.html` through a `file://` URL: fetches and camera APIs will not behave correctly. Camera APIs generally require HTTPS or the trusted `localhost` exception.

```bash
cd /path/to/recall-check
python3 -m http.server 8000
```

Open <http://localhost:8000/>. Run the Node-free test harness at <http://localhost:8000/tests.html>. For machine checks:

```bash
python3 -m json.tool data/recalls.json >/dev/null
python3 -m json.tool data/demo-products.json >/dev/null
python3 -m py_compile scripts/refresh_recalls.py
```

The refresh script performs network writes to `data/recalls.json`; do not run it merely to test syntax.

### Manual QA checklist

1. At 320 px, confirm no horizontal scrolling, visible focus, logical keyboard order, and usable touch targets.
2. Choose each demo; confirm the four required states plus manual review work without an Open Food Facts request.
3. For the lot/date demo, enter `L2407A`, an incorrect code, and choose “I cannot find it.”
4. Enter `012345678905`, press Enter, and confirm a live product failure stays distinct from recall-data failure.
5. Enter an invalid length and invalid check digit; confirm validation and explicit continue control.
6. Grant and deny camera permission; close with button and Escape; verify the camera indicator stops immediately.
7. Test scanner detection once and verify duplicate results do not appear.
8. Disable networking after initial load and confirm local demos still run.
9. Temporarily rename `data/recalls.json`; confirm the app never produces a no-match conclusion.
10. Use a screen reader to confirm loading/result announcements and scanner dialog naming/focus.

## GitHub Pages deployment

GitHub Pages provides HTTPS, which allows camera access on supported browsers.

1. Push these files to the repository's `main` branch.
2. On GitHub, open **Settings → Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**.
4. Select branch **main**, folder **/ (root)**, then **Save**.
5. Wait for the Pages deployment shown by GitHub, then open `https://USERNAME.github.io/REPOSITORY/` (or the configured custom domain).
6. Replace the footer's `USERNAME/REPOSITORY` placeholder with the actual repository URL before a public launch.

### Optional openFDA key and data refresh

Pages does not need a key. To raise openFDA limits for Actions:

1. Open **Settings → Secrets and variables → Actions**.
2. Choose **New repository secret**.
3. Name it exactly `OPENFDA_API_KEY`, paste the key, and choose **Add secret**.

To refresh manually, open **Actions → Refresh recall data → Run workflow**, select `main`, and choose **Run workflow**. The workflow also runs Mondays at 08:17 UTC, uses the built-in `GITHUB_TOKEN`, validates non-empty output, and commits only changed JSON. The key is passed through an environment variable; the script never prints its request URL, and no browser or generated file contains it.

## Testing on a phone and browser limitations

Deploy to Pages, open the HTTPS URL on the phone, tap **Scan a barcode**, and grant camera access. Prefer a physical device, bright diffuse light, a flat barcode, and 10–20 cm distance. iPhone Safari and Android Chrome may expose different camera resolution/focus behavior. Desktop browsers may select a webcam. Corporate policies, embedded browsers, denied permission, absent cameras, offline CDN access, or an insecure origin can prevent scanning; manual entry and local demos remain available. QR/Data Matrix decoding depends on the camera and formats supported by the pinned ZXing build.

## Demonstration scenarios

No barcode knowledge is required: cards launch confirmed match, lot/date required, no match, product not found, and manual-review scenarios. The matching package code is `L2407A`. Product/company names are fictional and explicitly labeled in the recall cache.

## Known limitations

This small cache is not comprehensive or real-time. FDA source descriptions often lack normalized UPCs and structured package fields. USDA ingestion is retention-only until a stable official API/format is verified. Open Food Facts may be slow, rate-limited, incomplete, or unavailable. Client-side identification cannot set a conventional custom `User-Agent` header, so the app sends an application-identification request header where the browser allows it. CDN loss disables camera decoding but not manual/demo operation. Barcode similarity cannot establish food safety, and some recalls have no barcode.

## Production hardening

A future production system should consider managed backend ingestion; a database-backed normalization pipeline; more frequent refresh; reliable UPC extraction from recall attachments; OCR for lot/date codes; GS1 product data; retailer receipt integrations; pantry monitoring and new-recall alerts; observability; formal data-quality, legal/safety, and privacy reviews; automated cross-browser/device tests; and human review of uncertain matches. These are intentionally out of scope here.

## Disclaimer, attribution, and license

> RecallCheck is an experimental prototype and does not replace official FDA, USDA, manufacturer, retailer, or healthcare guidance. Recall information can change, and some recalls may not include a barcode.

RecallCheck is not endorsed by FDA, USDA, Open Food Facts, or any company. Product data is attributed to Open Food Facts; recall links point to government sources. Code is available under the [MIT License](LICENSE). Database/source content may be subject to its source's own terms.
