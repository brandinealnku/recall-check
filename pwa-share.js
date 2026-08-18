(() => {
  "use strict";

  const APP_URL = "https://recallcheck.itsbadlabs.com/";
  let deferredInstallPrompt = null;

  const $ = id => document.getElementById(id);
  const isStandalone = () => window.matchMedia?.("(display-mode: standalone)")?.matches || window.navigator.standalone === true;
  const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent || "");

  function setInstalledState() {
    document.documentElement.classList.toggle("rc-installed", isStandalone());
  }

  function installSheet() {
    let sheet = $("rc-install-sheet");
    if (sheet) return sheet;
    sheet = document.createElement("div");
    sheet.id = "rc-install-sheet";
    sheet.className = "rc-install-sheet";
    sheet.hidden = true;
    sheet.setAttribute("role", "dialog");
    sheet.setAttribute("aria-modal", "true");
    sheet.setAttribute("aria-labelledby", "rc-install-title");
    sheet.innerHTML = `
      <section class="rc-install-panel">
        <h2 id="rc-install-title">Add RecallCheck to your phone</h2>
        <p>RecallCheck can open from your Home Screen like an app.</p>
        <ol class="rc-install-steps">
          <li>Tap the <strong>Share</strong> button in Safari.</li>
          <li>Choose <strong>Add to Home Screen</strong>.</li>
          <li>Tap <strong>Add</strong>.</li>
        </ol>
        <p class="rc-install-note">Apple requires these final taps before a website can be added to your Home Screen.</p>
        <div class="actions"><button type="button" class="primary" id="rc-install-share">Open Share menu</button><button type="button" class="secondary" id="rc-install-close">Done</button></div>
      </section>`;
    document.body.append(sheet);
    $("rc-install-close").addEventListener("click", () => { sheet.hidden = true; });
    $("rc-install-share").addEventListener("click", async () => {
      try {
        if (navigator.share) await navigator.share({ title: "RecallCheck", text: "Add RecallCheck to your Home Screen for quick food recall checks.", url: APP_URL });
      } catch (_) {}
    });
    sheet.addEventListener("click", event => { if (event.target === sheet) sheet.hidden = true; });
    return sheet;
  }

  async function requestInstall() {
    if (isStandalone()) return;
    if (deferredInstallPrompt) {
      deferredInstallPrompt.prompt();
      try { await deferredInstallPrompt.userChoice; } catch (_) {}
      deferredInstallPrompt = null;
      setInstalledState();
      return;
    }
    const sheet = installSheet();
    sheet.hidden = false;
    $("rc-install-close")?.focus();
  }

  async function shareRecallCheck() {
    const payload = {
      title: "RecallCheck — Is this food recalled?",
      text: "Check FDA and USDA food recalls with RecallCheck.",
      url: APP_URL
    };
    try {
      if (navigator.share) {
        await navigator.share(payload);
        return;
      }
    } catch (error) {
      if (error?.name === "AbortError") return;
    }
    try {
      await navigator.clipboard.writeText(APP_URL);
      const status = $("rc-share-status");
      if (status) status.textContent = "RecallCheck link copied.";
    } catch (_) {
      window.prompt("Copy this RecallCheck link:", APP_URL);
    }
  }

  function addUtilityActions() {
    const assurance = document.querySelector(".hero-assurance");
    if (!assurance || $("rc-utility-actions")) return;
    const wrap = document.createElement("div");
    wrap.id = "rc-utility-actions";
    wrap.className = "rc-utility-actions";

    const install = document.createElement("button");
    install.type = "button";
    install.className = "button button--secondary rc-install-button";
    install.textContent = isIOS() ? "Add to Home Screen" : "Install RecallCheck";
    install.addEventListener("click", requestInstall);

    const share = document.createElement("button");
    share.type = "button";
    share.className = "button button--secondary";
    share.textContent = "Share RecallCheck";
    share.addEventListener("click", shareRecallCheck);

    wrap.append(install, share);
    assurance.insertAdjacentElement("afterend", wrap);
    const status = document.createElement("p");
    status.id = "rc-share-status";
    status.className = "rc-share-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    wrap.insertAdjacentElement("afterend", status);
    setInstalledState();
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator) || location.protocol !== "https:") return;
    navigator.serviceWorker.register("service-worker.js", { scope: "./" }).catch(() => {});
  }

  window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault();
    deferredInstallPrompt = event;
  });
  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    setInstalledState();
  });

  function init() {
    addUtilityActions();
    registerServiceWorker();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
