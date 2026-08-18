(() => {
  "use strict";
  const VERSION = "3.0.0-beta";
  const $ = id => document.getElementById(id);

  function sentenceCase(value){const t=String(value||"").trim();return t?t.charAt(0).toUpperCase()+t.slice(1):""}
  function shortenOfficialTitle(title){
    const raw=String(title||"").replace(/\s+/g," ").trim(); if(!raw) return "Food recall";
    const patterns=[/(?:recalls?|recalling)\s+(.+?)\s+due\s+to\s+/i,/(?:public health alert|alert)\s+for\s+(.+?)\s+(?:due\s+to|because|after)\s+/i,/(?:recall)\s+of\s+(.+?)\s+due\s+to\s+/i];
    for(const p of patterns){const m=raw.match(p);if(m?.[1]) return sentenceCase(m[1].replace(/^various\s+/i,""))}
    const cut=raw.split(/\s+due\s+to\s+|\s+because\s+/i)[0]; return cut.length>82?`${cut.slice(0,79).trim()}…`:cut;
  }
  function hazardFromTitle(title,fallback){
    const raw=String(title||"");const m=raw.match(/due\s+to\s+(?:possible\s+)?(.+?)(?:\.|$)/i);
    if(m?.[1]){let h=m[1].replace(/\bcontamination\b/i,"contamination").trim();if(!/^possible\b/i.test(h)&&/possible/i.test(raw.slice(Math.max(0,m.index-14),m.index+m[0].length)))h=`Possible ${h}`;return sentenceCase(h)}
    const clean=String(fallback||"").trim();if(!clean||/^product contamination$/i.test(clean))return "See recall details for the reason";return sentenceCase(clean);
  }

  function enhanceRecallCard(card){
    if(!card||card.dataset.v3Enhanced==="true") return;
    const heading=card.querySelector("h3");if(!heading)return;
    const official=heading.textContent.trim();
    const reason=[...card.querySelectorAll("p")].find(p=>!p.classList.contains("recall-meta")&&!p.classList.contains("category")&&!p.classList.contains("recall-card__status")&&!p.classList.contains("recall-card__hazard"));
    const meta=card.querySelector(".recall-meta");const category=card.querySelector(".category");const existingLink=card.querySelector("a.secondary");
    const short=shortenOfficialTitle(official);heading.textContent="";
    const link=document.createElement("a");link.textContent=short;link.href=existingLink?.href||"recalls.html";heading.append(link);
    const status=document.createElement("p");status.className="recall-card__status";status.textContent="Current recall";card.prepend(status);
    const hazard=document.createElement("p");hazard.className="recall-card__hazard";hazard.textContent=hazardFromTitle(official,reason?.textContent);heading.after(hazard);reason?.remove();
    if(meta) meta.textContent=meta.textContent.replace(/\s*·\s*(Active Recall|Public Health Alert|Ongoing|Active|Current)\s*$/i,"").replace(/August (\d{1,2}), (\d{4})/,"Aug $1, $2");
    if(category){const labels=category.textContent.split("·").map(x=>x.trim()).filter(Boolean).slice(0,3);category.replaceChildren(...labels.map(label=>{const chip=document.createElement("span");chip.textContent=label;return chip}))}
    if(existingLink){existingLink.textContent="View recall details"}
    if(official&&official!==short){const d=document.createElement("details");d.className="recall-card__official-title";const s=document.createElement("summary");s.textContent="Official notice title";const p=document.createElement("p");p.textContent=official;d.append(s,p);card.append(d)}
    card.dataset.v3Enhanced="true";
  }
  function enhanceRecallCards(root=document){root.querySelectorAll?.(".recall-card").forEach(enhanceRecallCard)}
  function watchRecallCards(){enhanceRecallCards();document.querySelectorAll(".recall-grid").forEach(root=>new MutationObserver(()=>enhanceRecallCards(root)).observe(root,{childList:true}))}

  function polishSearch(){
    const title=$("v2-search-title");if(title)title.textContent="Search by product or brand";
    const intro=document.querySelector(".v2-search-intro");if(intro)intro.textContent="Don’t have the package? Search the recall records by product or brand.";
    const help=$("v2-search-help");if(help)help.textContent="For the most precise check, scan or enter the barcode on the package.";
    const submit=document.querySelector("#v2-search-form button[type='submit']");if(submit)submit.textContent="Search";
    document.querySelectorAll(".v2-eyebrow").forEach(n=>n.hidden=true);
  }
  function addCheckAnother(){
    const results=$("results"),summary=$("product-summary");if(!results||!summary||$("rc-check-another"))return;
    const b=document.createElement("button");b.id="rc-check-another";b.type="button";b.className="secondary rc-check-another";b.textContent="Check another product";
    b.addEventListener("click",()=>{document.querySelector(".hero")?.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});setTimeout(()=>$("scan-button")?.focus({preventScroll:true}),220)});summary.before(b);
  }
  function setVersion(){
    document.documentElement.dataset.recallcheckVersion=VERSION;const meta=document.querySelector('meta[name="version"]');if(meta)meta.content=VERSION;
    document.querySelectorAll("[data-version]").forEach(n=>n.textContent=VERSION);document.querySelectorAll(".copyright span").forEach(span=>{if(/^Version\s/i.test(span.textContent||""))span.textContent=`Version ${VERSION}`});
    const year=$("copyright-year");if(year)year.textContent=String(new Date().getFullYear());
  }
  function removeTestUI(){document.querySelector("details.demo")?.setAttribute("hidden","");$("session-history")?.setAttribute("hidden","")}
  function syncResultMode(){const r=$("results");if(r)document.body.classList.toggle("rc-has-results",!r.hidden)}
  function watchResults(){const r=$("results");if(!r)return;syncResultMode();new MutationObserver(syncResultMode).observe(r,{attributes:true,attributeFilter:["hidden"]})}
  function init(){setVersion();polishSearch();addCheckAnother();removeTestUI();watchRecallCards();watchResults();setTimeout(polishSearch,450)}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});else init();
  window.RecallCheckV3=Object.freeze({VERSION,shortenOfficialTitle,hazardFromTitle});
})();
