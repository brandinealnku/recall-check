(() => {
  "use strict";

  const VERSION = "2.1.1-beta";
  const MISMATCH_KEY = "recallcheck.productMismatches.v1";
  const MAX_MISMATCHES = 25;

  const $ = id => document.getElementById(id);

  function storageAvailable() {
    try {
      const key = "__rc_mismatch_test__";
      localStorage.setItem(key, "1");
      localStorage.removeItem(key);
      return true;
    } catch (_) {
      return false;
    }
  }

  function readMismatches() {
    if (!storageAvailable()) return [];
    try {
      const parsed = JSON.parse(localStorage.getItem(MISMATCH_KEY) || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }

  function productSnapshot() {
    const summary = $("product-summary");
    const card = summary?.querySelector(".product");
    if (!card) return null;
    const heading = card.querySelector("h3")?.textContent?.trim() || "";
    const paragraphs = [...card.querySelectorAll("p")].map(node => node.textContent?.trim() || "");
    const valueFor = label => paragraphs.find(text => text.toLowerCase().startsWith(label.toLowerCase()))?.split(":").slice(1).join(":").trim() || "";
    return {
      product: heading,
      brand: valueFor("Brand"),
      packageSize: valueFor("Package size"),
      barcode: valueFor("Barcode")
    };
  }

  function recordMismatch(snapshot) {
    if (!snapshot || !storageAvailable()) return;
    const history = readMismatches();
    history.unshift({
      ...snapshot,
      recordedAt: new Date().toISOString(),
      source: "not_my_product"
    });
    try {
      localStorage.setItem(MISMATCH_KEY, JSON.stringify(history.slice(0, MAX_MISMATCHES)));
    } catch (_) {}
  }

  function moveToSearch(snapshot) {
    $("results")?.setAttribute("hidden", "");
    const search = $("v2-search");
    const input = $("v2-search-input");
    if (!search || !input) {
      $("manual-button")?.click();
      $("barcode-input")?.focus();
      return;
    }

    const bestTerm = snapshot?.brand && snapshot.brand !== "Unavailable"
      ? snapshot.brand
      : snapshot?.product && snapshot.product !== "Name unavailable"
        ? snapshot.product
        : "";
    input.value = bestTerm;
    search.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    window.setTimeout(() => {
      input.focus({ preventScroll: true });
      input.select?.();
    }, 220);
  }

  function autoContinueProductConfirmation() {
    const confirmation = $("product-confirmation");
    if (!confirmation || confirmation.hidden) return;
    const confirm = $("confirm-product");
    if (!confirm || confirm.disabled) return;

    // V2.1.1 treats product identification as useful context, not a blocking
    // confirmation step. The user can correct a mismatch from the result card.
    confirmation.hidden = true;
    confirm.click();
  }

  function installConfirmationObserver() {
    const confirmation = $("product-confirmation");
    if (!confirmation) return;
    const observer = new MutationObserver(() => autoContinueProductConfirmation());
    observer.observe(confirmation, { attributes: true, attributeFilter: ["hidden"] });
    autoContinueProductConfirmation();
  }

  function installMismatchHandler() {
    document.addEventListener("click", event => {
      const button = event.target?.closest?.("button");
      if (!button || button.textContent?.trim() !== "Not my product") return;

      event.preventDefault();
      event.stopImmediatePropagation();
      const snapshot = productSnapshot();
      recordMismatch(snapshot);
      moveToSearch(snapshot);
    }, true);
  }

  function markVersion() {
    document.documentElement.dataset.recallcheckVersion = VERSION;
  }

  function init() {
    installConfirmationObserver();
    installMismatchHandler();
    markVersion();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  window.RecallCheckV211 = Object.freeze({ VERSION, readMismatches });
})();
