(function (global) {
  "use strict";
  const ACTIVE = new Set(["active", "ongoing", "open", "current"]);
  const CLOSED = new Set(["terminated", "closed", "completed"]);
  const OFFICIAL_HOSTS = ["fda.gov", "accessdata.fda.gov", "fsis.usda.gov", "usda.gov"];

  function cleanSourceLabel(value) {
    let textValue = String(value ?? "").trim();
    if (!textValue) return "Status unknown";
    textValue = textValue.replace(/^\[\s*/, "").replace(/\s*\]$/, "").replace(/["']/g, "").replace(/\s*,\s*/g, ", ").replace(/_/g, " ").replace(/\s+/g, " ").trim();
    return textValue || "Status unknown";
  }

  function cleanRecallText(value, fallback = "See the official notice for details.") {
    const raw = String(value ?? "").trim();
    if (!raw) return fallback;
    return cleanSourceLabel(raw);
  }

  function signalText(record) {
    const source = record?.sourceRecord || {};
    const values = [record?.title, record?.productDescription, record?.reason, ...(record?.categories || []), ...(record?.hazards || []), source.field_recall_type, source.recall_type, source.product_type, source.product_types, source.category, source.recall_reason_description, source.reason_for_announcement, source.reason_for_recall, source.reason, source.product_description, source.product_items, source.field_product_items];
    return values.map(cleanSourceLabel).join(" ").toLowerCase();
  }

  function hasAny(textValue, patterns) { return patterns.some(pattern => pattern.test(textValue)); }
  function isExplicitlyNotReadyToEat(textValue) { return /\bnot[- ]ready[- ]to[- ]eat\b|\bnrte\b/.test(textValue); }

  const CATEGORY_RULES = {
    "meat-poultry": r => r.agency === "USDA",
    "dairy-eggs": r => hasAny(signalText(r), [/\bdairy\b/, /\bmilk\b/, /\bcheese\b/, /\bcream\b/, /\byogurt\b/, /\bbutter\b/, /\begg(s)?\b/]),
    "prepared-foods": r => {
      const signals = signalText(r);
      if (isExplicitlyNotReadyToEat(signals)) return false;
      return hasAny(signals, [/\bprepared food(s)?\b/, /\bready[- ]to[- ]eat\b/, /\brte\b/, /\bmeal(s)?\b/, /\bsandwich(es)?\b/, /\bsalad(s)?\b/, /\bsoup(s)?\b/, /\bpizza(s)?\b/, /\bwrap(s)?\b/, /\bbowl(s)?\b/, /\bentree(s)?\b/]);
    },
    allergens: r => hasAny(signalText(r), [/\ballergen(s)?\b/, /\bunreported allergen(s)?\b/, /\bundeclared\b/, /\bmisbranding\b.*\ballergen/, /\bmilk allergen\b/, /\begg allergen\b/, /\bpeanut(s)?\b/, /\bsoy\b/, /\bwheat\b/, /\bsesame\b/, /\b tree nut(s)?\b/, /\bshellfish\b/]),
    contamination: r => hasAny(signalText(r), [/\bproduct contamination\b/, /\bcontamination\b/, /\bcontaminated\b/, /\bsalmonella\b/, /\blisteria\b/, /\be\.?\s*coli\b/, /\bclostridium\b/, /\bbotulism\b/, /\bforeign material\b/, /\bforeign matter\b/])
  };

  const lifecycle = r => String(r?.lifecycle?.state || r?.status || "unknown").toLowerCase();
  const actionable = r => Boolean(r?.lifecycle?.isActionable) || ACTIVE.has(lifecycle(r));

  function currentRecalls(records) {
    return (records || []).filter(r => actionable(r) && !CLOSED.has(lifecycle(r))).sort((a,b) => Date.parse(b.recallDate || b.timeline?.recallDate || 0) - Date.parse(a.recallDate || a.timeline?.recallDate || 0));
  }

  function reliableCategories(record) { return Object.entries(CATEGORY_RULES).filter(([,test]) => test(record)).map(([key]) => key); }
  function filterRecalls(records, filter) { const list = currentRecalls(records); if (!filter || filter === "all") return list; if (["FDA", "USDA"].includes(filter)) return list.filter(r => r.agency === filter); return CATEGORY_RULES[filter] ? list.filter(CATEGORY_RULES[filter]) : []; }
  function categoryLabel(key) { return ({"meat-poultry":"Meat & poultry","dairy-eggs":"Dairy & eggs","prepared-foods":"Prepared foods",allergens:"Allergens",contamination:"Contamination"})[key] || key.replace(/-/g, " "); }
  function validRecallId(value) { return typeof value === "string" && value.length > 0 && value.length <= 160 && /^[A-Za-z0-9._:-]+$/.test(value); }
  function detailUrl(id) { return validRecallId(id) ? `recall.html?id=${encodeURIComponent(id)}` : "recalls.html"; }

  function safeOfficialUrl(value) {
    try { const u = new URL(value); return u.protocol === "https:" && OFFICIAL_HOSTS.some(h => u.hostname === h || u.hostname.endsWith(`.${h}`)) ? u.href : ""; }
    catch (_) { return ""; }
  }

  function formatDate(value) {
    const t = Date.parse(value);
    return Number.isFinite(t) ? new Intl.DateTimeFormat("en-US", {year:"numeric", month:"long", day:"numeric", timeZone:"UTC"}).format(t) : "Not listed";
  }

  function text(tag, value, className) { const n = document.createElement(tag); n.textContent = value == null ? "Not listed" : value; if (className) n.className = className; return n; }

  function renderCard(record) {
    const a = text("article", "", "recall-card");
    a.append(text("h3", record.title || record.productDescription || "Food recall"));
    const status = cleanSourceLabel(record.lifecycle?.sourceStatus || record.status);
    a.append(text("p", `${record.agency} · ${formatDate(record.recallDate || record.timeline?.recallDate)} · ${status}`, "recall-meta"), text("p", cleanRecallText(record.reason)));
    const cats = reliableCategories(record);
    if (cats.length) a.append(text("p", cats.map(categoryLabel).join(" · "), "category"));
    const link = text("a", "View recall", "secondary"); link.href = detailUrl(record.id); a.append(link); return a;
  }

  async function load() { const response = await fetch("data/recalls.json", {cache:"no-store"}); if (!response.ok) throw new Error("Recall data unavailable"); return response.json(); }

  function setupNavigation() {
    const button = document.querySelector("[data-menu-button]"), nav = document.querySelector("[data-nav]"), more = nav?.querySelector(".more-menu"), mobile = matchMedia("(max-width: 960px)");
    if (!button || !nav) return;
    const close = (returnFocus=false) => { button.setAttribute("aria-expanded", "false"); nav.dataset.open = "false"; if (returnFocus) button.focus(); };
    const syncLayout = () => { if (more) more.open = mobile.matches; if (!mobile.matches) close(); };
    button.addEventListener("click", () => { const open = button.getAttribute("aria-expanded") !== "true"; button.setAttribute("aria-expanded", String(open)); nav.dataset.open = String(open); if (open) nav.querySelector("a")?.focus(); });
    nav.addEventListener("click", event => { if (event.target.closest("a") && mobile.matches) close(); });
    document.addEventListener("click", event => { if (button.getAttribute("aria-expanded") === "true" && !event.target.closest(".site-header")) close(); });
    document.addEventListener("keydown", event => { if (event.key === "Escape") { if (button.getAttribute("aria-expanded") === "true") close(true); else if (more?.open) { more.open = false; more.querySelector("summary")?.focus(); } } });
    mobile.addEventListener?.("change", syncLayout); syncLayout();
  }

  async function recent() {
    const root = document.querySelector("[data-recent]"); if (!root) return;
    try { const data = await load(); root.replaceChildren(...currentRecalls(data.recalls).slice(0,3).map(renderCard)); }
    catch (_) { root.replaceChildren(text("p", "Recent recalls could not be loaded. Visit the official FDA or USDA recall pages.")); }
  }

  async function listing() {
    const root = document.querySelector("[data-recall-list]"); if (!root) return;
    let records = [];
    try { records = (await load()).recalls; } catch (_) { root.replaceChildren(text("p", "Current recalls could not be loaded.")); return; }
    const buttons = [...document.querySelectorAll("[data-filter]")];
    const draw = filter => { const shown = filterRecalls(records, filter); root.replaceChildren(...shown.map(renderCard)); if (!shown.length) root.append(text("p", "No current recalls match this filter.")); buttons.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.filter === filter))); };
    buttons.forEach(b => b.addEventListener("click", () => draw(b.dataset.filter))); draw("all");
  }

  async function detail() {
    const root = document.querySelector("[data-recall-detail]"); if (!root) return;
    const id = new URLSearchParams(location.search).get("id"); if (!validRecallId(id)) return notFound(root);
    try {
      const data = await load(), r = data.recalls.find(x => x.id === id); if (!r) return notFound(root);
      const current = actionable(r), status = current ? "Current recall" : "Historical recall";
      document.title = `${r.title || "Recall details"} | RecallCheck`;
      const article = text("article", "", `result result--${current ? "critical" : "historical"}`), banner = text("header", "", `result-banner result-banner--${current ? "critical" : "historical"}`), bannerCopy = text("div", "");
      bannerCopy.append(text("p", `${status} · ${r.agency}`, "result-label"), text("h1", r.title || r.productDescription || "Recall details", "result-heading")); banner.append(bannerCopy);
      const summary = text("section", "", "result-summary");
      summary.append(text("p", current ? "Review the official recall instructions before eating or serving this product." : "The source record is listed as closed or terminated. This page does not identify a current package as part of an active recall.", "result-instruction"), text("h2", "Affected package"), text("p", [...(r.lotCodes || []), ...(r.dateCodes || []), ...(r.packageSizes || []), ...(r.establishmentNumbers || [])].join(", ") || r.productDescription || "See the official notice."));
      const official = safeOfficialUrl(r.officialUrl);
      if (official) { const link = text("a", current ? "View official recall instructions" : "View historical recall", "button " + (current ? "button--critical" : "button--secondary")); link.href = official; link.target = "_blank"; link.rel = "noopener noreferrer"; summary.append(link); }
      const details = text("section", "", "result-details"), dl = text("dl", "", "details");
      const sourceHealth = data?.dataHealth?.sources?.[r.agency] || {};
      [["Recall reason",cleanRecallText(r.reason, "See official notice")],["Recalling company",r.recallingFirm],["Agency",r.agency],["Recall date",formatDate(r.recallDate || r.timeline?.recallDate)],["Official status",cleanSourceLabel(r.lifecycle?.sourceStatus || r.status)],["Distribution",cleanRecallText(r.distribution, "See official notice")],["Source last successful retrieval",formatDate(sourceHealth.lastSuccessfulUpdate || sourceHealth.retrievedAt)],["Newest listed recall in this source",formatDate(sourceHealth.newestRecallDate)],["Dataset generated",formatDate(data.generatedAt)]].forEach(([k,v]) => dl.append(text("dt",k), text("dd",v)));
      details.append(dl);
      const technical = text("details", "", "technical"), technicalSummary = text("summary", "Technical identifiers"), technicalBody = text("p", [...(r.upcs || []), ...(r.gtins || []), ...(r.establishmentNumbers || [])].join(", ") || "No identifiers listed");
      technical.append(technicalSummary, technicalBody); details.append(technical); article.append(banner, summary, details);
      const actions = text("div", "", "actions result-actions"), scan = text("a", "Scan another product", "button button--secondary"); scan.href = "index.html";
      const share = text("button", navigator.share ? "Share this recall" : "Copy recall link", "button button--secondary"), live = text("p", "", "share-status"); share.type = "button"; live.setAttribute("role", "status"); share.addEventListener("click", () => shareRecall(r,status,live,share)); actions.append(share,scan); article.append(actions,live); root.replaceChildren(article);
    } catch (_) { notFound(root); }
  }

  async function copyUrl(live) { try { await navigator.clipboard.writeText(location.href); live.textContent = "Recall link copied"; } catch (_) { live.textContent = "Sharing failed. Copy the address from your browser."; } }
  async function shareRecall(r,status,live,button) { const payload = {title:r.title || "Food recall", text:`${r.agency} · ${status}`, url:location.href}; if (navigator.share) { try { await navigator.share(payload); return; } catch (e) { if (e?.name === "AbortError") { live.textContent = "Sharing canceled."; return; } live.textContent = "Sharing failed. Copy the recall link instead."; button.textContent = "Copy recall link"; button.onclick = () => copyUrl(live); return; } } return copyUrl(live); }
  function notFound(root) { root.replaceChildren(text("h1", "Recall not found"), text("p", "This recall link is invalid or the record is unavailable.")); const a = text("div", "", "actions"); [["Return to current recalls","recalls.html"],["Scan a product","index.html"],["Visit FDA recalls","https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts"],["Visit USDA recalls","https://www.fsis.usda.gov/recalls"]].forEach(([label,url]) => { const x = text("a",label,label.startsWith("Return") ? "primary" : "secondary"); x.href = url; if (url.startsWith("https")) { x.target = "_blank"; x.rel = "noopener noreferrer"; } a.append(x); }); root.append(a); }

  function init() { setupNavigation(); recent(); listing(); detail(); }
  const api = {currentRecalls, filterRecalls, reliableCategories, cleanSourceLabel, cleanRecallText, validRecallId, detailUrl, safeOfficialUrl, shareRecall};
  global.RecallDiscovery = Object.freeze(api);
  if (typeof module !== "undefined") module.exports = api;
  if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded", init);
})(typeof window !== "undefined" ? window : globalThis);
