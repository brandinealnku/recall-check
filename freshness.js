(() => {
  "use strict";

  const RECALL_URL = "data/recalls.json";
  const $ = selector => document.querySelector(selector);
  let latestData = null;
  let applying = false;

  function formatDate(value, includeTime = false) {
    const time = Date.parse(value || "");
    if (!Number.isFinite(time)) return "not available";
    return new Intl.DateTimeFormat("en-US", includeTime
      ? { year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }
      : { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }
    ).format(time);
  }

  function sourceSummary(agency, source) {
    if (!source) return `${agency}: status unavailable`;
    const newest = source.newestRecallDate
      ? `newest listed recall ${formatDate(source.newestRecallDate)}`
      : "newest recall date unavailable";
    if (source.success) {
      return `${agency}: checked successfully ${formatDate(source.checkedAt || source.retrievedAt, true)} · ${newest}`;
    }
    const lastGood = source.lastSuccessfulUpdate;
    return `${agency}: latest check failed · last successful retrieval ${formatDate(lastGood, true)} · ${newest}`;
  }

  function applyHomepageSummary(data) {
    if (applying) return;
    applying = true;
    const notice = document.getElementById("data-notice");
    const footer = document.getElementById("footer-updated");
    const sources = data?.dataHealth?.sources || {};
    const fda = sources.FDA;
    const usda = sources.USDA;
    const bothHealthy = Boolean(fda?.success && usda?.success);

    if (notice) {
      notice.textContent = bothHealthy
        ? "FDA + USDA checked successfully"
        : "Some official data needs attention";
    }
    if (footer) {
      footer.textContent = `Official sources last checked ${formatDate(data?.dataHealth?.checkedAt || data?.generatedAt, true)}.`;
    }

    const statusRoot = document.getElementById("data-status-content");
    if (statusRoot) {
      const existing = statusRoot.querySelector("[data-source-freshness]");
      if (existing) existing.remove();
      const wrap = document.createElement("div");
      wrap.dataset.sourceFreshness = "true";
      const heading = document.createElement("p");
      const strong = document.createElement("strong");
      strong.textContent = "Source freshness";
      heading.append(strong);
      wrap.append(heading);
      [sourceSummary("FDA", fda), sourceSummary("USDA FSIS", usda)].forEach(value => {
        const p = document.createElement("p");
        p.textContent = value;
        wrap.append(p);
      });
      statusRoot.prepend(wrap);
    }
    applying = false;
  }

  function setListingSummary(data) {
    const root = $("[data-freshness-summary]");
    if (!root) return;
    const sources = data?.dataHealth?.sources || {};
    root.replaceChildren();
    const checked = document.createElement("p");
    checked.textContent = `Official sources last checked ${formatDate(data?.dataHealth?.checkedAt || data?.generatedAt, true)}.`;
    root.append(checked);
    [sourceSummary("FDA", sources.FDA), sourceSummary("USDA FSIS", sources.USDA)].forEach(value => {
      const p = document.createElement("p");
      p.textContent = value;
      root.append(p);
    });
  }

  function watchForLegacyOverwrite() {
    const targets = [
      document.getElementById("data-notice"),
      document.getElementById("footer-updated"),
      document.getElementById("data-status-content")
    ].filter(Boolean);
    if (!targets.length || !latestData) return;
    const observer = new MutationObserver(() => {
      if (!applying && latestData) queueMicrotask(() => applyHomepageSummary(latestData));
    });
    targets.forEach(target => observer.observe(target, { childList: true, characterData: true, subtree: true }));
  }

  async function init() {
    try {
      const response = await fetch(RECALL_URL, { cache: "no-store" });
      if (!response.ok) return;
      latestData = await response.json();
      applyHomepageSummary(latestData);
      setListingSummary(latestData);
      watchForLegacyOverwrite();
      setTimeout(() => applyHomepageSummary(latestData), 250);
      setTimeout(() => applyHomepageSummary(latestData), 1000);
    } catch (_) {
      // Existing page-level unavailable states remain authoritative on fetch failure.
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
