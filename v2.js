(() => {
  "use strict";

  const VERSION = "2.0.0-beta";
  const DATA_URL = "data/recalls.json";
  const MAX_RESULTS = 8;
  let recallDataPromise = null;

  const $ = id => document.getElementById(id);
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  };

  function normalize(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function tokens(value) {
    return normalize(value).split(" ").filter(Boolean);
  }

  function isBarcodeQuery(value) {
    const code = String(value || "").replace(/\D/g, "");
    return [8, 12, 13, 14].includes(code.length) && normalize(value).replace(/\s/g, "") === code;
  }

  function loadRecallData() {
    if (!recallDataPromise) {
      recallDataPromise = fetch(DATA_URL, { cache: "no-store" }).then(response => {
        if (!response.ok) throw new Error(`Recall data request failed (${response.status})`);
        return response.json();
      });
    }
    return recallDataPromise;
  }

  function lifecycle(recall) {
    if (window.RecallCheck?.recallLifecycle) return window.RecallCheck.recallLifecycle(recall);
    const value = String(recall?.status || "").toLowerCase();
    if (["ongoing", "active", "open", "current"].includes(value)) return { state: "active", sourceStatus: recall.status || "Active" };
    if (value === "terminated") return { state: "terminated", sourceStatus: recall.status };
    if (["completed", "closed"].includes(value)) return { state: "closed", sourceStatus: recall.status };
    return { state: "unknown", sourceStatus: recall.status || "Status not listed" };
  }

  function dateValue(recall) {
    return recall?.timeline?.recallDate || recall?.recallDate || recall?.date || "";
  }

  function dateLabel(value) {
    const parsed = Date.parse(value);
    if (!Number.isFinite(parsed)) return "Date not listed";
    return new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }).format(parsed);
  }

  function scoreRecall(query, recall) {
    const q = normalize(query);
    const qTokens = tokens(query);
    if (!q || !qTokens.length) return 0;

    const brandNames = (recall.brandNames || []).map(normalize);
    const productNames = (recall.productNames || []).map(normalize);
    const firm = normalize(recall.recallingFirm);
    const reason = normalize(recall.reason);
    const combined = [...brandNames, ...productNames, firm, reason].filter(Boolean).join(" ");

    let score = 0;
    if (brandNames.some(value => value === q)) score += 120;
    if (productNames.some(value => value === q)) score += 115;
    if (firm === q) score += 90;
    if (brandNames.some(value => value.includes(q))) score += 75;
    if (productNames.some(value => value.includes(q))) score += 70;
    if (firm.includes(q)) score += 55;

    const matchedTokens = qTokens.filter(token => combined.includes(token));
    score += Math.round((matchedTokens.length / qTokens.length) * 45);

    const status = lifecycle(recall).state;
    if (status === "active") score += 35;
    else if (status === "unknown") score += 8;

    const recallTime = Date.parse(dateValue(recall));
    if (Number.isFinite(recallTime)) {
      const ageDays = Math.max(0, (Date.now() - recallTime) / 86400000);
      if (ageDays <= 30) score += 20;
      else if (ageDays <= 180) score += 10;
    }

    return matchedTokens.length === qTokens.length || score >= 55 ? score : 0;
  }

  function searchRecalls(query, data) {
    return (data?.recalls || [])
      .map(recall => ({ recall, score: scoreRecall(query, recall), life: lifecycle(recall) }))
      .filter(item => item.score > 0)
      .sort((a, b) => {
        const activeDelta = Number(b.life.state === "active") - Number(a.life.state === "active");
        if (activeDelta) return activeDelta;
        if (b.score !== a.score) return b.score - a.score;
        return (Date.parse(dateValue(b.recall)) || 0) - (Date.parse(dateValue(a.recall)) || 0);
      })
      .slice(0, MAX_RESULTS);
  }

  function safeOfficialUrl(recall) {
    if (window.RecallDiscovery?.safeOfficialUrl) return window.RecallDiscovery.safeOfficialUrl(recall?.officialUrl) || "";
    try {
      const url = new URL(recall?.officialUrl || "");
      if (url.protocol !== "https:") return "";
      return url.href;
    } catch (_) {
      return "";
    }
  }

  function renderSearchResults(query, matches) {
    const root = $("v2-search-results");
    const status = $("v2-search-status");
    if (!root || !status) return;
    root.replaceChildren();

    if (!matches.length) {
      status.textContent = `No matching recall records found for “${query}”.`;
      const empty = el("article", null, "v2-empty-state");
      empty.append(
        el("h3", "No matching recall records found"),
        el("p", "This text search checks the product, brand, recalling company, and recall reason fields in the available RecallCheck data. A no-match result is not a guarantee that a product is safe."),
        el("p", "Try a shorter brand name, a product name, or enter the package barcode for the strongest available check.", "v2-muted")
      );
      root.append(empty);
      return;
    }

    status.textContent = `${matches.length} matching recall record${matches.length === 1 ? "" : "s"} shown for “${query}”.`;

    matches.forEach(({ recall, life }) => {
      const card = el("article", null, `v2-recall-card v2-recall-card--${life.state}`);
      const badge = el("span", life.state === "active" ? "CURRENT" : life.state === "unknown" ? "VERIFY STATUS" : "HISTORICAL", "v2-status-badge");
      const title = el("h3", (recall.productNames || [])[0] || recall.recallingFirm || "Recall record");
      const meta = el("p", `${recall.agency || "Agency not listed"} · ${dateLabel(dateValue(recall))}`, "v2-recall-meta");
      const reason = el("p", recall.reason || "Recall reason not listed.");
      const company = el("p", `Recalling company: ${recall.recallingFirm || "Not listed"}`, "v2-muted");

      const actions = el("div", null, "v2-result-actions");
      if (recall.id) {
        const detail = el("a", "View RecallCheck details", "button button--secondary");
        detail.href = `recall.html?id=${encodeURIComponent(recall.id)}`;
        actions.append(detail);
      }
      const officialUrl = safeOfficialUrl(recall);
      if (officialUrl) {
        const official = el("a", "View official notice", "button button--secondary");
        official.href = officialUrl;
        official.target = "_blank";
        official.rel = "noopener noreferrer";
        actions.append(official);
      }

      card.append(badge, title, meta, reason, company);
      if ((recall.brandNames || []).length) card.append(el("p", `Brand: ${recall.brandNames.slice(0, 4).join(", ")}`, "v2-muted"));
      card.append(actions);
      root.append(card);
    });
  }

  function delegateBarcodeQuery(query) {
    const code = String(query || "").replace(/\D/g, "");
    $("manual-button")?.click();
    const input = $("barcode-input");
    if (!input) return;
    input.value = code;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    $("barcode-form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  }

  async function runSearch(query) {
    const value = String(query || "").trim();
    if (!value) return;

    if (isBarcodeQuery(value)) {
      $("v2-search-status").textContent = "Barcode detected. Running the package barcode check…";
      delegateBarcodeQuery(value);
      return;
    }

    const status = $("v2-search-status");
    const root = $("v2-search-results");
    status.textContent = "Searching available recall records…";
    root.replaceChildren();

    try {
      const data = await loadRecallData();
      renderSearchResults(value, searchRecalls(value, data));
    } catch (_) {
      status.textContent = "Recall search is temporarily unavailable.";
      const failure = el("article", null, "v2-empty-state");
      failure.append(
        el("h3", "Unable to search recalls"),
        el("p", "The recall data could not be loaded. Use the official FDA or USDA recall sites until RecallCheck can complete the search.")
      );
      root.replaceChildren(failure);
    }
  }

  function buildSearchUI() {
    if ($("v2-search")) return;
    const heroCopy = document.querySelector(".hero-copy");
    if (!heroCopy) return;

    const section = el("section", null, "v2-search-card");
    section.id = "v2-search";
    section.setAttribute("aria-labelledby", "v2-search-title");

    const eyebrow = el("p", "RECALLCHECK V2", "v2-eyebrow");
    const heading = el("h2", "Search by product, brand, or barcode");
    heading.id = "v2-search-title";
    const intro = el("p", "No camera needed. Search available recall records by product or brand, or paste a barcode for the strongest check.", "v2-search-intro");

    const form = el("form", null, "v2-search-form");
    form.id = "v2-search-form";
    form.setAttribute("role", "search");
    const label = el("label", "Product, brand, or barcode");
    label.htmlFor = "v2-search-input";
    const row = el("div", null, "v2-search-row");
    const input = el("input");
    input.id = "v2-search-input";
    input.name = "q";
    input.type = "search";
    input.autocomplete = "off";
    input.enterKeyHint = "search";
    input.placeholder = "Try Skittles, Trader Joe's, or a barcode";
    input.setAttribute("aria-describedby", "v2-search-help v2-search-status");
    const submit = el("button", "Search recalls", "primary");
    submit.type = "submit";
    row.append(input, submit);
    const help = el("small", "Text search looks across the recall records RecallCheck has available. Barcode checks remain the most specific option.");
    help.id = "v2-search-help";
    form.append(label, row, help);

    const status = el("p", "", "v2-search-status");
    status.id = "v2-search-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const results = el("div", null, "v2-search-results");
    results.id = "v2-search-results";

    form.addEventListener("submit", event => {
      event.preventDefault();
      runSearch(input.value);
    });

    section.append(eyebrow, heading, intro, form, status, results);

    const dataFacts = heroCopy.querySelector(".data-facts");
    if (dataFacts) dataFacts.insertAdjacentElement("beforebegin", section);
    else heroCopy.append(section);
  }

  function newestRecallDate(data) {
    let newest = 0;
    for (const recall of data?.recalls || []) {
      const value = Date.parse(dateValue(recall));
      if (Number.isFinite(value) && value > newest) newest = value;
    }
    return newest ? new Date(newest) : null;
  }

  async function buildSourceStrip() {
    if ($("v2-source-strip")) return;
    const facts = document.querySelector(".data-facts");
    if (!facts) return;
    const strip = el("div", null, "v2-source-strip");
    strip.id = "v2-source-strip";
    strip.setAttribute("role", "status");
    strip.setAttribute("aria-live", "polite");
    strip.textContent = "Checking live source status…";
    facts.insertAdjacentElement("afterend", strip);

    try {
      const data = await loadRecallData();
      const health = data?.dataHealth?.sources || {};
      const fda = health.FDA || {};
      const usda = health.USDA || {};
      const newest = newestRecallDate(data);
      const checked = data?.generatedAt ? new Date(data.generatedAt) : null;

      const items = [];
      items.push(`FDA ${fda.success || fda.recordCount > 0 ? "available" : "unavailable"}${fda.recordCount ? ` · ${fda.recordCount} records` : ""}`);
      items.push(`USDA ${usda.success || usda.recordCount > 0 ? "available" : "unavailable"}${usda.recordCount ? ` · ${usda.recordCount} records` : ""}`);
      if (newest) items.push(`Newest listed recall ${dateLabel(newest.toISOString())}`);
      if (checked) items.push(`Source check ${checked.toLocaleString()}`);
      strip.textContent = items.join(" · ");
    } catch (_) {
      strip.textContent = "Live source status could not be loaded. Use the official FDA or USDA sites if you need to verify a recall now.";
      strip.classList.add("v2-source-strip--warning");
    }
  }

  function detectInAppBrowser() {
    const ua = navigator.userAgent || "";
    const referrer = document.referrer || "";
    return /LinkedInApp|LinkedIn|FBAN|FBAV|Instagram|TikTok/i.test(ua) || /linkedin\.com|facebook\.com|instagram\.com/i.test(referrer);
  }

  function buildBrowserNotice() {
    if (!detectInAppBrowser() || $("v2-browser-notice")) return;
    const hero = document.querySelector(".hero-copy");
    if (!hero) return;
    const notice = el("aside", null, "v2-browser-notice");
    notice.id = "v2-browser-notice";
    notice.setAttribute("role", "status");
    notice.append(
      el("strong", "Camera scanning may be limited in this in-app browser."),
      el("span", " You can search recalls or enter a barcode here without leaving the app. For camera scanning, open RecallCheck directly in Safari or Chrome.")
    );
    hero.insertAdjacentElement("afterbegin", notice);
  }

  function markVersion() {
    document.documentElement.dataset.recallcheckVersion = VERSION;
    document.querySelectorAll("footer .copyright").forEach(node => {
      node.querySelectorAll("span").forEach(span => {
        if (/^Version\s/i.test(span.textContent || "")) span.textContent = `Version ${VERSION}`;
      });
    });
  }

  function init() {
    buildBrowserNotice();
    buildSearchUI();
    buildSourceStrip();
    markVersion();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();

  window.RecallCheckV2 = Object.freeze({ VERSION, searchRecalls, scoreRecall, runSearch });
})();
