(() => {
  "use strict";

  const replacements = new Map([
    ["Product information supplied by Open Food Facts and may be incomplete.", "Product details come from Open Food Facts and may not always be complete or correct."],
    ["Product information comes from Open Food Facts and may be incomplete.", "Product details come from Open Food Facts and may not always be complete or correct."],
    ["This product is recalled", "Recall found"],
    ["This barcode is linked to a current recall", "Recall found — check your package"],
    ["This barcode appears in an official recall record", "Possible recall match"],
    ["No matching recall found", "No current recall match found"],
    ["This barcode appears in an older recall record", "Older recall found"],
    ["FDA and USDA recall records could not be checked", "We couldn’t complete the check"]
  ]);

  function polishText(root = document) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
      const text = node.nodeValue?.trim();
      if (!text) return;
      if (replacements.has(text)) node.nodeValue = node.nodeValue.replace(text, replacements.get(text));
    });
  }

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE || node.nodeType === Node.DOCUMENT_FRAGMENT_NODE) polishText(node);
      });
    }
  });

  polishText(document);
  observer.observe(document.body, { childList: true, subtree: true });
})();
