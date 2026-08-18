(() => {
  "use strict";

  const STATUS_URL = "data/source-status.json";
  const OFFICIAL = {
    FDA: "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts",
    USDA: "https://www.fsis.usda.gov/recalls"
  };
  const OFFICIAL_LABELS = {
    FDA: "Open FDA official recalls",
    USDA: "Open USDA official recalls"
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
    const healthy = source.success !== false && (raw === "current" || raw === "healthy" || source.current === true);
    const failed = source.success === false || raw === "failed" || raw === "unavailable";
    return {
      agency,
      source,
      healthy,
      failed,
      label: healthy ? "Current" : failed ? "Unavailable" : "Needs attention"
    };
  }

  function allHealthy() {
    return sourceState("FDA").healthy && sourceState("USDA").healthy;
  }

  function checkedDate() {
    const raw = sourceStatus?.checkedAt || sourceStatus?.generatedAt;
    const parsed = Date.parse(raw || "");
    return Number.isFinite(parsed) ? new Date(parsed) : null;
  }

  function relativeChecked(date) {
    if (!date) return "Verification time unavailable";
    const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
    if (minutes < 1) return "Verified just now";
    if (minutes < 60) return `Verified ${minutes} min ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `Verified ${hours} hr${hours === 1 ? "" : "s"} ago`;
    return `Verified ${date.toLocaleString()}`;
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
    if (!notice || !sourceStatus) return;
    const checked = checkedDate();
    if (allHealthy()) {
      notice.textContent = `Official sources current · ${relativeChecked(checked)}`;
      notice.classList.remove("coverage-warning");
      notice.classList.add("coverage-current");
    } else {
      notice.textContent = "Official source coverage needs attention";
      notice.classList.remove("coverage-current");
      notice.classList.add("coverage-warning");
    }
  }

  function buildVerificationCard() {
    const card = el("section", null, "trust-verification-card");
    card.setAttribute("aria-label", "Source verification for this result");
    const head = el("div", null, "trust-verification-head");
    head.append(el("h3", "Sources checked for this result"), el("p", relativeChecked(checkedDate()), "trust-verified-time"));
    card.append(head);

    const grid = el("div", null, "trust-source-grid");
    [sourceState("FDA"), sourceState("USDA")].forEach(state => {
      const item = el("div", null, `trust-source trust-source--${state.healthy ? "current" : state.failed ? "failed" : "warning"}`);
      const top = el("div", null, "trust-source-title");
      top.append(el("strong", state.agency === "FDA" ? "FDA food recalls" : "USDA FSIS recalls"), el("span", state.label, "trust-source-badge"));
      item.append(top);
      const newest = state.source.newestRecallDate || state.source.latestRecallDate;
      if (newest) item.append(el("p", `Newest record in this source: ${new Date(`${newest}T00:00:00Z`).toLocaleDateString()}`));
      if (!state.healthy) item.append(el("p", "RecallCheck will not treat a no-match as a complete verification while this source needs attention.", "trust-source-warning"));
      item.append(officialLink(state.agency, OFFICIAL_LABELS[state.agency]));
      grid.append(item);
    });
    card.append(grid);
    return card;
  }

  function buildProvenance() {
    const details = el("details", null, "result-provenance");
    details.append(el("summary", "Which official sources were checked?"));
    const body = el("div", null, "result-provenance-body");
    [sourceState("FDA"), sourceState("USDA")].forEach(state => {
      const section = el("section");
      section.append(el("h4", state.agency === "FDA" ? "FDA" : "USDA FSIS"));
      const list = el("ul");
      surfaceEntries(state).forEach(surface => {
        const checked = surface.checkedAt && Number.isFinite(Date.parse(surface.checkedAt)) ? ` · checked ${new Date(surface.checkedAt).toLocaleString()}` : "";
        list.append(el("li", `${surface.name}: ${surface.success ? "reached" : "unavailable"}${checked}`));
      });
      section.append(list);
      body.append(section);
    });
    details.append(body);
    return details;
  }

  function degradeNoMatch(result) {
    if (allHealthy()) return;
    const heading = result.querySelector(".result-heading");
    const label = result.querySelector(".result-label");
    const instruction = result.querySelector(".result-instruction");
    if (!heading || !/no matching recall found/i.test(heading.textContent || "")) return;

    result.className = result.className.replace(/result--[^\s]+/g, "").trim() + " result--warning trust-result-degraded";
    const banner = result.querySelector(".result-banner");
    if (banner) banner.className = banner.className.replace(/result-banner--[^\s]+/g, "").trim() + " result-banner--warning";
    label.textContent = "UNABLE TO FULLY VERIFY";
    heading.textContent = "No match found, but official coverage is incomplete";
    instruction.textContent = "We did not find this barcode in the recall records currently available to RecallCheck. At least one official source needs attention, so this is not a complete no-match result.";

    if (!result.querySelector(".trust-degraded-actions")) {
      const actions = el("div", null, "result-actions trust-degraded-actions");
      [sourceState("FDA"), sourceState("USDA")].filter(state => !state.healthy).forEach(state => actions.append(officialLink(state.agency, `Verify with ${state.agency}`)));
      const summary = result.querySelector(".result-summary");
      if (summary) summary.append(actions);
    }
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

  function enhanceResult() {
    const panel = document.getElementById("result-panel");
    const result = panel?.querySelector(".result");
    if (!result || !sourceStatus) return;
    degradeNoMatch(result);
    enhancePackageVerification(result);
    if (!result.querySelector(".trust-verification-card")) {
      const trustSummary = result.querySelector(".trust-summary");
      result.insertBefore(buildVerificationCard(), trustSummary || null);
    }
    if (!result.querySelector(".result-provenance")) {
      const transparency = result.querySelector(".transparency");
      result.insertBefore(buildProvenance(), transparency || null);
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
      if (resultPanel) new MutationObserver(enhanceResult).observe(resultPanel, { childList: true });
    } catch (_) {
      const notice = document.getElementById("data-notice");
      if (notice) {
        notice.textContent = "Source verification unavailable";
        notice.classList.add("coverage-warning");
      }
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
