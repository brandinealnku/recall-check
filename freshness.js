(() => {
  "use strict";

  const RECALL_URL = "data/recalls.json";
  const CLEAN_RECALLCHECK_URL = "https://recallcheck.itsbadlabs.com/";
  const FDA_RECALLS_URL = "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts";
  const $ = selector => document.querySelector(selector);
  let coverageData = null;

  function formatDate(value, includeTime = false) {
    const time = Date.parse(value || "");
    if (!Number.isFinite(time)) return "not available";
    return new Intl.DateTimeFormat("en-US", includeTime
      ? { year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }
      : { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }
    ).format(time);
  }

  function sourceIsCurrent(source) {
    return Boolean(source?.success && source?.current === true && source?.qualityStatus === "current");
  }

  function failedSurfaceNames(source) {
    const labels = {
      annualAnnouncements: "FDA recall announcements",
      publicAlerts: "FDA public recall alerts",
      enforcement: "FDA enforcement reports",
    };
    return Object.entries(source?.surfaces || {})
      .filter(([, status]) => status?.success !== true)
      .map(([name]) => labels[name] || name);
  }

  function sourceSummary(agency, source) {
    if (!source) return `${agency}: status unavailable`;
    const checked = formatDate(source.checkedAt || source.retrievedAt, true);
    const newest = source.newestRecallDate
      ? `newest RecallCheck record ${formatDate(source.newestRecallDate)}`
      : "newest RecallCheck record unavailable";

    if (!source.success) {
      const lastGood = source.lastSuccessfulUpdate;
      return `${agency}: latest official-source check failed · last successful retrieval ${formatDate(lastGood, true)} · ${newest}`;
    }

    if (source.qualityStatus === "degraded" || source.coverageComplete === false) {
      const failed = failedSurfaceNames(source);
      return `${agency}: coverage degraded · checked ${checked} · ${newest}${failed.length ? ` · unavailable: ${failed.join(", ")}` : ""}`;
    }

    if (source.qualityStatus === "stale") {
      return `${agency}: data may be incomplete · checked ${checked} · ${newest}`;
    }

    if (source.qualityStatus === "unverified") {
      return `${agency}: source reached successfully ${checked}, but coverage could not be verified · ${newest}`;
    }

    if (sourceIsCurrent(source)) {
      if (source.coverageMethod === "official-fda-multi-surface-union-v1") {
        return `${agency}: current across FDA announcement, public-alert, and enforcement sources · checked ${checked} · ${newest}`;
      }
      return `${agency}: current · checked successfully ${checked} · ${newest}`;
    }

    return `${agency}: source reached successfully ${checked} · coverage status unavailable · ${newest}`;
  }

  function applyHomepageSummary(data) {
    const notice = document.getElementById("data-notice");
    const footer = document.getElementById("footer-updated");
    const sources = data?.dataHealth?.sources || {};
    const fda = sources.FDA;
    const usda = sources.USDA;
    const bothCurrent = sourceIsCurrent(fda) && sourceIsCurrent(usda);

    if (notice) {
      notice.textContent = bothCurrent
        ? "FDA + USDA coverage current"
        : "Official-source coverage needs attention";
    }
    if (footer) {
      footer.textContent = `Official sources last checked ${formatDate(data?.dataHealth?.checkedAt || data?.generatedAt, true)}.`;
    }

    const statusRoot = document.getElementById("data-status-content");
    if (statusRoot) {
      statusRoot.querySelector("[data-source-freshness]")?.remove();
      const wrap = document.createElement("div");
      wrap.dataset.sourceFreshness = "true";
      const heading = document.createElement("p");
      const strong = document.createElement("strong");
      strong.textContent = "Official-source coverage";
      heading.append(strong);
      wrap.append(heading);
      [sourceSummary("FDA", fda), sourceSummary("USDA FSIS", usda)].forEach(value => {
        const p = document.createElement("p");
        p.textContent = value;
        wrap.append(p);
      });
      statusRoot.prepend(wrap);
    }
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

  function guardNoMatchWhenCoverageDegraded() {
    const panel = document.getElementById("result-panel");
    if (!panel || !coverageData) return;
    const fda = coverageData?.dataHealth?.sources?.FDA;
    if (sourceIsCurrent(fda)) return;
    const text = String(panel.textContent || "").toLowerCase();
    if (!text.includes("no current recall match found") && !text.includes("no matching current recall")) return;
    if (panel.querySelector("[data-coverage-caution]")) return;

    const warning = document.createElement("section");
    warning.className = "notice notice--warning";
    warning.dataset.coverageCaution = "true";
    warning.setAttribute("role", "status");
    const strong = document.createElement("strong");
    strong.textContent = "This is a partial recall check.";
    const body = document.createElement("p");
    body.textContent = "FDA coverage is currently incomplete, so this no-match result only reflects the official records RecallCheck could retrieve.";
    const link = document.createElement("a");
    link.href = FDA_RECALLS_URL;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Check current FDA recalls";
    warning.append(strong, body, link);
    panel.prepend(warning);
  }

  function watchResultCoverage() {
    const panel = document.getElementById("result-panel");
    const results = document.getElementById("results");
    if (!panel) return;
    const observer = new MutationObserver(() => guardNoMatchWhenCoverageDegraded());
    observer.observe(panel, { childList: true, subtree: true });
    if (results) new MutationObserver(() => guardNoMatchWhenCoverageDegraded()).observe(results, { attributes: true, attributeFilter: ["hidden"] });
  }

  function isLinkedInContext() {
    const params = new URLSearchParams(window.location.search);
    const userAgent = String(navigator.userAgent || "");
    return params.has("linkedin") || /LinkedInApp|LinkedIn/i.test(userAgent);
  }

  function cameraFallbackNeeded() {
    const isHttps = window.location.protocol === "https:";
    const cameraUnavailable = !window.isSecureContext || !navigator.mediaDevices?.getUserMedia;
    return isLinkedInContext() || (isHttps && cameraUnavailable);
  }

  function ensureLinkedInNotice() {
    if (!isLinkedInContext()) return null;
    let notice = document.getElementById("linkedin-browser-notice");
    if (notice) return notice;
    const actions = document.querySelector(".hero-actions");
    if (!actions) return null;

    notice = document.createElement("aside");
    notice.id = "linkedin-browser-notice";
    notice.className = "manual-card";
    notice.setAttribute("aria-labelledby", "linkedin-browser-title");
    const title = document.createElement("h2");
    title.id = "linkedin-browser-title";
    title.textContent = "For barcode scanning, open RecallCheck in your browser";
    const explanation = document.createElement("p");
    explanation.textContent = "LinkedIn opens links inside its own browser, which can prevent RecallCheck from using your camera.";
    const instructions = document.createElement("p");
    instructions.innerHTML = "On iPhone, tap <strong>•••</strong> in the top-right corner and choose <strong>Open in Safari</strong>. Then tap Scan barcode again.";
    const buttonRow = document.createElement("div");
    buttonRow.className = "actions";
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "secondary";
    copyButton.textContent = "Copy RecallCheck link";
    const copyStatus = document.createElement("span");
    copyStatus.setAttribute("role", "status");
    copyStatus.setAttribute("aria-live", "polite");
    copyButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(CLEAN_RECALLCHECK_URL);
        copyStatus.textContent = " Link copied.";
      } catch (_) {
        const input = document.createElement("input");
        input.value = CLEAN_RECALLCHECK_URL;
        input.setAttribute("readonly", "");
        input.style.position = "fixed";
        input.style.opacity = "0";
        document.body.append(input);
        input.select();
        try { document.execCommand("copy"); copyStatus.textContent = " Link copied."; }
        catch (_error) { copyStatus.textContent = ` Copy this link: ${CLEAN_RECALLCHECK_URL}`; }
        finally { input.remove(); }
      }
    });
    const manualButton = document.createElement("button");
    manualButton.type = "button";
    manualButton.className = "text-button";
    manualButton.textContent = "Enter barcode manually instead";
    manualButton.addEventListener("click", () => {
      const section = document.getElementById("manual-section");
      const toggle = document.getElementById("manual-button");
      if (!section) return;
      section.hidden = false;
      toggle?.setAttribute("aria-expanded", "true");
      document.getElementById("barcode-input")?.focus();
    });
    buttonRow.append(copyButton, manualButton, copyStatus);
    notice.append(title, explanation, instructions, buttonRow);
    actions.insertAdjacentElement("afterend", notice);
    return notice;
  }

  function showCameraFallback() {
    const dialog = document.getElementById("scanner-dialog");
    if (dialog?.open) dialog.close();
    if (isLinkedInContext()) {
      const notice = ensureLinkedInNotice();
      notice?.scrollIntoView({ behavior: "smooth", block: "center" });
      notice?.querySelector("button")?.focus();
      return;
    }
    const manual = document.getElementById("manual-section");
    const manualButton = document.getElementById("manual-button");
    const input = document.getElementById("barcode-input");
    if (!manual) return;
    manual.hidden = false;
    manualButton?.setAttribute("aria-expanded", "true");
    let notice = document.getElementById("camera-browser-notice");
    if (!notice) {
      notice = document.createElement("p");
      notice.id = "camera-browser-notice";
      notice.className = "field-error";
      notice.setAttribute("role", "status");
      document.getElementById("manual-title")?.insertAdjacentElement("afterend", notice);
    }
    notice.textContent = "Camera scanning isn’t available in this browser. Open RecallCheck in Safari or Chrome to scan, or enter the barcode number below.";
    input?.focus();
  }

  function installCameraFallback() {
    ensureLinkedInNotice();
    const scanButton = document.getElementById("scan-button");
    const correctionScan = document.getElementById("correction-scan");
    [scanButton, correctionScan].filter(Boolean).forEach(button => {
      button.addEventListener("click", event => {
        if (!cameraFallbackNeeded()) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        showCameraFallback();
      }, true);
    });
  }

  async function init() {
    installCameraFallback();
    watchResultCoverage();
    try {
      const response = await fetch(RECALL_URL, { cache: "no-store" });
      if (!response.ok) return;
      coverageData = await response.json();
      applyHomepageSummary(coverageData);
      setListingSummary(coverageData);
      guardNoMatchWhenCoverageDegraded();
      setTimeout(() => applyHomepageSummary(coverageData), 250);
      setTimeout(() => applyHomepageSummary(coverageData), 1000);
    } catch (_) {
      // Existing page-level unavailable states remain authoritative on fetch failure.
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
