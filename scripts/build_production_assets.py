#!/usr/bin/env python3
"""Build deploy-only RecallCheck assets that stay below Cloudflare Workers limits.

The source repository keeps the canonical data/recalls.json for ingestion/tests. The
production build excludes that monolith, splits the recall records into bounded JSON
chunks, writes a lightweight manifest, and injects a compatibility loader before any
other page scripts. Existing consumer code may continue fetching data/recalls.json;
the loader reconstructs the exact dataset in memory from the deploy-safe chunks.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / ".deploy"
SOURCE_DATA = ROOT / "data" / "recalls.json"
MAX_CHUNK_BYTES = 8 * 1024 * 1024
WARN_ASSET_BYTES = 18 * 1024 * 1024
LOADER_TAG = '<script src="recall-data-loader.js?v=1.0.0"></script>'
EXCLUDE_TOP = {".git", ".github", ".deploy", "scripts", "tests", "node_modules"}

LOADER_JS = r'''(() => {
  "use strict";
  const nativeFetch = window.fetch.bind(window);
  const TARGET = /(?:^|\/)data\/recalls\.json(?:[?#]|$)/;
  let assembled = null;

  async function fetchJson(url, init) {
    const response = await nativeFetch(url, { ...(init || {}), cache: "no-store" });
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    return response.json();
  }

  async function loadRecallDataset(init) {
    if (!assembled) assembled = (async () => {
      const manifest = await fetchJson("data/recalls-manifest.json", init);
      if (!Array.isArray(manifest.chunks) || !manifest.chunks.length) throw new Error("Recall data manifest has no chunks");
      const parts = await Promise.all(manifest.chunks.map(item => fetchJson(item.url, init)));
      const recalls = [];
      for (const part of parts) {
        if (!Array.isArray(part.recalls)) throw new Error("Recall data chunk is malformed");
        recalls.push(...part.recalls);
      }
      if (recalls.length !== manifest.recordCount) throw new Error(`Recall data record count mismatch (${recalls.length} != ${manifest.recordCount})`);
      return { ...manifest.dataset, recalls };
    })();
    return assembled;
  }

  window.fetch = async function(input, init) {
    const raw = typeof input === "string" ? input : input?.url || "";
    let pathname = raw;
    try { pathname = new URL(raw, window.location.href).pathname; } catch (_) {}
    if (!TARGET.test(pathname)) return nativeFetch(input, init);
    const data = await loadRecallDataset(init);
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
    });
  };
})();
'''


def compact_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def copy_public_tree(out: pathlib.Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for item in ROOT.iterdir():
        if item.name in EXCLUDE_TOP:
            continue
        destination = out / item.name
        if item.is_dir():
            shutil.copytree(item, destination, ignore=shutil.ignore_patterns("recalls.json" if item.name == "data" else "__never__"))
        else:
            shutil.copy2(item, destination)


def split_dataset(out: pathlib.Path) -> dict:
    dataset = json.loads(SOURCE_DATA.read_text(encoding="utf-8"))
    recalls = dataset.get("recalls")
    if not isinstance(recalls, list):
        raise SystemExit("data/recalls.json is missing a recalls array")

    data_dir = out / "data"
    chunk_dir = data_dir / "recalls"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    current = []
    current_size = len(compact_bytes({"recalls": []}))

    def flush() -> None:
        nonlocal current, current_size
        if not current:
            return
        index = len(chunks) + 1
        name = f"recalls/chunk-{index:03d}.json"
        payload = {"recalls": current}
        raw = compact_bytes(payload)
        if len(raw) > MAX_CHUNK_BYTES:
            raise SystemExit(f"Generated chunk exceeds {MAX_CHUNK_BYTES} bytes: {name}")
        (data_dir / name).write_bytes(raw)
        chunks.append({"url": f"data/{name}", "records": len(current), "bytes": len(raw)})
        current = []
        current_size = len(compact_bytes({"recalls": []}))

    for record in recalls:
        record_size = len(compact_bytes(record)) + 1
        if current and current_size + record_size > MAX_CHUNK_BYTES:
            flush()
        current.append(record)
        current_size += record_size
    flush()

    metadata = {key: value for key, value in dataset.items() if key != "recalls"}
    manifest = {
        "schemaVersion": 1,
        "recordCount": len(recalls),
        "chunks": chunks,
        "dataset": metadata,
    }
    manifest_raw = compact_bytes(manifest)
    (data_dir / "recalls-manifest.json").write_bytes(manifest_raw)
    (out / "recall-data-loader.js").write_text(LOADER_JS, encoding="utf-8")
    return manifest


def inject_loader(out: pathlib.Path) -> None:
    for path in out.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if LOADER_TAG in text:
            continue
        marker = "</head>"
        if marker not in text:
            raise SystemExit(f"Cannot inject recall loader into {path.relative_to(out)}")
        path.write_text(text.replace(marker, f"  {LOADER_TAG}\n{marker}", 1), encoding="utf-8")


def verify_assets(out: pathlib.Path, manifest: dict) -> None:
    oversized = []
    for path in out.rglob("*"):
        if path.is_file() and path.stat().st_size >= WARN_ASSET_BYTES:
            oversized.append((path.relative_to(out), path.stat().st_size))
    if oversized:
        details = ", ".join(f"{name}={size / 1024 / 1024:.1f} MiB" for name, size in oversized)
        raise SystemExit(f"Production asset safety limit exceeded ({WARN_ASSET_BYTES / 1024 / 1024:.0f} MiB): {details}")
    if (out / "data" / "recalls.json").exists():
        raise SystemExit("Monolithic data/recalls.json must never be included in production assets")
    if sum(item["records"] for item in manifest["chunks"]) != manifest["recordCount"]:
        raise SystemExit("Chunk manifest does not preserve every recall record")
    print(f"Production assets ready: {manifest['recordCount']} recalls across {len(manifest['chunks'])} chunks; largest asset safely below {WARN_ASSET_BYTES // 1024 // 1024} MiB.")


def build(out: pathlib.Path = DEFAULT_OUT) -> None:
    copy_public_tree(out)
    manifest = split_dataset(out)
    inject_loader(out)
    verify_assets(out, manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.out.resolve())


if __name__ == "__main__":
    main()
