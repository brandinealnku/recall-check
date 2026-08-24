#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]; DEFAULT_OUT=ROOT/'.deploy'; SOURCE_DATA=ROOT/'data'/'recalls.json'
MAX_CHUNK_BYTES=8*1024*1024; WARN_ASSET_BYTES=18*1024*1024
LOADER_TAG='<script src="recall-data-loader.js?v=1.0.0"></script>'
EXCLUDE_TOP={'.git','.github','.deploy','scripts','tests','node_modules'}
LOADER_JS=r'''(() => {"use strict";const nativeFetch=window.fetch.bind(window),TARGET=/(?:^|\/)data\/recalls\.json(?:[?#]|$)/;let assembled=null;async function fetchJson(url,init){const r=await nativeFetch(url,{...(init||{}),cache:"no-store"});if(!r.ok)throw new Error(`Request failed (${r.status})`);return r.json()}async function loadRecallDataset(init){if(!assembled)assembled=(async()=>{const m=await fetchJson("data/recalls-manifest.json",init);if(!Array.isArray(m.chunks)||!m.chunks.length)throw new Error("Recall data manifest has no chunks");const parts=await Promise.all(m.chunks.map(x=>fetchJson(x.url,init))),recalls=[];for(const p of parts){if(!Array.isArray(p.recalls))throw new Error("Recall data chunk is malformed");recalls.push(...p.recalls)}if(recalls.length!==m.recordCount)throw new Error(`Recall data record count mismatch (${recalls.length} != ${m.recordCount})`);return {...m.dataset,recalls}})();return assembled}window.fetch=async function(input,init){const raw=typeof input==="string"?input:input?.url||"";let pathname=raw;try{pathname=new URL(raw,window.location.href).pathname}catch(_){}if(!TARGET.test(pathname))return nativeFetch(input,init);const data=await loadRecallDataset(init);return new Response(JSON.stringify(data),{status:200,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}})}})();'''
def compact_bytes(v): return json.dumps(v,ensure_ascii=False,separators=(',',':')).encode()
def copy_public_tree(out):
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    for item in ROOT.iterdir():
        if item.name in EXCLUDE_TOP: continue
        dest=out/item.name
        if item.is_dir(): shutil.copytree(item,dest,ignore=shutil.ignore_patterns('recalls.json' if item.name=='data' else '__never__'))
        else: shutil.copy2(item,dest)
def split_dataset(out):
    dataset=json.loads(SOURCE_DATA.read_text()); recalls=dataset.get('recalls')
    if not isinstance(recalls,list): raise SystemExit('data/recalls.json is missing a recalls array')
    data_dir=out/'data'; (data_dir/'recalls').mkdir(parents=True,exist_ok=True); chunks=[]; current=[]; current_size=len(compact_bytes({'recalls':[]}))
    def flush():
        nonlocal current,current_size
        if not current:return
        name=f"recalls/chunk-{len(chunks)+1:03d}.json"; raw=compact_bytes({'recalls':current})
        if len(raw)>MAX_CHUNK_BYTES: raise SystemExit(f'Generated chunk exceeds limit: {name}')
        (data_dir/name).write_bytes(raw); chunks.append({'url':f'data/{name}','records':len(current),'bytes':len(raw)}); current=[]; current_size=len(compact_bytes({'recalls':[]}))
    for record in recalls:
        size=len(compact_bytes(record))+1
        if current and current_size+size>MAX_CHUNK_BYTES: flush()
        current.append(record); current_size+=size
    flush(); metadata={k:v for k,v in dataset.items() if k!='recalls'}; manifest={'schemaVersion':1,'recordCount':len(recalls),'chunks':chunks,'dataset':metadata}
    (data_dir/'recalls-manifest.json').write_bytes(compact_bytes(manifest)); (out/'recall-data-loader.js').write_text(LOADER_JS); return manifest
def inject_loader(out):
    for p in out.rglob('*.html'):
        text=p.read_text()
        if LOADER_TAG not in text:
            if '</head>' not in text: raise SystemExit(f'Cannot inject loader into {p}')
            p.write_text(text.replace('</head>',f'  {LOADER_TAG}\n</head>',1))
def verify_assets(out,manifest):
    bad=[(p.relative_to(out),p.stat().st_size) for p in out.rglob('*') if p.is_file() and p.stat().st_size>=WARN_ASSET_BYTES]
    if bad: raise SystemExit('Production asset safety limit exceeded: '+', '.join(f'{n}={s/1024/1024:.1f} MiB' for n,s in bad))
    if (out/'data'/'recalls.json').exists(): raise SystemExit('Monolithic data/recalls.json must never be included in production assets')
    if sum(x['records'] for x in manifest['chunks'])!=manifest['recordCount']: raise SystemExit('Chunk manifest does not preserve every recall record')
    print(f"Production assets ready: {manifest['recordCount']} recalls across {len(manifest['chunks'])} chunks")
def build(out=DEFAULT_OUT): copy_public_tree(out); m=split_dataset(out); inject_loader(out); verify_assets(out,m)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--out',type=pathlib.Path,default=DEFAULT_OUT); a=p.parse_args(); build(a.out.resolve())
if __name__=='__main__': main()
