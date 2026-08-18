(() => {
  "use strict";

  const RECALLCHECK_URL = "https://recallcheck.itsbadlabs.com/";

  function loadV2SearchFix() {
    if (document.querySelector('script[data-recallcheck-v2-search-fix]')) return;
    const fix = document.createElement("script");
    fix.src = "v2-search-fix.js?v=2.0.1-beta";
    fix.defer = true;
    fix.dataset.recallcheckV2SearchFix = "true";
    document.body.appendChild(fix);
  }

  function loadV2Assets() {
    if (!document.querySelector('link[data-recallcheck-v2]')) {
      const stylesheet = document.createElement("link");
      stylesheet.rel = "stylesheet";
      stylesheet.href = "v2.css?v=2.0.0-beta";
      stylesheet.dataset.recallcheckV2 = "true";
      document.head.appendChild(stylesheet);
    }
    if (!document.querySelector('script[data-recallcheck-v2]')) {
      const script = document.createElement("script");
      script.src = "v2.js?v=2.0.0-beta";
      script.defer = true;
      script.dataset.recallcheckV2 = "true";
      script.addEventListener("load", loadV2SearchFix, { once: true });
      document.body.appendChild(script);
    } else loadV2SearchFix();
  }

  function isLinkedInBrowser() {
    const ua = navigator.userAgent || "";
    const referrer = document.referrer || "";
    return /LinkedInApp|LinkedIn/i.test(ua) || /linkedin\.com/i.test(referrer);
  }

  function needsBrowserFallback() {
    return isLinkedInBrowser() || !window.isSecureContext;
  }

  function ensureFallbackDialog() {
    let dialog = document.getElementById("browser-fallback-dialog");
    if (dialog) return dialog;

    dialog = document.createElement("dialog");
    dialog.id = "browser-fallback-dialog";
    dialog.setAttribute("aria-labelledby", "browser-fallback-title");
    dialog.innerHTML = `
      <div class="dialog-head">
        <div>
          <p class="privacy-note">Camera scanning isn’t available here</p>
          <h2 id="browser-fallback-title">Open RecallCheck in Safari or Chrome</h2>
        </div>
        <button id="browser-fallback-close" class="icon-button" type="button" aria-label="Close">×</button>
      </div>
      <p class="scanner-instruction">LinkedIn’s in-app browser can block camera access. You can still check a product without the camera.</p>
      <div class="browser-fallback-tip"><strong>Best option:</strong> copy the RecallCheck link, open Safari or Chrome yourself, and paste it into the address bar.</div>
      <p id="browser-fallback-copy-status" class="scanner-help" role="status" aria-live="polite"></p>
      <div class="actions">
        <button id="copy-recallcheck-link" class="primary" type="button">Copy RecallCheck link</button>
        <button id="browser-fallback-manual" class="secondary" type="button">Enter barcode instead</button>
      </div>
      <details class="browser-fallback-details">
        <summary>How to open it directly</summary>
        <ol><li>Copy the RecallCheck link.</li><li>Open Safari or Chrome.</li><li>Paste the link into the address bar.</li></ol>
      </details>`;
    document.body.appendChild(dialog);

    const close = () => {
      if (dialog.open) dialog.close();
      document.getElementById("scan-button")?.focus();
    };

    dialog.querySelector("#browser-fallback-close")?.addEventListener("click", close);
    dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });

    dialog.querySelector("#browser-fallback-manual")?.addEventListener("click", () => {
      close();
      document.getElementById("manual-button")?.click();
    });

    dialog.querySelector("#copy-recallcheck-link")?.addEventListener("click", async () => {
      const status = dialog.querySelector("#browser-fallback-copy-status");
      let copied = false;
      try {
        if (navigator.clipboard?.writeText && window.isSecureContext) {
          await navigator.clipboard.writeText(RECALLCHECK_URL);
          copied = true;
        }
      } catch (_) {}

      if (!copied) {
        const input = document.createElement("textarea");
        input.value = RECALLCHECK_URL;
        input.setAttribute("readonly", "");
        input.style.position = "fixed";
        input.style.opacity = "0";
        document.body.appendChild(input);
        input.select();
        try { copied = document.execCommand("copy"); } catch (_) {}
        input.remove();
      }

      if (status) status.textContent = copied
        ? "Link copied. Open Safari or Chrome and paste it into the address bar."
        : "Copy the browser address, then paste it into Safari or Chrome.";
    });

    return dialog;
  }

  function cleanLegacyFallback() {
    const scanner = document.getElementById("scanner-dialog");
    if (!scanner) return;
    scanner.querySelectorAll(".scanner-help").forEach(node => {
      if (/Opening from LinkedIn\?/i.test(node.textContent || "")) node.remove();
    });
    scanner.querySelectorAll('a[href="https://recallcheck.itsbadlabs.com/"]').forEach(node => {
      if (/Open secure RecallCheck/i.test(node.textContent || "")) node.remove();
    });
  }

  function showFallback() {
    const scanner = document.getElementById("scanner-dialog");
    if (scanner?.open) scanner.close();
    const dialog = ensureFallbackDialog();
    if (!dialog.open) dialog.showModal();
    dialog.querySelector("#copy-recallcheck-link")?.focus();
  }

  function installGuard() {
    loadV2Assets();
    cleanLegacyFallback();
    const scanButton = document.getElementById("scan-button");
    if (!scanButton) return;

    scanButton.addEventListener("click", event => {
      if (!needsBrowserFallback()) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      showFallback();
    }, true);

    document.getElementById("correction-scan")?.addEventListener("click", event => {
      if (!needsBrowserFallback()) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      showFallback();
    }, true);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", installGuard, { once: true });
  else installGuard();
})();
