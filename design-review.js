(() => {
 "use strict";
 const states=[
  ["confirmed-current","critical","Current recall","This product is connected to a current recall","Do not eat or serve this product until you review the official recall instructions."],
  ["details-required","critical","Current recall","This barcode is associated with a current recall","Do not eat or serve the product until you confirm whether your package is included.","Check whether your package is included"],
  ["package-included","critical","Current recall","Your package appears to be included in the recall","Do not eat or serve this product. Follow the official recall instructions."],
  ["package-no-match","critical","Current recall","This barcode is associated with a current recall","The package information entered does not match. This is not a safety guarantee.","Package code does not match the listed recall"],
  ["package-unknown","critical","Current recall","This barcode is associated with a current recall","Do not assume the product is unaffected.","We cannot determine whether your package is included"],
  ["unknown-status","warning-critical","Official recall match","This barcode appears in an official recall record","RecallCheck could not confirm whether the recall is still active."],
  ["historical-exact","historical","Historical recall","This barcode appears in an older recall record","Your current package is not being identified as part of an active recall."],
  ["historical-similar","historical","Similar historical recall","Your barcode does not match this official record","This is not evidence that your package is recalled."],
  ["no-match","neutral-result","No current match found","No matching current recall was found","This is not a safety guarantee."],
  ["product-not-found","neutral-result","Product identity","Product name not found","We still checked the barcode against official recall records."],
  ["partial-fda","warning","Partial recall check","Only FDA recall data could be checked","USDA was unavailable. A complete no-match conclusion cannot be made."],
  ["partial-usda","warning","Partial recall check","Only USDA recall data could be checked","FDA was unavailable. A complete no-match conclusion cannot be made."],
  ["source-failure","failure","Check not completed","FDA and USDA recall records could not be checked","Do not rely on this page to determine whether the product is recalled."],
  ["invalid-barcode","neutral-result","Inline form error","Check the barcode number","Enter the 8, 12, 13, or 14 digits printed below the barcode."],
  ["current-detail","critical","Current recall detail","Fictional current recall product","Do not eat or serve this product. Review the official instructions."],
  ["historical-detail","historical","Historical recall detail","Fictional older recall product","The official record is closed or terminated."]
 ];
 const root=document.getElementById("fixtures");
 states.forEach(([id,tone,label,heading,copy,packageHeading])=>{const article=document.createElement("article");article.id=id;article.className=`result result--${tone}`;const banner=document.createElement("header");banner.className=`result-banner result-banner--${tone}`;const wrap=document.createElement("div"),l=document.createElement("p"),h=document.createElement("h2");l.className="result-label";l.textContent=label;h.className="result-heading";h.textContent=heading;wrap.append(l,h);banner.append(wrap);const summary=document.createElement("section");summary.className="result-summary";const p=document.createElement("p");p.className="result-instruction";p.textContent=copy;summary.append(p);article.append(banner,summary);if(packageHeading){const panel=document.createElement("section");panel.className="package-verification package-verification--warning";const ph=document.createElement("h3");ph.textContent=packageHeading;panel.append(ph);article.append(panel);}root.append(article);});
})();
