(() => {
  "use strict";

  const VERSION = "2.2.0-beta";
  const $ = id => document.getElementById(id);

  function setVersion() {
    document.documentElement.dataset.recallcheckVersion = VERSION;
    const meta = document.querySelector('meta[name="version"]');
    if (meta) meta.setAttribute("content", VERSION);
    document.querySelectorAll("footer .copyright span").forEach(span => {
      if (/^Version\s/i.test(span.textContent || "")) span.textContent = `Version ${VERSION}`;
    });
  }

  function polishPrimaryTask() {
    const searchTitle = $("v2-search-title");
    if (searchTitle) searchTitle.textContent = "Search instead";

    const searchIntro = document.querySelector(".v2-search-intro");
    if (searchIntro) searchIntro.textContent = "No barcode handy? Search by product or brand.";

    const searchHelp = $("v2-search-help");
    if (searchHelp) searchHelp.textContent = "For the most precise check, scan or enter the barcode on the package.";

    const searchSubmit = document.querySelector("#v2-search-form button[type='submit']");
    if (searchSubmit) searchSubmit.textContent = "Search";

    const manual = $("manual-button");
    if (manual) manual.textContent = "Or enter the barcode number";

    const footerBrand = document.querySelector(".footer-brand span");
    if (footerBrand) footerBrand.textContent = "An ITSBAD Labs product";
  }

  function removeTestingSignals() {
    document.querySelectorAll(".v2-eyebrow").forEach(node => node.hidden = true);
    const demo = document.querySelector("details.demo");
    if (demo) demo.setAttribute("aria-hidden", "true");
  }

  function addCheckAnotherAction() {
    const results = $("results");
    const productSummary = $("product-summary");
    if (!results || !productSummary || $("rc-check-another")) return;

    const button = document.createElement("button");
    button.id = "rc-check-another";
    button.className = "secondary rc-check-another";
    button.type = "button";
    button.textContent = "Check another product";
    button.addEventListener("click", () => {
      const hero = document.querySelector(".hero");
      hero?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
      window.setTimeout(() => $("scan-button")?.focus({ preventScroll: true }), 250);
    });
    productSummary.before(button);
  }

  function syncResultMode() {
    const results = $("results");
    if (!results) return;
    document.body.classList.toggle("rc-has-results", !results.hidden);
  }

  function watchResults() {
    const results = $("results");
    if (!results) return;
    syncResultMode();
    const observer = new MutationObserver(syncResultMode);
    observer.observe(results, { attributes: true, attributeFilter: ["hidden"] });
  }

  function init() {
    setVersion();
    polishPrimaryTask();
    removeTestingSignals();
    addCheckAnotherAction();
    watchResults();

    // V2 search is deferred but should already exist; one bounded retry covers slow devices.
    window.setTimeout(() => {
      polishPrimaryTask();
      removeTestingSignals();
    }, 500);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
