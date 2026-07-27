(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.RecallCheckDates = Object.freeze(api);
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const GS = "\u001d";
  const AI = {
    "01": { length: 14, field: "gtin" },
    "10": { max: 20, field: "lotNumber" },
    "11": { length: 6, field: "productionDate", type: "production" },
    "13": { length: 6, field: "packagingDate", type: "packaging" },
    "15": { length: 6, field: "bestBeforeDate", type: "best_before", allowDayZero: true },
    "16": { length: 6, field: "sellByDate", type: "sell_by" },
    "17": { length: 6, field: "expirationDate", type: "expiration", allowDayZero: true },
    "21": { max: 20, field: "serialNumber" }
  };
  const DATE_AIS = new Set(["11", "13", "15", "16", "17"]);
  const blank = () => ({ gtin: "", lotNumber: "", productionDate: "", packagingDate: "", bestBeforeDate: "", sellByDate: "", expirationDate: "", serialNumber: "", applicationIdentifiers: {}, parseWarnings: [] });
  const daysInMonth = (year, month) => new Date(year, month, 0).getDate();

  // Consumer-package rolling window: accept years from 10 years ago through 30
  // years ahead. If both centuries fit, return ambiguity rather than guessing.
  function parseGS1Date(value, options = {}) {
    const raw = String(value || "");
    if (!/^\d{6}$/.test(raw)) return { error: "GS1 date must contain six digits." };
    const yy=+raw.slice(0,2), month=+raw.slice(2,4), encodedDay=+raw.slice(4,6);
    if (month < 1 || month > 12) return { error: "GS1 date has an invalid month." };
    const today=options.today || new Date(), current=today.getFullYear();
    const candidates=[1900+yy,2000+yy,2100+yy].filter(y=>y>=current-10&&y<=current+30);
    if (candidates.length !== 1) { const plausible=[1900+yy,2000+yy,2100+yy].filter(y=>Math.abs(y-current)<=50); return { error: "GS1 year cannot be interpreted safely.", ambiguous: candidates.length > 1 || plausible.length > 1 }; }
    const year=candidates[0];
    if (encodedDay===0 && !options.allowDayZero) return { error: "Day 00 is not allowed for this date type." };
    const day=encodedDay===0 ? daysInMonth(year,month) : encodedDay;
    if (day<1 || day>daysInMonth(year,month)) return { error: "GS1 date is not a possible calendar date." };
    return { iso:`${year}-${String(month).padStart(2,"0")}-${String(day).padStart(2,"0")}`, dayZero:encodedDay===0, ambiguous:false };
  }
  function assign(result, ai, value, today) {
    const spec=AI[ai]; result.applicationIdentifiers[ai]=value;
    if (DATE_AIS.has(ai)) { const parsed=parseGS1Date(value,{today,allowDayZero:spec.allowDayZero}); if(parsed.error){result.parseWarnings.push(`${ai}: ${parsed.error}`);return;} result[spec.field]=parsed.iso; if(parsed.dayZero)result.parseWarnings.push(`${ai}: day 00 was conservatively interpreted as the last day of the month.`); }
    else result[spec.field]=value;
  }
  function parsePairs(pairs, today) { const result=blank(); for(const [ai,value] of pairs){if(!AI[ai]){result.parseWarnings.push(`Unsupported Application Identifier ${ai}.`);continue;}const spec=AI[ai];if((spec.length&&value.length!==spec.length)||(!spec.length&&(value.length<1||value.length>spec.max))){result.parseWarnings.push(`${ai}: malformed value length.`);continue;}assign(result,ai,value,today);}return result; }
  function parseDigitalLink(text,today) { try { const url=new URL(text); const segments=url.pathname.split("/").filter(Boolean).map(decodeURIComponent), pairs=[]; for(let i=0;i+1<segments.length;i+=2)if(/^\d{2}$/.test(segments[i]))pairs.push([segments[i],segments[i+1]]); for(const [key,value] of url.searchParams)if(/^\d{2}$/.test(key))pairs.push([key,value]); return parsePairs(pairs,today); } catch(_e){return null;} }
  function parseGS1(text, options={}) {
    const raw=String(text??"").trim(), digital=/^https?:\/\//i.test(raw)?parseDigitalLink(raw,options.today):null;
    if(digital)return digital;
    if(!raw)return blank();
    const parenthesized=[...raw.matchAll(/\((\d{2})\)([^()]*)/g)];
    if(parenthesized.length)return parsePairs(parenthesized.map(m=>[m[1],m[2].replace(new RegExp(GS,"g"),"")]),options.today);
    let data=raw.replace(/^\]?[dQq][12]/,"").replace(/^\]C1/,""), pos=0; const pairs=[], warnings=[];
    while(pos<data.length){if(data[pos]===GS){pos++;continue;}const ai=data.slice(pos,pos+2),spec=AI[ai];if(!spec){warnings.push(`Unsupported or malformed Application Identifier near position ${pos}.`);break;}pos+=2;let value;if(spec.length){value=data.slice(pos,pos+spec.length);pos+=spec.length;}else{const end=data.indexOf(GS,pos);if(end>=0){value=data.slice(pos,end);pos=end+1;}else{ // Without FNC1, stop at the next recognized fixed AI when it is unambiguous.
        let boundary=-1;for(let i=pos+1;i<data.length-1;i++){const next=AI[data.slice(i,i+2)];if(next?.length&&data.length-i>=2+next.length){boundary=i;break;}}value=data.slice(pos,boundary<0?data.length:boundary);pos=boundary<0?data.length:boundary;}
      }pairs.push([ai,value]);}
    const result=parsePairs(pairs,options.today);result.parseWarnings.unshift(...warnings);return result;
  }
  function normalizeScanResult(rawValue, format="", options={}) { const raw=String(rawValue??""), digits=raw.replace(/\D/g,""); const ordinary=/^(UPC_A|UPC_E|EAN_8|EAN_13)$/i.test(format)||/^\d{8,14}$/.test(raw); const parsed=ordinary?blank():parseGS1(raw,options); const gtin=ordinary?digits:parsed.gtin; return {rawValue:raw,format:String(format||"UNKNOWN"),gtin,applicationIdentifiers:parsed.applicationIdentifiers,containsEncodedDate:Boolean(parsed.productionDate||parsed.packagingDate||parsed.bestBeforeDate||parsed.sellByDate||parsed.expirationDate),parsed}; }
  function parseISODate(value){const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value||""));if(!m)return null;const y=+m[1],mo=+m[2],d=+m[3];if(mo<1||mo>12||d<1||d>daysInMonth(y,mo))return null;return {year:y,month:mo,day:d,iso:`${m[1]}-${m[2]}-${m[3]}`};}
  function compareDateOnly(value,today=new Date()){const d=parseISODate(value);if(!d)return null;const a=d.year*10000+d.month*100+d.day,b=today.getFullYear()*10000+(today.getMonth()+1)*100+today.getDate();return a<b?"past":a>b?"future":"today";}
  function evaluateDate({date,type="unknown",source="manual",today=new Date()}={}) { const relation=compareDateOnly(date,today);if(!relation)return {status:"date_unreadable",dateType:type,source,detectedDate:"",relation:"unknown",meaning:"The package date could not be read.",nextStep:"Enter the date manually or follow the manufacturer’s guidance.",uncertainty:"No date conclusion was made."}; if(type==="production"||type==="packaging")return {status:"production_or_packaging_date",dateType:type,source,detectedDate:date,relation,meaning:"Package date identified. This is not an expiration date.",nextStep:"Look for a separate best-by, use-by, or expiration date.",uncertainty:"A production or packaging date does not establish shelf life."}; const prefix=source==="encoded"?"encoded_":"printed_date_", kind=type==="best_before"?"best_before":type==="sell_by"?"sell_by":"expiration"; const status=source==="encoded"?`${prefix}${kind}_${relation}`:`${prefix}${relation}`; let meaning=relation==="past"?"Package date has passed":relation==="today"?"Package date is today":"Package date has not passed";let nextStep="Follow the manufacturer’s instructions and inspect the package. When in doubt, do not use the product.",uncertainty="A date check is separate from recall status and is not a safety guarantee.";if(type==="best_before"){meaning=relation==="past"?"Best-quality date has passed":"Best-quality date has not passed";nextStep="Check storage history, packaging integrity, appearance, texture, and odor. Follow manufacturer guidance when available.";uncertainty="Best By dates generally describe expected quality rather than proving that food is unsafe.";}else if(type==="sell_by"){meaning=relation==="past"?"Sell-by date has passed":"Sell-by date has not passed";uncertainty="A sell-by date guides store inventory and does not by itself determine safety.";}else if(type==="use_by")meaning=relation==="past"?"Use-by date has passed":relation==="today"?"Use-by date is today":"Use-by date has not passed";else if(type==="expiration")meaning=relation==="past"?"Expiration date has passed":relation==="today"?"Expiration date is today":"Expiration date has not passed";return {status,dateType:type,source,detectedDate:date,relation,meaning,nextStep,uncertainty}; }
  function combinedSummary(recallStatus,dateResult){const current=["confirmed_current_recall","current_recall_details_required","current_recall_manual_review"].includes(recallStatus);if(current)return "Do not use this product until you review the official recall notice.";if(recallStatus==="recall_data_unavailable")return "The package date check was completed, but the recall check could not be completed.";if(dateResult?.relation==="past"&&["expiration","use_by"].includes(dateResult.dateType))return "No matching current recall was found, but the package’s use-by or expiration date has passed.";if(dateResult?.relation==="past"&&dateResult.dateType==="best_before")return "No matching current recall was found. The best-quality date has passed, which does not by itself mean the food is unsafe.";if(["future","today"].includes(dateResult?.relation))return "No matching current recall was found, and the entered package date has not passed.";return "Recall status and package-date status are shown separately.";}
  return {AI,parseGS1Date,parseGS1,normalizeScanResult,parseISODate,compareDateOnly,evaluateDate,combinedSummary};
});
