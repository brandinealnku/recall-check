(() => {
  "use strict";

  const APP_URL = "https://recallcheck.itsbadlabs.com/";
  const SESSION_KEY = "recallcheck.completedChecks.v1";
  const DISMISS_KEY = "recallcheck.installDismissed.v1";
  let deferredInstallPrompt = null;
  let lastResultSignature = "";

  const $ = id => document.getElementById(id);
  const isStandalone = () => window.matchMedia?.("(display-mode: standalone)")?.matches || window.navigator.standalone === true;
  const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent || "");

  function setInstalledState() {
    document.documentElement.classList.toggle("rc-installed", isStandalone());
  }

  function completedChecks() {
    try { return Number(sessionStorage.getItem(SESSION_KEY) || "0") || 0; } catch (_) { return 0; }
  }

  function incrementCompletedChecks() {
    const next = completedChecks() + 1;
    try { sessionStorage.setItem(SESSION_KEY, String(next)); } catch (_) {}
    return next;
  }

  function installDismissed() {
    try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch (_) { return false; }
  }

  function dismissInstallPromotion() {
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch (_) {}
    $("rc-install-promotion")?.remove();
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
        <h2 id="rc-install-title">Add to Home Screen</h2>
        <ol class="rc-install-steps">
          <li>Tap <strong>Share</strong> in Safari.</li>
          <li>Tap <strong>Add to Home Screen</strong>.</li>
        </ol>
        <button type="button" class="primary" id="rc-install-close">Got it</button>
      </section>`;
    document.body.append(sheet);
    $("rc-install-close").addEventListener("click", () => { sheet.hidden = true; });
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
    if (isIOS()) {
      const sheet = installSheet();
      sheet.hidden = false;
      $("rc-install-close")?.focus();
    }
  }

  async function sharePayload(payload, fallbackUrl = APP_URL) {
    try {
      if (navigator.share) {
        await navigator.share(payload);
        return;
      }
    } catch (error) {
      if (error?.name === "AbortError") return;
    }
    try {
      await navigator.clipboard.writeText(fallbackUrl);
      const status = $("rc-share-status");
      if (status) status.textContent = "Link copied.";
    } catch (_) {
      window.prompt("Copy this link:", fallbackUrl);
    }
  }

  function shareRecallCheck() {
    return sharePayload({
      title: "RecallCheck — Is this food recalled?",
      text: "Check FDA and USDA food recalls with RecallCheck.",
      url: APP_URL
    });
  }

  function isPositiveRecall(result) {
    const heading = (result?.querySelector(".result-heading")?.textContent || "").toLowerCase();
    const label = (result?.querySelector(".result-label")?.textContent || "").toLowerCase();
    return /recalled|linked to a current recall|current recall/.test(`${heading} ${label}`) && !/no recall|no match|historical/.test(`${heading} ${label}`);
  }

  function officialRecallUrl(result) {
    const links = [...(result?.querySelectorAll("a[href]") || [])];
    const official = links.find(a => /fda\.gov|fsis\.usda\.gov/.test(a.href));
    return official?.href || APP_URL;
  }

  function addShareThisRecall(result) {
    if (!isPositiveRecall(result) || result.querySelector("[data-share-recall]")) return;
    const actions = result.querySelector(".result-actions") || result.querySelector(".result-summary") || result;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button button--secondary rc-share-recall";
    button.dataset.shareRecall = "true";
    button.textContent = "Share this recall";
    button.addEventListener("click", () => {
      const product = $("product-summary")?.querySelector("h3")?.textContent?.trim() || "a food product";
      const url = officialRecallUrl(result);
      sharePayload({
        title: `Food recall: ${product}`,
        text: `RecallCheck found a current recall related to ${product}. Review the official recall details before using the product.`,
        url
      }, url);
    });
    actions.append(button);
  }

  function addInstallPromotion(result) {
    if (isStandalone() || installDismissed() || $("rc-install-promotion")) return;
    const checks = completedChecks();
    if (checks < 2 && !isPositiveRecall(result)) return;

    const card = document.createElement("aside");
    card.id = "rc-install-promotion";
    card.className = "rc-install-promotion";
    card.innerHTML = `
      <div><strong>Keep RecallCheck handy</strong><p>Add it to your Home Screen for faster checks.</p></div>
      <div class="rc-install-promotion-actions"><button type="button" class="button button--secondary" data-install> Add to Home Screen </button><button type="button" class="text-button" data-dismiss>Not now</button></div>`;
    card.querySelector("[data-install]").addEventListener("click", requestInstall);
    card.querySelector("[data-dismiss]").addEventListener("click", dismissInstallPromotion);
    const results = $("results");
    results?.insertAdjacentElement("afterend", card);
  }

  function recordResultAndEnhance() {
    const result = $("result-panel")?.querySelector(".result");
    if (!result) return;
    const signature = `${result.querySelector(".result-heading")?.textContent || ""}|${result.querySelector(".coverage-line")?.textContent || ""}`;
    if (signature && signature !== lastResultSignature) {
      lastResultSignature = signature;
      incrementCompletedChecks();
    }
    addShareThisRecall(result);
    addInstallPromotion(result);
  }

  function addFooterShare() {
    if ($("rc-footer-share")) return;
    const nav = document.querySelector("footer nav");
    if (!nav) return;
    const button = document.createElement("button");
    button.id = "rc-footer-share";
    button.type = "button";
    button.className = "rc-footer-share";
    button.textContent = "Share RecallCheck";
    button.addEventListener("click", shareRecallCheck);
    nav.append(button);
    const status = document.createElement("span");
    status.id = "rc-share-status";
    status.className = "sr-only";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    nav.append(status);
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
    $("rc-install-promotion")?.remove();
    setInstalledState();
  });

  function init() {
    document.getElementById("install-prompt")?.setAttribute("hidden", "");
    addFooterShare();
    registerServiceWorker();
    setInstalledState();
    const panel = $("result-panel");
    if (panel) new MutationObserver(recordResultAndEnhance).observe(panel, { childList: true, subtree: true });
    recordResultAndEnhance();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
