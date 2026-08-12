(() => {
  "use strict";

  const nativeFetch = window.fetch.bind(window);
  const OFF_HOST = "world.openfoodfacts.org";
  const PRODUCT_PATH = /^\/api\/v2\/product\/([0-9]+)\.json$/;

  function barcodeCandidates(value) {
    const code = String(value || "").replace(/\D/g, "");
    const candidates = new Set([code]);

    // UPC-A and EAN-13 are often the same GTIN with or without a leading zero.
    if (code.length === 12) candidates.add(`0${code}`);
    if (code.length === 13 && code.startsWith("0")) candidates.add(code.slice(1));

    // GTIN-14 may similarly carry zero padding. Only remove leading zero
    // padding; never alter significant digits.
    if (code.length === 14 && code.startsWith("0")) candidates.add(code.slice(1));
    if (code.length === 14 && code.startsWith("00")) candidates.add(code.slice(2));

    return [...candidates].filter(Boolean);
  }

  async function productWasFound(response) {
    if (!response?.ok) return false;
    try {
      const body = await response.clone().json();
      return body?.status === 1 && Boolean(body.product);
    } catch (_) {
      return false;
    }
  }

  window.fetch = async function recallCheckFetch(input, init) {
    const originalUrl = typeof input === "string" ? input : input?.url;
    let parsed;
    try { parsed = new URL(originalUrl, window.location.href); }
    catch (_) { return nativeFetch(input, init); }

    const match = parsed.hostname === OFF_HOST ? parsed.pathname.match(PRODUCT_PATH) : null;
    if (!match) return nativeFetch(input, init);

    const originalResponse = await nativeFetch(input, init);
    if (await productWasFound(originalResponse)) return originalResponse;

    const originalCode = match[1];
    const alternatives = barcodeCandidates(originalCode).filter(code => code !== originalCode);

    for (const candidate of alternatives) {
      const retryUrl = new URL(parsed.href);
      retryUrl.pathname = `/api/v2/product/${encodeURIComponent(candidate)}.json`;
      try {
        const retryResponse = await nativeFetch(retryUrl.href, init);
        if (await productWasFound(retryResponse)) return retryResponse;
      } catch (_) {
        // A failed equivalent lookup must never turn a valid original miss into
        // a service failure. RecallCheck still checks the original barcode
        // directly against FDA/USDA records.
      }
    }

    return originalResponse;
  };

  // Make an Open Food Facts directory miss distinct from a scanner failure.
  // app.js already continues with the direct FDA/USDA barcode check; this layer
  // makes that successful fallback explicit to the user.
  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("result-panel");
    if (!root) return;
    const clarified = new WeakSet();
    const clarify = () => {
      root.querySelectorAll(".product-identity").forEach(identity => {
        if (clarified.has(identity)) return;
        const heading = identity.querySelector("h3");
        const paragraph = identity.querySelector("p");
        if (!heading || heading.textContent.trim() !== "Product name not found") return;
        clarified.add(identity);
        heading.textContent = "Product details unavailable";
        if (paragraph) paragraph.textContent = "The barcode scanned successfully, but Open Food Facts did not have a matching product record. RecallCheck still compared this barcode with the available FDA and USDA recall records.";
      });
    };
    clarify();
    new MutationObserver(clarify).observe(root, { childList: true, subtree: true });
  });

  window.RecallCheckProductLookup = Object.freeze({ barcodeCandidates });
})();
