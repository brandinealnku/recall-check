(() => {
  "use strict";

  const VERSION = "2.3.0-beta";

  function sentenceCase(value) {
    const text = String(value || "").trim();
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
  }

  function shortenOfficialTitle(title) {
    const raw = String(title || "").replace(/\s+/g, " ").trim();
    if (!raw) return "Food recall";

    const patterns = [
      /(?:recalls?|recalling)\s+(.+?)\s+due\s+to\s+/i,
      /(?:public health alert|alert)\s+for\s+(.+?)\s+(?:due\s+to|because|after)\s+/i,
      /(?:recall)\s+of\s+(.+?)\s+due\s+to\s+/i
    ];
    for (const pattern of patterns) {
      const match = raw.match(pattern);
      if (match?.[1]) return sentenceCase(match[1].replace(/^various\s+/i, ""));
    }

    const cut = raw.split(/\s+due\s+to\s+|\s+because\s+/i)[0];
    return cut.length > 86 ? `${cut.slice(0, 83).trim()}…` : cut;
  }

  function hazardFromTitle(title, fallback) {
    const raw = String(title || "");
    const match = raw.match(/due\s+to\s+(?:possible\s+)?(.+?)(?:\.|$)/i);
    if (match?.[1]) {
      let hazard = match[1].replace(/\bcontamination\b/i, "contamination").trim();
      if (!/^possible\b/i.test(hazard) && /possible/i.test(raw.slice(Math.max(0, match.index - 12), match.index + match[0].length))) hazard = `Possible ${hazard}`;
      return sentenceCase(hazard);
    }
    const clean = String(fallback || "").trim();
    if (!clean || /^product contamination$/i.test(clean)) return "See recall details for the reason";
    return sentenceCase(clean);
  }

  function enhanceCard(card) {
    if (!card || card.dataset.v23Enhanced === "true") return;
    const heading = card.querySelector("h3");
    if (!heading) return;

    const officialTitle = heading.textContent.trim();
    const existingReason = [...card.querySelectorAll("p")].find(p => !p.classList.contains("recall-meta") && !p.classList.contains("category"));
    const meta = card.querySelector(".recall-meta");
    const category = card.querySelector(".category");

    heading.textContent = shortenOfficialTitle(officialTitle);

    const status = document.createElement("p");
    status.className = "recall-card__status";
    status.textContent = "Current recall";
    card.prepend(status);

    const hazard = document.createElement("p");
    hazard.className = "recall-card__hazard";
    hazard.textContent = hazardFromTitle(officialTitle, existingReason?.textContent);
    heading.after(hazard);
    existingReason?.remove();

    if (meta) {
      meta.textContent = meta.textContent
        .replace(/\s*·\s*(Active Recall|Public Health Alert|Ongoing|Active|Current)\s*$/i, "")
        .replace(/August (\d{1,2}), (\d{4})/, "Aug $1, $2");
    }

    if (category) {
      const labels = category.textContent.split("·").map(x => x.trim()).filter(Boolean).slice(0, 3);
      category.replaceChildren(...labels.map(label => {
        const chip = document.createElement("span");
        chip.textContent = label;
        return chip;
      }));
    }

    if (officialTitle && officialTitle !== heading.textContent) {
      const details = document.createElement("details");
      details.className = "recall-card__official-title";
      const summary = document.createElement("summary");
      summary.textContent = "Official notice title";
      const p = document.createElement("p");
      p.textContent = officialTitle;
      details.append(summary, p);
      card.append(details);
    }

    card.dataset.v23Enhanced = "true";
  }

  function enhanceRecallCards(root = document) {
    root.querySelectorAll?.(".recall-card").forEach(enhanceCard);
  }

  function watchCards() {
    enhanceRecallCards();
    const roots = [...document.querySelectorAll(".recall-grid")];
    roots.forEach(root => {
      const observer = new MutationObserver(() => enhanceRecallCards(root));
      observer.observe(root, { childList: true });
    });
  }

  function setVersion() {
    const meta = document.querySelector('meta[name="version"]');
    if (meta) meta.content = VERSION;
    document.documentElement.dataset.recallcheckVersion = VERSION;
    document.querySelectorAll(".copyright span").forEach(span => {
      if (/^Version\s/i.test(span.textContent || "")) span.textContent = `Version ${VERSION}`;
    });
  }

  function init() {
    setVersion();
    watchCards();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
