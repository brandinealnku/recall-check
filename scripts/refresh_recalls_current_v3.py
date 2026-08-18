#!/usr/bin/env python3
"""RecallCheck source pipeline v0.6 — augment FDA XML with the live FDA recall table.

The annual FDA XML remains useful for broad/history coverage, but it can lag the
consumer-facing FDA recalls table. This wrapper adds currently visible FDA Food &
Beverages rows from the official public table to the normalized dataset, deduplicates
them against XML records, and only marks FDA current when the merged dataset reaches
the authoritative newest public food-recall date.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import urllib.parse
from html.parser import HTMLParser
from typing import Any

import refresh_recalls_current_v2 as v2

current = v2.current
legacy = current.legacy
WORKFLOW_VERSION = "0.6.0"


class FdaPublicTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_row = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[dict[str, Any]] = []
        self.rows: list[list[dict[str, Any]]] = []
        self.cell_href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name == "tr":
            self.in_row = True
            self.row = []
        elif self.in_row and name in {"td", "th"}:
            self.in_cell = True
            self.cell_parts = []
            self.cell_href = ""
        elif self.in_cell and name == "a" and not self.cell_href:
            self.cell_href = dict(attrs).get("href") or ""

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            text = legacy.clean_text(data)
            if text:
                self.cell_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if self.in_row and self.in_cell and name in {"td", "th"}:
            self.row.append({"text": legacy.clean_text(" ".join(self.cell_parts)), "href": self.cell_href})
            self.cell_parts = []
            self.cell_href = ""
            self.in_cell = False
        elif self.in_row and name == "tr":
            if self.row:
                self.rows.append(self.row)
            self.row = []
            self.in_row = False
            self.in_cell = False


def normalized_header(value: str) -> str:
    return " ".join(legacy.clean_text(value).lower().replace("(s)", "s").split())


def iso_date(value: str) -> str:
    text = legacy.clean_text(value)
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return legacy.parse_date(text)


def parse_public_food_rows(html: str) -> list[dict[str, str]]:
    parser = FdaPublicTableParser()
    parser.feed(str(html))
    headers: dict[str, int] | None = None
    out: list[dict[str, str]] = []

    for row in parser.rows:
        texts = [normalized_header(cell["text"]) for cell in row]
        if "date" in texts and any("product type" in text for text in texts):
            headers = {name: i for i, name in enumerate(texts)}
            continue
        if not headers:
            continue

        def cell_for(*names: str) -> dict[str, str]:
            for wanted in names:
                idx = next((i for name, i in headers.items() if wanted in name), None)
                if idx is not None and idx < len(row):
                    return row[idx]
            return {"text": "", "href": ""}

        product_type = cell_for("product type")["text"]
        if "food & beverages" not in product_type.lower():
            continue

        date_cell = cell_for("date")
        product_cell = cell_for("product description")
        brand_cell = cell_for("brand name")
        reason_cell = cell_for("recall reason")
        company_cell = cell_for("company name")
        terminated_cell = cell_for("terminated recall")
        excerpt_cell = cell_for("excerpt")
        recall_date = iso_date(date_cell["text"])
        if not recall_date or not product_cell["text"]:
            continue

        href = product_cell.get("href") or brand_cell.get("href") or excerpt_cell.get("href") or ""
        if href.startswith("/"):
            href = urllib.parse.urljoin("https://www.fda.gov", href)
        if not href.startswith("https://www.fda.gov/"):
            href = current.FDA_RECALLS_PAGE

        out.append({
            "date": recall_date,
            "brand": brand_cell["text"],
            "product": product_cell["text"],
            "productType": product_type,
            "reason": reason_cell["text"] or "See official notice",
            "company": company_cell["text"] or "Unknown",
            "terminated": terminated_cell["text"],
            "excerpt": excerpt_cell["text"],
            "url": href,
        })
    return out


def normalize_public_row(row: dict[str, str]) -> dict[str, Any]:
    combined = " ".join([row.get("brand", ""), row.get("product", ""), row.get("reason", ""), row.get("excerpt", "")])
    extraction = legacy.extract_candidates(combined)
    terminated = bool(legacy.clean_text(row.get("terminated")))
    timeline = legacy.normalize_timeline(row["date"])
    stable = "|".join([row["date"], row.get("company", ""), row.get("brand", ""), row.get("product", "")])
    record_id = "FDA-PUBLIC-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]
    title = row.get("product") or f"{row.get('company', 'FDA')} food recall"
    identifiers = extraction["identifiers"]
    return {
        "id": record_id,
        "sourceRecordId": record_id.removeprefix("FDA-"),
        "agency": "FDA",
        "type": "recall",
        "status": "terminated" if terminated else "current",
        "lifecycle": legacy.normalize_lifecycle("terminated" if terminated else "active"),
        "timeline": timeline,
        "classification": "unknown",
        "title": title,
        "recallingFirm": row.get("company") or "Unknown",
        "productDescription": row.get("product") or title,
        "brandNames": legacy.unique(([row.get("brand")] if row.get("brand") else []) + extraction["brandNames"]),
        "productNames": legacy.split_names(row.get("product") or title),
        "upcs": [x for x in identifiers if len(x) in (8, 12, 13)],
        "gtins": [x for x in identifiers if len(x) == 14],
        "packageSizes": extraction["packageSizes"],
        "lotCodes": extraction["lotCodes"],
        "dateCodes": extraction["dateCodes"],
        "establishmentNumbers": [],
        "reason": row.get("reason") or "See official notice",
        "distribution": "See official notice",
        "recallDate": timeline["recallDate"],
        "officialUrl": row.get("url") or current.FDA_RECALLS_PAGE,
        "extraction": extraction["extraction"],
        "sourceRecord": {"source": "FDA public recalls table", **row},
        "searchText": legacy.clean_text(" ".join([row.get("company", ""), row.get("brand", ""), row.get("product", ""), row.get("reason", "")])).lower(),
    }


def semantic_key(record: dict[str, Any]) -> tuple[str, str, str]:
    date = legacy.parse_date(record.get("recallDate") or record.get("timeline", {}).get("recallDate"))
    firm = legacy.clean_text(record.get("recallingFirm")).lower()
    product = legacy.clean_text(record.get("productDescription") or record.get("title")).lower()
    return date, firm, " ".join(product.split())[:180]


def augment_fda(dataset: dict[str, Any], fetcher=current.fetch_text) -> dict[str, Any]:
    html, _headers = fetcher(current.FDA_RECALLS_PAGE, {"Accept": "text/html"})
    public_rows = parse_public_food_rows(str(html))
    if not public_rows:
        raise ValueError("FDA public recalls table contained no usable Food & Beverages rows")

    public_records = [normalize_public_row(row) for row in public_rows]
    existing = list(dataset.get("recalls") or [])
    keys = {semantic_key(item) for item in existing if item.get("agency") == "FDA"}
    added = 0
    for item in public_records:
        key = semantic_key(item)
        if key not in keys:
            existing.append(item)
            keys.add(key)
            added += 1

    existing.sort(key=lambda item: legacy.parse_date(item.get("recallDate") or item.get("timeline", {}).get("recallDate")) or "", reverse=True)
    dataset["recalls"] = existing

    health = dataset.setdefault("dataHealth", {})
    health["workflowVersion"] = WORKFLOW_VERSION
    sources = health.setdefault("sources", {})
    fda = sources.setdefault("FDA", {})
    fda_records = [item for item in existing if item.get("agency") == "FDA"]
    newest = max((legacy.parse_date(item.get("recallDate") or item.get("timeline", {}).get("recallDate")) for item in fda_records), default="")
    authoritative = max(row["date"] for row in public_rows)
    fda.update({
        "success": True,
        "recordCount": len(fda_records),
        "newestRecallDate": newest,
        "authoritativeNewestRecallDate": authoritative,
        "freshnessValidated": True,
        "freshnessValidatedAt": health.get("checkedAt") or dataset.get("generatedAt"),
        "freshnessLagDays": max(0, (dt.date.fromisoformat(authoritative) - dt.date.fromisoformat(newest)).days) if newest else None,
        "current": bool(newest and newest >= authoritative),
        "qualityStatus": "current" if newest and newest >= authoritative else "stale",
        "validationMethod": "annual-xml-plus-public-recall-table",
        "livePublicRowsSeen": len(public_rows),
        "livePublicRowsAdded": added,
    })
    warnings = health.setdefault("warnings", [])
    warnings[:] = [w for w in warnings if not str(w).startswith("FDA data may be incomplete:")]
    if not fda["current"]:
        warnings.append(f"FDA data may be incomplete: RecallCheck newest FDA record {newest or 'unknown'}; FDA public listing newest food recall {authoritative}")
    return dataset


_original_build = v2.build_dataset_with_quality


def build_dataset_live(existing, fda_fetcher=current.fetch_text, usda_fetcher=legacy.fetch_json, now=None):
    dataset = _original_build(existing, fda_fetcher, usda_fetcher, now)
    return augment_fda(dataset, fda_fetcher)


current.build_dataset = build_dataset_live


if __name__ == "__main__":
    current.main()
