from __future__ import annotations
import hashlib, json, math, os, shutil, subprocess
from pathlib import Path
from typing import Any
import requests

ROOT=Path(__file__).resolve().parents[2]
MANIFEST_PATH=ROOT/"media_vault"/"drive_manifest.json"
VAULT=ROOT/"storage"/"media_vault"; VAULT.mkdir(parents=True,exist_ok=True)
INDEX_PATH=VAULT/"index.json"

def load_manifest()->dict[str,Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.is_file() else {"items":[]}
def load_index()->dict[str,Any]:
    try:return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:return {"items":[]}
def _save(x): INDEX_PATH.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
def registered_sources(): return list(load_manifest().get("items",[]))

def _probe(p:Path):
    try:
        x=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration,size:stream=codec_type,codec_name,width,height","-of","json",str(p)],capture_output=True,text=True,timeout=30,check=True)
        return json.loads(x.stdout)
    except Exception:return {}

def _download_drive(fid:str,target:Path):
    urls=[f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t",f"https://drive.google.com/uc?export=download&id={fid}"]
    for url in urls:
        try:
            r=requests.get(url,stream=True,timeout=(20,240),allow_redirects=True,headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code>=400 or "text/html" in (r.headers.get("content-type") or "").lower(): continue
            tmp=target.with_suffix(".part"); total=0
            with tmp.open("wb") as w:
                for b in r.iter_content(1024*1024):
                    if b: total+=len(b); w.write(b)
                    if total>800_000_000: raise RuntimeError("media_too_large")
            if total>10000: tmp.replace(target); return True
            tmp.unlink(missing_ok=True)
        except Exception: pass
    return False

def _scene_frames(video:Path,out:Path,duration:float):
    out.mkdir(parents=True,exist_ok=True)
    # Adaptive sampling: at most 12 representative frames per source.
    count=max(3,min(12,int(math.ceil(max(duration,1)/8))))
    interval=max(1.0,duration/count)
    pattern=str(out/"frame-%03d.jpg")
    subprocess.run(["ffmpeg","-y","-i",str(video),"-vf",f"fps=1/{interval},scale=640:-2","-frames:v",str(count),pattern],capture_output=True,timeout=180)
    return sorted(out.glob("frame-*.jpg"))

def _vision(frame:Path):
    key=os.getenv("OPENROUTER_API_KEY","").strip()
    if not key:return {"description":"vision_pending","tags":[]}
    import base64
    b64=base64.b64encode(frame.read_bytes()).decode()
    try:
        r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},json={"model":os.getenv("CENARA_VISION_MODEL","google/gemini-2.5-flash"),"messages":[{"role":"user","content":[{"type":"text","text":"Describe this video frame for a reusable media library. Return compact JSON with description, objects, setting, shot, mood, tags. Do not identify real people."},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64}}]}],"temperature":0.1,"max_tokens":300},timeout=(20,90))
        txt=((r.json().get("choices") or [{}])[0].get("message") or {}).get("content","")
        txt=txt.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(txt)
    except Exception:return {"description":"vision_failed","tags":[]}

def _tokens(text:str):
    return {x for x in "".join(c.lower() if c.isalnum() else " " for c in text).split() if len(x)>2}
def _semantic_score(query:str,item:dict):
    q=_tokens(query); d=_tokens(json.dumps(item,ensure_ascii=False))
    return len(q&d)/max(1,len(q))

def ingest_manifest(limit:int|None=None):
    old={x.get("drive_file_id"):x for x in load_index().get("items",[])}
    items=load_manifest().get("items",[]); items=items[:limit] if limit else items
    out=[]; counts={"registered":len(items),"ready":0,"blocked":0,"review_required":0}
    for n,src in enumerate(items,1):
        fid=src["drive_file_id"]; row=dict(old.get(fid) or src)
        video=VAULT/f"drive-{n:03d}-{fid}.mp4"
        if not video.exists() and not _download_drive(fid,video):
            row["status"]="blocked_source"; out.append(row); counts["blocked"]+=1; continue
        probe=_probe(video); duration=float((probe.get("format") or {}).get("duration") or 0)
        if duration<=0:
            row["status"]="invalid_media"; out.append(row); counts["blocked"]+=1; continue
        frames=_scene_frames(video,VAULT/f"drive-{n:03d}-frames",duration)
        scenes=[{"frame":str(x),"analysis":_vision(x)} for x in frames]
        row.update(status="indexed",local_path=str(video),probe=probe,duration=duration,scenes=scenes,
                   fingerprint=hashlib.sha256(video.read_bytes()[:8_000_000]).hexdigest(),
                   rights=row.get("rights","review_required"))
        counts["ready"]+=1
        if row["rights"]=="review_required": counts["review_required"]+=1
        out.append(row); _save({"version":"2.0","counts":counts,"items":out})
    data={"version":"2.0","counts":counts,"items":out}; _save(data); return data

def search_vault(query:str="",limit:int=30,rights_safe:bool=False):
    rows=[]
    for item in load_index().get("items",[]):
        if item.get("status")!="indexed": continue
        if rights_safe and item.get("rights") not in {"XPEX_OWNED","CLIENT_AUTHORIZED"}: continue
        score=_semantic_score(query,item) if query.strip() else 1.0
        if query.strip() and score<=0: continue
        x=dict(item); x["score"]=round(score,4); rows.append(x)
    rows.sort(key=lambda x:x.get("score",0),reverse=True)
    return rows[:limit]

def select_for_edit(query:str,limit:int=8):
    # Production reuse is intentionally rights-gated.
    return search_vault(query,limit=limit,rights_safe=True)
