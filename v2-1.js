(() => {
  "use strict";

  const VERSION = "2.1.0-beta";
  const HISTORY_KEY = "recallcheck.recentChecks.v2";
  const FEEDBACK_KEY = "recallcheck.localFeedback.v2";
  const MAX_HISTORY = 6;
  const nativeFetch = window.fetch.bind(window);
  const OFF_HOST = "world.openfoodfacts.org";
  const PRODUCT_PATH = /^\/api\/v2\/product\/([0-9]+)\.json$/;

  const $ = id => document.getElementById(id);
  const normalizeCode = value => String(value || "").replace(/\D/g, "");
  const storageAvailable = (() => {
    try {
      const key = "__rc_test__";
      localStorage.setItem(key, "1");
      localStorage.removeItem(key);
      return true;
    } catch (_) { return false; }
  })();

  function barcodeCandidates(value) {
    const code = normalizeCode(value);
    const set = new Set([code]);
    if (code.length === 12) set.add(`0${code}`);
    if (code.length === 13 && code.startsWith("0")) set.add(code.slice(1));
    if (code.length === 14 && code.startsWith("0")) set.add(code.slice(1));
    if (code.length === 14 && code.startsWith("00")) set.add(code.slice(2));
    return [...set].filter(Boolean);
  }

  async function bodyHasProduct(response) {
    if (!response?.ok) return false;
    try {
      const body = await response.clone().json();
      return body?.status === 1 && Boolean(body.product);
    } catch (_) { return false; }
  }

  async function searchOpenFoodFactsByCode(code, init) {
    const fields = "code,product_name,generic_name,brands,quantity,image_front_small_url,categories,countries,manufacturing_places,owner_fields";
    for (const candidate of barcodeCandidates(code)) {
      const url = new URL("https://world.openfoodfacts.org/cgi/search.pl");
      url.searchParams.set("search_terms", candidate);
      url.searchParams.set("search_simple", "1");
      url.searchParams.set("action", "process");
      url.searchParams.set("json", "1");
      url.searchParams.set("page_size", "10");
      url.searchParams.set("fields", fields);
      try {
        const response = await nativeFetch(url.href, { ...init, method: "GET", body: undefined });
        if (!response.ok) continue;
        const body = await response.json();
        const product = (body?.products || []).find(item => barcodeCandidates(item?.code).some(v => barcodeCandidates(candidate).includes(v)));
        if (!product) continue;
        return new Response(JSON.stringify({ status: 1, code: product.code || candidate, product }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      } catch (_) {}
    }
    return null;
  }

  window.fetch = async function recallCheckV21Fetch(input, init) {
    const originalUrl = typeof input === "string" ? input : input?.url;
    let url;
    try { url = new URL(originalUrl, location.href); }
    catch (_) { return nativeFetch(input, init); }
    const match = url.hostname === OFF_HOST ? url.pathname.match(PRODUCT_PATH) : null;
    if (!match) return nativeFetch(input, init);

    const response = await nativeFetch(input, init);
    if (await bodyHasProduct(response)) return response;
    const fallback = await searchOpenFoodFactsByCode(match[1], init);
    return fallback || response;
  };

  function moveTo(node, focusTarget) {
    if (!node || node.hidden) return;
    requestAnimationFrame(() => {
      node.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
      const target = focusTarget || node.querySelector("h1,h2,h3,[tabindex='-1']");
      if (target) {
        if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
        setTimeout(() => target.focus({ preventScroll: true }), 180);
      }
    });
  }

  function observeScanFlow() {
    const confirmation = $("product-confirmation");
    const results = $("results");
    if (confirmation) {
      new MutationObserver(() => {
        if (!confirmation.hidden) moveTo(confirmation, $("confirmation-title"));
      }).observe(confirmation, { attributes: true, attributeFilter: ["hidden"] });
    }
    if (results) {
      new MutationObserver(() => {
        if (!results.hidden) {
          moveTo(results, $("completed-result-heading"));
          captureRecentCheck();
          enhanceMissingIdentity();
          attachLocalFeedbackCapture();
        }
      }).observe(results, { attributes: true, attributeFilter: ["hidden"] });
    }
  }

  function readJson(key, fallback) {
    if (!storageAvailable) return fallback;
    try { return JSON.parse(localStorage.getItem(key) || "null") || fallback; }
    catch (_) { return fallback; }
  }

  function writeJson(key, value) {
    if (!storageAvailable) return;
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {}
  }

  function resultSnapshot() {
    const product = $("product-summary");
    const result = $("result-panel");
    if (!result || result.childElementCount === 0) return null;
    const productName = product?.querySelector(".product h3")?.textContent?.trim() ||
      result.querySelector(".product-identity h3")?.textContent?.trim() || "Barcode check";
    const barcodeText = [...(product?.querySelectorAll("p") || [])].map(p => p.textContent || "").find(t => /^Barcode:/i.test(t));
    const barcode = barcodeText ? normalizeCode(barcodeText.replace(/^Barcode:\s*/i, "")) : "";
    const heading = result.querySelector(".result-heading")?.textContent?.trim() || "Recall check result";
    const label = result.querySelector(".result-label")?.textContent?.trim() || "Result";
    return { productName, barcode, heading, label, checkedAt: new Date().toISOString() };
  }

  function captureRecentCheck() {
    const snapshot = resultSnapshot();
    if (!snapshot) return;
    const history = readJson(HISTORY_KEY, []);
    const signature = `${snapshot.productName}|${snapshot.barcode}|${snapshot.heading}`;
    const next = [snapshot, ...history.filter(item => `${item.productName}|${item.barcode}|${item.heading}` !== signature)].slice(0, MAX_HISTORY);
    writeJson(HISTORY_KEY, next);
    renderRecentChecks();
  }

  function renderRecentChecks() {
    let section = $("recent-checks-v21");
    const history = readJson(HISTORY_KEY, []);
    if (!history.length) {
      section?.remove();
      return;
    }
    if (!section) {
      section = document.createElement("section");
      section.id = "recent-checks-v21";
      section.className = "content-section recent-checks-v21";
      section.setAttribute("aria-labelledby", "recent-checks-v21-title");
      const results = $("results");
      results?.insertAdjacentElement("afterend", section);
    }
    section.replaceChildren();
    const heading = document.createElement("div");
    heading.className = "section-heading";
    heading.innerHTML = '<h2 id="recent-checks-v21-title">Recent checks on this device</h2>';
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "text-button";
    clear.textContent = "Clear";
    clear.addEventListener("click", () => { writeJson(HISTORY_KEY, []); renderRecentChecks(); });
    heading.append(clear);
    const list = document.createElement("div");
    list.className = "recent-checks-list-v21";
    history.forEach(item => {
      const card = document.createElement("article");
      card.className = "recent-check-v21";
      const title = document.createElement("h3");
      title.textContent = item.productName;
      const status = document.createElement("p");
      status.innerHTML = `<strong>${item.label}</strong> · ${item.heading}`;
      const meta = document.createElement("p");
      meta.className = "v2-muted";
      meta.textContent = `${item.barcode ? `Barcode ${item.barcode} · ` : ""}${new Date(item.checkedAt).toLocaleString()}`;
      card.append(title, status, meta);
      if (item.barcode) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "button button--secondary";
        button.textContent = "Check again";
        button.addEventListener("click", () => {
          $("manual-button")?.click();
          const input = $("barcode-input");
          if (input) input.value = item.barcode;
          $("barcode-form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
        });
        card.append(button);
      }
      list.append(card);
    });
    const privacy = document.createElement("p");
    privacy.className = "v2-muted";
    privacy.textContent = "Recent checks are stored only in this browser on this device.";
    section.append(heading, list, privacy);
  }

  function enhanceMissingIdentity() {
    const identity = $("result-panel")?.querySelector(".product-identity");
    if (!identity || identity.dataset.v21Enhanced === "true") return;
    identity.dataset.v21Enhanced = "true";
    const actions = document.createElement("div");
    actions.className = "result-actions identity-actions-v21";
    const search = document.createElement("button");
    search.type = "button";
    search.className = "button button--primary";
    search.textContent = "Search by product or brand";
    search.addEventListener("click", () => {
      const searchCard = $("v2-search");
      const input = $("v2-search-input");
      if (searchCard) moveTo(searchCard, input);
    });
    const again = document.createElement("button");
    again.type = "button";
    again.className = "button button--secondary";
    again.textContent = "Scan again";
    again.addEventListener("click", () => $("scan-button")?.click());
    actions.append(search, again);
    identity.append(actions);
  }

  function attachLocalFeedbackCapture() {
    const panel = $("result-panel");
    if (!panel || panel.dataset.v21Feedback === "true") return;
    panel.dataset.v21Feedback = "true";
    panel.addEventListener("click", event => {
      const button = event.target.closest?.(".feedback-choice");
      if (!button) return;
      const choice = String(button.textContent || "").trim().toLowerCase();
      const feedback = readJson(FEEDBACK_KEY, []);
      feedback.unshift({ choice, result: resultSnapshot(), at: new Date().toISOString() });
      writeJson(FEEDBACK_KEY, feedback.slice(0, 50));
    });
  }

  function markVersion() {
    document.documentElement.dataset.recallcheckVersion = VERSION;
    document.querySelectorAll("footer .copyright span").forEach(span => {
      if (/^Version\s/i.test(span.textContent || "")) span.textContent = `Version ${VERSION}`;
    });
  }

  function init() {
    markVersion();
    observeScanFlow();
    renderRecentChecks();
    enhanceMissingIdentity();
    attachLocalFeedbackCapture();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();

  window.RecallCheckV21 = Object.freeze({ VERSION, barcodeCandidates, renderRecentChecks });
})();
