(() => {
  "use strict";

  const panel = document.getElementById("result-panel");
  if (!panel) return;

  const states = {
    recalled: {
      icon: "!",
      label: "RECALL FOUND",
      message: "This product matches a current recall.",
      next: "Do not eat or serve this product. Check the official recall notice for return, disposal, or other instructions."
    },
    verify: {
      icon: "!",
      label: "RECALL FOUND — CHECK YOUR PACKAGE",
      message: "This barcode matches a recall, but only certain packages may be affected.",
      next: "Before eating or serving it, compare your package’s lot number, date, size, or other details with the official recall notice."
    },
    warning: {
      icon: "?",
      label: "POSSIBLE RECALL MATCH",
      message: "We found a recall that may be related to this product, but we can’t confirm that your package is included.",
      next: "Check the official recall notice before eating or serving this product."
    },
    neutral: {
      icon: "i",
      label: "NO CURRENT RECALL MATCH FOUND",
      message: "We didn’t find this barcode in the current FDA or USDA recall records we checked.",
      next: "This does not guarantee the product is safe. If something seems wrong with the product, don’t use it and check the official FDA or USDA sources."
    },
    historical: {
      icon: "↺",
      label: "OLDER RECALL FOUND",
      message: "This barcode appears in an older recall that is now listed as closed or terminated.",
      next: "If you may have an older package, compare its details with the original recall notice."
    },
    failure: {
      icon: "×",
      label: "WE COULDN’T COMPLETE THE CHECK",
      message: "We couldn’t check all of the FDA or USDA recall data right now.",
      next: "Try again, or use the official FDA and USDA links below to check directly."
    }
  };

  function classify(result) {
    const heading = (result.querySelector(".result-heading")?.textContent || "").toLowerCase();
    if (result.classList.contains("result--critical")) {
      return heading.includes("this product is recalled") || heading.includes("recall found") && !heading.includes("check your package") ? states.recalled : states.verify;
    }
    if (result.classList.contains("result--warning") || result.classList.contains("result--warning-critical")) return states.warning;
    if (result.classList.contains("result--historical")) return states.historical;
    if (result.classList.contains("result--failure")) return states.failure;
    return states.neutral;
  }

  function polishProductAttribution() {
    document.querySelectorAll(".coverage-line").forEach(node => {
      const text = (node.textContent || "").trim();
      if (text === "Product information supplied by Open Food Facts and may be incomplete.") {
        node.textContent = "Product details come from Open Food Facts and may not always be complete or correct.";
      }
    });
  }

  function polishHomepage() {
    const lede = document.querySelector(".hero .lede");
    if (lede) lede.textContent = "Scan a food barcode to see whether it matches a current FDA or USDA recall.";
    const confirmationNote = document.getElementById("confirmation-note");
    if (confirmationNote) confirmationNote.textContent = "Product details come from Open Food Facts and may not always be complete or correct.";
  }

  function decorate(result) {
    if (!result || result.dataset.indicatorsApplied === "true") return;
    const state = classify(result);

    const indicator = document.createElement("div");
    indicator.className = "result-status-indicator";
    indicator.setAttribute("role", "status");
    indicator.setAttribute("aria-label", `${state.label}. ${state.message}`);

    const icon = document.createElement("span");
    icon.className = "result-status-indicator__icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = state.icon;

    const copy = document.createElement("div");
    copy.className = "result-status-indicator__copy";

    const label = document.createElement("strong");
    label.className = "result-status-indicator__label";
    label.textContent = state.label;

    const message = document.createElement("span");
    message.className = "result-status-indicator__message";
    message.textContent = state.message;

    copy.append(label, message);
    indicator.append(icon, copy);

    const next = document.createElement("aside");
    next.className = "result-next-step";
    next.setAttribute("aria-label", "What to do next");
    const eyebrow = document.createElement("strong");
    eyebrow.className = "result-next-step__eyebrow";
    eyebrow.textContent = "What to do next";
    const text = document.createElement("p");
    text.textContent = state.next;
    next.append(eyebrow, text);

    const banner = result.querySelector(".result-banner");
    if (banner) banner.before(indicator);
    else result.prepend(indicator);

    const summary = result.querySelector(".result-summary");
    if (summary) summary.after(next);
    else result.append(next);

    const heading = result.querySelector(".result-heading");
    if (heading) heading.textContent = state.label.charAt(0) + state.label.slice(1).toLowerCase();

    result.dataset.indicatorsApplied = "true";
  }

  function scan() {
    polishHomepage();
    polishProductAttribution();
    panel.querySelectorAll(".result").forEach(decorate);
  }

  const observer = new MutationObserver(scan);
  observer.observe(document.body, { childList: true, subtree: true });
  scan();
})();
