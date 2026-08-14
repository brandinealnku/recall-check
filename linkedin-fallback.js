(() => {
  "use strict";

  const RECALLCHECK_URL = "https://recallcheck.itsbadlabs.com/";

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
          <p class="privacy-note">Barcode scanning needs a direct browser session.</p>
          <h2 id="browser-fallback-title">Open RecallCheck directly</h2>
        </div>
        <button id="browser-fallback-close" class="icon-button" type="button" aria-label="Close">×</button>
      </div>
      <p class="scanner-instruction">LinkedIn can limit camera access, even after choosing “Open in Safari” or “Open in Chrome.”</p>
      <div class="camera-status" role="status">
        <strong>To scan with your camera:</strong><br>
        1. Copy the RecallCheck link below.<br>
        2. Open Safari or Chrome yourself.<br>
        3. Paste the link into the address bar.
      </div>
      <p class="scanner-help"><strong>${RECALLCHECK_URL}</strong></p>
      <p id="browser-fallback-copy-status" class="scanner-help" role="status" aria-live="polite"></p>
      <div class="actions">
        <button id="copy-recallcheck-link" class="primary" type="button">Copy RecallCheck link</button>
        <button id="browser-fallback-manual" class="secondary" type="button">Enter barcode manually</button>
        <button id="browser-fallback-cancel" class="text-button" type="button">Cancel</button>
      </div>`;
    document.body.appendChild(dialog);

    const close = () => {
      if (dialog.open) dialog.close();
      document.getElementById("scan-button")?.focus();
    };

    dialog.querySelector("#browser-fallback-close")?.addEventListener("click", close);
    dialog.querySelector("#browser-fallback-cancel")?.addEventListener("click", close);
    dialog.addEventListener("cancel", event => {
      event.preventDefault();
      close();
    });

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

      if (status) {
        status.textContent = copied
          ? "Link copied. Now open Safari or Chrome and paste it into the address bar."
          : "Press and hold the URL above to copy it, then paste it into Safari or Chrome.";
      }
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

    if (!window.isSecureContext) {
      const status = document.getElementById("scanner-status");
      if (status && /HTTPS or localhost/i.test(status.textContent || "")) {
        status.textContent = "Camera scanning isn't available in this browser session. Open RecallCheck directly in Safari or Chrome, or enter the barcode manually.";
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installGuard, { once: true });
  } else {
    installGuard();
  }
})();
