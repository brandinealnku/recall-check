(() => {
  "use strict";

  const previousFetch = window.fetch.bind(window);
  const OFF_HOST = "world.openfoodfacts.org";
  const PRODUCT_PATH = /^\/api\/v2\/product\/([0-9]+)\.json$/;
  const CACHE_KEY = "recallcheck.productIdentity.v1";
  const RECENT_KEY = "recallcheck.recentChecks.v2";
  const MAX_CACHE = 40;

  const normalizeCode = value => String(value || "").replace(/\D/g, "");

  function barcodeCandidates(value) {
    const code = normalizeCode(value);
    const set = new Set([code]);
    if (code.length === 12) set.add(`0${code}`);
    if (code.length === 13 && code.startsWith("0")) set.add(code.slice(1));
    if (code.length === 14 && code.startsWith("0")) set.add(code.slice(1));
    if (code.length === 14 && code.startsWith("00")) set.add(code.slice(2));
    return [...set].filter(Boolean);
  }

  function readJson(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key) || "null") || fallback; }
    catch (_) { return fallback; }
  }

  function writeJson(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); }
    catch (_) {}
  }

  function cleanedInit(init = {}) {
    const next = { ...init };
    const headers = new Headers(init.headers || {});
    // X-Requested-With turns a simple cross-origin GET into a preflighted request
    // in Safari. It is not required by Open Food Facts and can make lookups less
    // reliable on mobile networks.
    headers.delete("X-Requested-With");
    headers.delete("x-requested-with");
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    next.headers = headers;
    return next;
  }

  async function responseProduct(response) {
    if (!response?.ok) return null;
    try {
      const body = await response.clone().json();
      if (body?.status === 1 && body.product) return { body, product: body.product };
    } catch (_) {}
    return null;
  }

  function cacheProduct(requestedCode, found) {
    if (!found?.product) return;
    const cache = readJson(CACHE_KEY, {});
    const product = { ...found.product };
    const canonical = normalizeCode(product.code || found.body?.code || requestedCode);
    const entry = { product, code: canonical || normalizeCode(requestedCode), cachedAt: new Date().toISOString(), source: "Open Food Facts" };
    barcodeCandidates(requestedCode).forEach(code => { cache[code] = entry; });
    barcodeCandidates(canonical).forEach(code => { cache[code] = entry; });
    const ordered = Object.entries(cache).sort((a, b) => Date.parse(b[1]?.cachedAt || 0) - Date.parse(a[1]?.cachedAt || 0));
    writeJson(CACHE_KEY, Object.fromEntries(ordered.slice(0, MAX_CACHE)));
  }

  function cachedProduct(code) {
    const cache = readJson(CACHE_KEY, {});
    for (const candidate of barcodeCandidates(code)) {
      if (cache[candidate]?.product) return { ...cache[candidate].product, code: cache[candidate].product.code || candidate, recallcheck_identity_source: "cached Open Food Facts result" };
    }
    return null;
  }

  function recentProduct(code) {
    const recent = readJson(RECENT_KEY, []);
    const candidates = new Set(barcodeCandidates(code));
    const item = recent.find(entry => barcodeCandidates(entry?.barcode).some(value => candidates.has(value)));
    const name = String(item?.productName || "").trim();
    if (!name || /^(barcode check|product details unavailable|product name not found)$/i.test(name)) return null;
    return {
      code: normalizeCode(item.barcode || code),
      product_name: name,
      generic_name: "",
      brands: "",
      quantity: "",
      image_front_small_url: "",
      recallcheck_identity_source: "previously identified on this device"
    };
  }

  function productResponse(product, requestedCode) {
    return new Response(JSON.stringify({ status: 1, code: product.code || requestedCode, product }), {
      status: 200,
      headers: { "Content-Type": "application/json", "X-RecallCheck-Identity": product.recallcheck_identity_source || "cache" }
    });
  }

  window.fetch = async function recallCheckProductLookup(input, init) {
    const originalUrl = typeof input === "string" ? input : input?.url;
    let parsed;
    try { parsed = new URL(originalUrl, window.location.href); }
    catch (_) { return previousFetch(input, init); }

    const match = parsed.hostname === OFF_HOST ? parsed.pathname.match(PRODUCT_PATH) : null;
    if (!match) return previousFetch(input, init);

    const requestedCode = match[1];
    let response;
    try {
      response = await previousFetch(parsed.href, cleanedInit(init));
      const found = await responseProduct(response);
      if (found) {
        cacheProduct(requestedCode, found);
        return response;
      }
    } catch (_) {
      response = null;
    }

    // If the directory is temporarily missing a product that RecallCheck has
    // already identified successfully, preserve that identity on this device.
    const cached = cachedProduct(requestedCode) || recentProduct(requestedCode);
    if (cached) return productResponse(cached, requestedCode);

    if (response) return response;
    throw new Error("service");
  };

  window.RecallCheckProductIdentity = Object.freeze({ barcodeCandidates, cachedProduct, recentProduct });
})();
