(() => {
  "use strict";
  const VERSION = "3.2.0-beta";
  const RESPONSIVE_CSS = "recallcheck-v3-responsive.css?v=3.2.0-beta";
  const $ = id => document.getElementById(id);

  function ensureResponsiveStyles(){
    if(document.querySelector('link[data-recallcheck-responsive]')) return;
    const link=document.createElement("link");
    link.rel="stylesheet";
    link.href=RESPONSIVE_CSS;
    link.dataset.recallcheckResponsive="true";
    document.head.append(link);
  }

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

  function formatDate(value){
    const time=Date.parse(value||"");
    return Number.isFinite(time)?new Intl.DateTimeFormat("en-US",{year:"numeric",month:"short",day:"numeric",timeZone:"UTC"}).format(time):"date unavailable";
  }
  function sourceName(agency){return agency==="USDA"?"USDA FSIS":agency}
  function sourceNeedsAttention(source){return Boolean(source&&(source.current===false||["stale","unverified"].includes(source.qualityStatus)||source.success===false))}
  function collectionContextNode(kind){
    const existing=document.querySelector(`[data-${kind}-summary]`);if(existing)return existing;
    const p=document.createElement("p");p.className="collection-context";p.dataset[`${kind}Summary`]="true";p.setAttribute("role","status");p.setAttribute("aria-live","polite");
    if(kind==="recent") document.querySelector(".recent-section .section-heading")?.insertAdjacentElement("afterend",p);
    else document.querySelector(".filters")?.insertAdjacentElement("beforebegin",p);
    return p;
  }
  async function setRecallCollectionContext(){
    if(!document.querySelector("[data-recent], [data-recall-list]"))return;
    try{
      const response=await fetch("data/recalls.json",{cache:"no-store"});if(!response.ok)return;
      const data=await response.json();
      const current=window.RecallDiscovery?.currentRecalls?.(data.recalls)||[];
      const newest=current[0];if(!newest)return;
      const date=newest.recallDate||newest.timeline?.recallDate;
      const sources=data?.dataHealth?.sources||{};
      const attention=Object.entries(sources).filter(([,source])=>sourceNeedsAttention(source));
      let text=`Newest displayed current record: ${sourceName(newest.agency)} · ${formatDate(date)}.`;
      if(attention.length){
        const details=attention.map(([agency,source])=>{
          if(source.qualityStatus==="stale"){
            const rc=source.newestRecallDate?`RecallCheck ${formatDate(source.newestRecallDate)}`:"RecallCheck date unavailable";
            const official=source.authoritativeNewestRecallDate?`official listing ${formatDate(source.authoritativeNewestRecallDate)}`:"official freshness not verified";
            return `${sourceName(agency)} data may be incomplete (${rc}; ${official})`;
          }
          if(source.success===false)return `${sourceName(agency)} source retrieval failed`;
          return `${sourceName(agency)} freshness is not independently verified`;
        });
        text+=` Source coverage note: ${details.join("; ")}.`;
      }
      ["recent","currentList"].forEach(kind=>{
        const selector=kind==="recent"?"[data-recent]":"[data-recall-list]";
        if(!document.querySelector(selector))return;
        const node=collectionContextNode(kind);if(!node)return;
        node.textContent=text;node.dataset.warning=String(attention.length>0);
      });
    }catch(_){/* Existing source-status UI remains authoritative. */}
  }

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
  function init(){ensureResponsiveStyles();setVersion();polishSearch();addCheckAnother();removeTestUI();watchRecallCards();watchResults();setRecallCollectionContext();setTimeout(polishSearch,450)}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});else init();
  window.RecallCheckV3=Object.freeze({VERSION,shortenOfficialTitle,hazardFromTitle});
})();
