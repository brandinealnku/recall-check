(() => {
  "use strict";

  const DATA_URL = "data/recalls.json";
  const MAX_RESULTS = 8;
  let recallDataPromise = null;

  const normalize = value => String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

  const tokens = value => normalize(value).split(" ").filter(Boolean);

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

  function fieldMatchStrength(query, field) {
    const q = normalize(query);
    const value = normalize(field);
    if (!q || !value) return 0;
    if (value === q) return 5;
    if (value.includes(q)) return 4;

    const qTokens = tokens(q);
    const fieldTokens = new Set(tokens(value));
    if (!qTokens.length) return 0;
    const matched = qTokens.filter(token => fieldTokens.has(token)).length;
    if (matched === qTokens.length) return 3;
    if (qTokens.length > 1 && matched / qTokens.length >= 0.75) return 2;
    return 0;
  }

  function relevance(query, recall) {
    const brandStrength = Math.max(0, ...(recall.brandNames || []).map(value => fieldMatchStrength(query, value)));
    const productStrength = Math.max(0, ...(recall.productNames || []).map(value => fieldMatchStrength(query, value)));
    const firmStrength = fieldMatchStrength(query, recall.recallingFirm);
    const lexicalStrength = Math.max(brandStrength, productStrength, firmStrength);
    if (!lexicalStrength) return 0;

    let score = 0;
    score += brandStrength * 30;
    score += productStrength * 28;
    score += firmStrength * 20;

    const life = lifecycle(recall).state;
    if (life === "active") score += 15;
    else if (life === "unknown") score += 3;

    const recallTime = Date.parse(dateValue(recall));
    if (Number.isFinite(recallTime)) {
      const ageDays = Math.max(0, (Date.now() - recallTime) / 86400000);
      if (ageDays <= 30) score += 8;
      else if (ageDays <= 180) score += 4;
    }
    return score;
  }

  function searchRecalls(query, data) {
    return (data?.recalls || [])
      .map(recall => ({ recall, score: relevance(query, recall), life: lifecycle(recall) }))
      .filter(item => item.score > 0)
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        const activeDelta = Number(b.life.state === "active") - Number(a.life.state === "active");
        if (activeDelta) return activeDelta;
        return (Date.parse(dateValue(b.recall)) || 0) - (Date.parse(dateValue(a.recall)) || 0);
      })
      .slice(0, MAX_RESULTS);
  }

  function cleanDisplayValue(value) {
    if (Array.isArray(value)) return value.map(cleanDisplayValue).filter(Boolean).join("; ");
    const text = String(value || "").trim();
    if (!text) return "";
    return text
      .replace(/^\[?["']?/, "")
      .replace(/["']?\]?$/, "")
      .replace(/\\n/g, " ")
      .replace(/\\r/g, " ")
      .replace(/\s{2,}/g, " ")
      .trim();
  }

  function safeOfficialUrl(recall) {
    if (window.RecallDiscovery?.safeOfficialUrl) return window.RecallDiscovery.safeOfficialUrl(recall?.officialUrl) || "";
    try {
      const url = new URL(recall?.officialUrl || "");
      return url.protocol === "https:" ? url.href : "";
    } catch (_) {
      return "";
    }
  }

  function make(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function render(query, matches) {
    const root = document.getElementById("v2-search-results");
    const status = document.getElementById("v2-search-status");
    if (!root || !status) return;
    root.replaceChildren();

    if (!matches.length) {
      status.textContent = `No matching recalls found for “${query}”.`;
      const empty = make("article", null, "v2-empty-state");
      empty.append(
        make("h3", "No matching recalls found"),
        make("p", `We didn’t find a recall matching “${query}” in the records currently available to RecallCheck.`),
        make("p", "Try the brand name, a more specific product name, or scan the package barcode. A search with no results does not guarantee the product is safe.", "v2-muted")
      );
      root.append(empty);
      return;
    }

    status.textContent = `${matches.length} relevant recall record${matches.length === 1 ? "" : "s"} found for “${query}”.`;

    for (const { recall, life } of matches) {
      const card = make("article", null, `v2-recall-card v2-recall-card--${life.state}`);
      const badge = make("span", life.state === "active" ? "CURRENT RECALL" : life.state === "unknown" ? "CHECK STATUS" : "OLDER RECALL", "v2-status-badge");
      const title = make("h3", cleanDisplayValue((recall.productNames || [])[0]) || cleanDisplayValue(recall.recallingFirm) || "Recall record");
      const meta = make("p", `${recall.agency || "Agency not listed"} · ${dateLabel(dateValue(recall))}`, "v2-recall-meta");
      const reason = make("p", cleanDisplayValue(recall.reason) || "Recall reason not listed.");
      const firm = cleanDisplayValue(recall.recallingFirm);
      const company = make("p", `Recalling company: ${firm || "Not listed"}`, "v2-muted");
      const actions = make("div", null, "v2-result-actions");

      if (recall.id) {
        const detail = make("a", "View RecallCheck details", "button button--secondary");
        detail.href = `recall.html?id=${encodeURIComponent(recall.id)}`;
        actions.append(detail);
      }
      const officialUrl = safeOfficialUrl(recall);
      if (officialUrl) {
        const official = make("a", "View official recall", "button button--secondary");
        official.href = officialUrl;
        official.target = "_blank";
        official.rel = "noopener noreferrer";
        actions.append(official);
      }

      card.append(badge, title, meta, reason, company);
      const brands = (recall.brandNames || []).map(cleanDisplayValue).filter(Boolean);
      if (brands.length) card.append(make("p", `Brand: ${brands.slice(0, 4).join(", ")}`, "v2-muted"));
      card.append(actions);
      root.append(card);
    }
  }

  async function runFixedSearch(query) {
    const status = document.getElementById("v2-search-status");
    const root = document.getElementById("v2-search-results");
    if (!status || !root) return;
    status.textContent = "Searching available recalls…";
    root.replaceChildren();
    try {
      const data = await loadRecallData();
      render(query, searchRecalls(query, data));
    } catch (_) {
      status.textContent = "Recall search is temporarily unavailable.";
      const failure = make("article", null, "v2-empty-state");
      failure.append(
        make("h3", "We couldn’t search recalls"),
        make("p", "RecallCheck couldn’t load the recall data right now. Try again, or use the official FDA or USDA recall sites to check directly.")
      );
      root.replaceChildren(failure);
    }
  }

  document.addEventListener("submit", event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.id !== "v2-search-form") return;
    const input = document.getElementById("v2-search-input");
    const query = String(input?.value || "").trim();
    if (!query || isBarcodeQuery(query)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    runFixedSearch(query);
  }, true);

  window.RecallCheckV2SearchFix = Object.freeze({ relevance, searchRecalls });
})();
