(() => {
  "use strict";

  const RECALL_URL = "data/recalls.json";
  const $ = selector => document.querySelector(selector);

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
      statusRoot.querySelector("[data-source-freshness]")?.remove();
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

  function cameraFallbackNeeded() {
    const isHttps = window.location.protocol === "https:";
    const cameraUnavailable = !window.isSecureContext || !navigator.mediaDevices?.getUserMedia;
    return isHttps && cameraUnavailable;
  }

  function showCameraFallback() {
    const dialog = document.getElementById("scanner-dialog");
    if (dialog?.open) dialog.close();

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

    notice.textContent = "Camera scanning isn’t available inside this in-app browser. Open RecallCheck in Safari or Chrome to scan, or enter the barcode number below.";
    input?.focus();
  }

  function installCameraFallback() {
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
    try {
      const response = await fetch(RECALL_URL, { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      applyHomepageSummary(data);
      setListingSummary(data);

      // app.js also updates the homepage after its own data load. Re-apply the
      // source-specific wording a finite number of times instead of observing and
      // rewriting the same DOM nodes indefinitely.
      setTimeout(() => applyHomepageSummary(data), 250);
      setTimeout(() => applyHomepageSummary(data), 1000);
    } catch (_) {
      // Existing page-level unavailable states remain authoritative on fetch failure.
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
