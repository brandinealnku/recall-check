(() => {
  "use strict";

  const panel = document.getElementById("result-panel");
  if (!panel) return;

  const states = {
    recalled: {
      icon: "!",
      label: "RECALLED",
      message: "A current recall matches this product.",
      next: "Do not eat or serve this product. Open the official recall notice and follow the agency instructions."
    },
    verify: {
      icon: "!",
      label: "RECALL MATCH — VERIFY PACKAGE",
      message: "This barcode is linked to a recall, but package details still matter.",
      next: "Do not eat or serve the product until you confirm the lot, date, package size, or other identifying details in the official notice."
    },
    warning: {
      icon: "?",
      label: "VERIFY BEFORE USING",
      message: "RecallCheck found information that needs manual verification.",
      next: "Review the dated official recall notice before using the product."
    },
    neutral: {
      icon: "i",
      label: "NO MATCH FOUND",
      message: "No matching current recall was found in the official records checked.",
      next: "You can use the product identification and source details below to verify the result. No match is not a guarantee that the product is safe."
    },
    historical: {
      icon: "↺",
      label: "HISTORICAL RECALL",
      message: "This barcode appears in an older recall record.",
      next: "The listed recall is closed or terminated. Review the historical notice if you need to compare package details."
    },
    failure: {
      icon: "×",
      label: "CHECK UNAVAILABLE",
      message: "RecallCheck could not complete the official recall check.",
      next: "Do not rely on this result. Use the FDA or USDA links below to check the official sources directly."
    }
  };

  function classify(result) {
    const heading = (result.querySelector(".result-heading")?.textContent || "").toLowerCase();
    if (result.classList.contains("result--critical")) {
      return heading.includes("this product is recalled") ? states.recalled : states.verify;
    }
    if (result.classList.contains("result--warning") || result.classList.contains("result--warning-critical")) return states.warning;
    if (result.classList.contains("result--historical")) return states.historical;
    if (result.classList.contains("result--failure")) return states.failure;
    return states.neutral;
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

    result.dataset.indicatorsApplied = "true";
  }

  function scan() {
    panel.querySelectorAll(".result").forEach(decorate);
  }

  const observer = new MutationObserver(scan);
  observer.observe(panel, { childList: true, subtree: true });
  scan();
})();