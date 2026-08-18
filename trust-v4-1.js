(() => {
  "use strict";

  const STATUS_URL = "data/source-status.json";
  const OFFICIAL = {
    FDA: "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts",
    USDA: "https://www.fsis.usda.gov/recalls"
  };
  let sourceStatus = null;

  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  };

  function sourceState(agency) {
    const source = sourceStatus?.sources?.[agency] || {};
    const raw = String(source.coverageStatus || source.qualityStatus || "").toLowerCase();
    const freshnessVerified = source.freshnessValidated===true;
    const healthy = source.success === true && source.current === true && freshnessVerified && (raw === "current" || raw === "healthy");
    const failed = source.success === false || raw === "failed" || raw === "unavailable";
    return { agency, source, healthy, failed, label: healthy ? "Current" : failed ? "Unavailable" : "Needs attention" };
  }

  function allHealthy() {
    return sourceState("FDA").healthy && sourceState("USDA").healthy;
  }

  function checkedDate() {
    const raw = sourceStatus?.checkedAt || sourceStatus?.generatedAt;
    const parsed = Date.parse(raw || "");
    return Number.isFinite(parsed) ? new Date(parsed) : null;
  }

  function formatChecked(date) {
    if (!date) return "Verification time unavailable";
    return new Intl.DateTimeFormat("en-US", {
      month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit"
    }).format(date);
  }

  function formatRecordDate(value) {
    const parsed = Date.parse(value || "");
    if (!Number.isFinite(parsed)) return "not available";
    return new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }).format(parsed);
  }

  function relativeChecked(date) {
    if (!date) return "Verification time unavailable";
    const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
    if (minutes < 1) return "checked just now";
    if (minutes < 60) return `checked ${minutes} min ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `checked ${hours} hr${hours === 1 ? "" : "s"} ago`;
    return `checked ${formatChecked(date)}`;
  }

  function surfaceEntries(state) {
    const source = state.source || {};
    const raw = source.surfaces || source.inputs || source.sourceSurfaces || {};
    const entries = [];
    if (Array.isArray(raw)) {
      raw.forEach(item => entries.push({
        name: item.name || item.label || item.id || "Official source",
        success: item.success !== false,
        checkedAt: item.checkedAt || item.lastSuccessfulUpdate || ""
      }));
    } else if (raw && typeof raw === "object") {
      Object.entries(raw).forEach(([name, item]) => {
        const value = item && typeof item === "object" ? item : {};
        entries.push({ name: value.label || name, success: value.success !== false, checkedAt: value.checkedAt || value.lastSuccessfulUpdate || "" });
      });
    }
    if (!entries.length) {
      entries.push({
        name: state.agency === "FDA" ? "FDA official recall sources" : "USDA FSIS Recall API",
        success: state.source.success !== false,
        checkedAt: state.source.checkedAt || state.source.lastSuccessfulUpdate || ""
      });
    }
    return entries;
  }

  function officialLink(agency, label) {
    const a = el("a", label, "button button--secondary trust-source-link");
    a.href = OFFICIAL[agency];
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }

  function updateGlobalStatus() {
    const notice = document.getElementById("data-notice");
    const footer = document.getElementById("footer-updated");
    if (!sourceStatus) return;
    const fda = sourceState("FDA");
    const usda = sourceState("USDA");
    if (notice) {
      if (allHealthy()) {
        notice.textContent = `Official sources current · FDA verified through ${formatRecordDate(fda.source.newestRecallDate)} · USDA FSIS through ${formatRecordDate(usda.source.newestRecallDate)}`;
        notice.classList.remove("coverage-warning");
        notice.classList.add("coverage-current");
      } else {
        notice.textContent = "Official source coverage needs attention";
        notice.classList.remove("coverage-current");
        notice.classList.add("coverage-warning");
      }
    }
    if (footer) {
      footer.textContent = `Official source status checked ${formatChecked(checkedDate())}. Newest verified records: FDA ${formatRecordDate(fda.source.newestRecallDate)}; USDA FSIS ${formatRecordDate(usda.source.newestRecallDate)}.`;
    }
  }

  function legacyValues(result) {
    const values = {};
    result.querySelectorAll(".trust-summary .details").forEach(dl => {
      const terms = [...dl.querySelectorAll("dt")];
      terms.forEach(dt => {
        const dd = dt.nextElementSibling;
        if (dd?.tagName === "DD") values[dt.textContent.trim()] = dd.textContent.trim();
      });
    });
    return values;
  }

  function isNoMatch(result) {
    const heading = (result.querySelector(".result-heading")?.textContent || "").toLowerCase();
    return heading.includes("no matching recall found") || heading.includes("no match found") || heading.includes("no current recall");
  }

  function addFact(list, label, value) {
    if (!value || value === "Not applicable") return;
    const row = el("div", null, "about-check-row");
    row.append(el("dt", label), el("dd", value));
    list.append(row);
  }

  function buildTechnicalDetails(result, legacy) {
    const technical = el("details", null, "about-check-technical");
    technical.append(el("summary", "Technical details"));
    const body = el("div", null, "about-check-technical-body");

    [sourceState("FDA"), sourceState("USDA")].forEach(state => {
      const section = el("section", null, "about-check-source");
      section.append(el("h4", state.agency === "FDA" ? "FDA" : "USDA FSIS"));
      const list = el("ul");
      surfaceEntries(state).forEach(surface => {
        const when = surface.checkedAt && Number.isFinite(Date.parse(surface.checkedAt))
          ? ` · ${formatChecked(new Date(surface.checkedAt))}` : "";
        list.append(el("li", `${surface.name}: ${surface.success ? "reached" : "unavailable"}${when}`));
      });
      list.append(el("li", `Newest verified record: ${formatRecordDate(state.source.newestRecallDate)}`));
      section.append(list, officialLink(state.agency, `Open ${state.agency} official recalls`));
      body.append(section);
    });

    const oldTransparency = result.querySelector(".transparency");
    const oldTechnical = oldTransparency?.querySelector(".technical p")?.textContent?.trim();
    if (oldTechnical) {
      const match = el("section", null, "about-check-source");
      match.append(el("h4", "Recall matching"), el("p", oldTechnical));
      body.append(match);
    }

    if (legacy["Barcode match"] && legacy["Barcode match"] !== "No" && legacy["Barcode match"] !== "Not applicable") {
      const match = el("section", null, "about-check-source");
      match.append(el("h4", "Identifier relationship"), el("p", legacy["Barcode match"]));
      body.append(match);
    }

    technical.append(body);
    return technical;
  }

  function buildAboutCheck(result) {
    const legacy = legacyValues(result);
    const noMatch = isNoMatch(result);
    const details = el("details", null, "about-check");
    details.append(el("summary", "About this check"));

    const body = el("div", null, "about-check-body");
    const facts = el("dl", null, "about-check-facts");
    addFact(facts, "Sources checked", "FDA food recalls and USDA FSIS recalls");
    addFact(facts, "Recall records last refreshed", legacy["Recall data updated"] || formatChecked(checkedDate()));
    addFact(facts, "FDA newest verified record", formatRecordDate(sourceState("FDA").source.newestRecallDate));
    addFact(facts, "USDA newest verified record", formatRecordDate(sourceState("USDA").source.newestRecallDate));
    addFact(facts, "Product information", legacy["Product information source"] || "Open Food Facts");

    if (!noMatch) {
      addFact(facts, "Official recall status", legacy["Official status"]);
      if (legacy["Package confirmation"] && legacy["Package confirmation"] !== "Not applicable") {
        addFact(facts, "Package verification", legacy["Package confirmation"]);
      }
    }

    body.append(facts);
    const sourceLine = el("p", allHealthy() ? "FDA and USDA source coverage was current and freshness-verified for this check." : "At least one official source needs attention, so this check may be incomplete.", allHealthy() ? "about-check-health" : "about-check-health about-check-health--warning");
    body.append(sourceLine, buildTechnicalDetails(result, legacy));
    details.append(body);
    return details;
  }

  function degradeNoMatch(result) {
    if (allHealthy()) return;
    const heading = result.querySelector(".result-heading");
    const label = result.querySelector(".result-label");
    const instruction = result.querySelector(".result-instruction");
    if (!heading || !/no matching recall found|no match found|no current recall/i.test(heading.textContent || "")) return;

    result.className = result.className.replace(/result--[^\s]+/g, "").trim() + " result--warning trust-result-degraded";
    const banner = result.querySelector(".result-banner");
    if (banner) banner.className = banner.className.replace(/result-banner--[^\s]+/g, "").trim() + " result-banner--warning";
    if (label) label.textContent = "UNABLE TO FULLY VERIFY — PARTIAL CHECK";
    heading.textContent = "No match found, but official coverage is incomplete";
    if (instruction) instruction.textContent = "We did not find this barcode in the recall records currently available to RecallCheck. At least one official source is unavailable, stale, or not freshness-verified, so this does not prove the product is not recalled.";

    if (!result.querySelector(".trust-degraded-actions")) {
      const actions = el("div", null, "result-actions trust-degraded-actions");
      [sourceState("FDA"), sourceState("USDA")].filter(state => !state.healthy).forEach(x => actions.append(officialLink(x.agency, `Verify with ${x.agency}`)));
      const summary = result.querySelector(".result-summary");
      if (summary) summary.append(actions);
    }
  }

  function productIdentityCaution(result) {
    const text = (result.textContent || "").toLowerCase();
    if (!(text.includes("product information") || text.includes("name unavailable") || text.includes("could not identify"))) return;
    if (result.querySelector("[data-identity-caution]")) return;
    const caution = el("p", "Product identity could not be confirmed from this barcode. Any recall result reflects barcode matching only; compare package details with the official notice.", "about-check-health about-check-health--warning");
    caution.dataset.identityCaution = "true";
    (result.querySelector(".result-summary") || result).prepend(caution);
  }

  function enhancePackageVerification(result) {
    const panel = result.querySelector(".package-verification");
    if (!panel || panel.querySelector(".package-verification-guidance")) return;
    const guide = el("aside", null, "package-verification-guidance");
    guide.append(
      el("strong", "Match the package, not only the barcode."),
      el("p", "Compare every identifier listed in the official recall—such as lot/date code, package size, or establishment number. A matching barcode alone may not mean every package is recalled.")
    );
    const actions = panel.querySelector(".verification-actions");
    panel.insertBefore(guide, actions || null);
  }

  function simplifyTrustUI(result) {
    if (result.dataset.trustSimplified === "true") return;
    const about = buildAboutCheck(result);
    result.querySelector(".trust-verification-card")?.remove();
    result.querySelector(".result-provenance")?.remove();
    result.querySelector(".trust-summary")?.remove();
    result.querySelector(".transparency")?.remove();
    const feedback = result.querySelector(".feedback");
    const repeat = result.querySelector(".result-actions");
    result.insertBefore(about, feedback || repeat || null);
    result.dataset.trustSimplified = "true";
  }

  function enhanceResult() {
    const panel = document.getElementById("result-panel");
    const result = panel?.querySelector(".result");
    if (!result || !sourceStatus) return;
    degradeNoMatch(result);
    productIdentityCaution(result);
    enhancePackageVerification(result);
    simplifyTrustUI(result);
  }

  function renderSourceFailure() {
    const notice = document.getElementById("data-notice");
    const footer = document.getElementById("footer-updated");
    const root = document.getElementById("data-status-content");
    if (notice) {
      notice.textContent = "Source verification unavailable";
      notice.classList.add("coverage-warning");
    }
    if (footer) footer.textContent = "RecallCheck could not verify official source freshness. Confirm results with FDA and USDA FSIS.";
    if (root) {
      root.replaceChildren(el("p", "RecallCheck could not verify source freshness right now. Results may be incomplete; use the official FDA and USDA FSIS listings for confirmation.", "field-error"));
    }
  }

  async function init() {
    try {
      const response = await fetch(STATUS_URL, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      sourceStatus = await response.json();
      updateGlobalStatus();
      enhanceResult();
      const resultPanel = document.getElementById("result-panel");
      if (resultPanel) new MutationObserver(enhanceResult).observe(resultPanel, { childList: true, subtree: true });
    } catch (_) {
      sourceStatus = null;
      renderSourceFailure();
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
