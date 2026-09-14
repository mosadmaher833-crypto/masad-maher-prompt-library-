#!/usr/bin/env python3
"""Pull declared GitHub prompt repositories into the review inbox.

Only repositories explicitly listed below are read. Candidates stay pending_review;
the existing update engine decides whether they are eligible for publication.
"""
import csv
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data/inbox/github-prompts.json"
MAX_BYTES = 180_000
MAX_FILES_PER_SOURCE = 8

SOURCES = [
    {"id":"prompts-chat","repo":"f/prompts.chat","files":["prompts.csv","PROMPTS.md"],"license":"CC0-1.0 (prompt data, per repository README)"},
    {"id":"awesome-gpt-image-2","repo":"freestylefly/awesome-gpt-image-2","files":["docs/templates.md","agents/skills/gpt-image-2-style-library/references/style-library.md"],"license":"MIT"},
    {"id":"promptforge","repo":"ffdown/PromptForge","files":["STYLES.json","CAMERA.json","MATERIALS.json","README.md"],"license":"MIT"},
    {"id":"frontier-ai-prompts","repo":"sebuzdugan/frontier-ai-prompts","files":["prompts/agents/README.md","prompts/business/README.md","prompts/coding/README.md","prompts/content/README.md","prompts/images/README.md","prompts/research/README.md","templates/core-template.md"],"license":"MIT"},
    {"id":"ai-prompt-cheatsheet","repo":"manduks/ai-prompt-cheatsheet","files":["README.md","index.html"],"license":"MIT"},
    {"id":"ai-boost-awesome-prompts","repo":"ai-boost/awesome-prompts","files":["prompts/3D_Generative_Artist.txt","prompts/Cinematography_Prompt_Engineer.txt","prompts/Personal_Knowledge_Assistant.txt","prompts/Prompt Creater.md","README.md"],"license":"GPL-3.0"},
]


def headers():
    h={"Accept":"application/vnd.github+json","User-Agent":"masad-maher-prompt-library","X-GitHub-Api-Version":"2026-03-10"}
    token=os.getenv("GITHUB_TOKEN")
    if token: h["Authorization"]=f"Bearer {token}"
    return h


def get(url):
    req=urllib.request.Request(url,headers=headers())
    with urllib.request.urlopen(req,timeout=20) as r:
        return r.read(MAX_BYTES).decode("utf-8",errors="replace")


def normalize(s):
    return " ".join(str(s or "").lower().split())


def score(text):
    t=normalize(text); p=0
    if len(t)>=120:p+=2
    if len(t)>=300:p+=2
    if any(x in t for x in ("role","goal","context","instructions","output")):p+=2
    if "you are" in t or "act as" in t:p+=1
    if any(x in t for x in ("constraints","format","steps","criteria")):p+=2
    return min(10,p)


def extract_markdown(text):
    return [x.strip() for x in re.findall(r"```(?:text|markdown|prompt)?\s*\n(.*?)```",text,re.I|re.S) if len(x.strip())>=80]


def extract_text(text):
    blocks=extract_markdown(text)
    for m in re.finditer(r"(?im)^\s*(?:prompt|system prompt)\s*[:\-]\s*(.{80,1800})$",text): blocks.append(m.group(1).strip())
    return blocks


def add(existing,seen,source,rel,prompt,title):
    prompt=prompt.strip()
    if len(prompt)<80:return 0
    h=hashlib.sha256(normalize(prompt).encode()).hexdigest()
    if h in seen or score(prompt)<8:return 0
    existing["candidates"].append({
        "id":f"ghsrc-{source['id']}-{h[:12]}","title":title or rel,
        "category":"prompt-engineering","tags":["github",source["id"],"auto-discovery"],
        "prompt":prompt,"quality_score":score(prompt),"source":"GitHub",
        "source_id":source["id"],"source_repository":source["repo"],
        "source_url":f"https://github.com/{source['repo']}/blob/main/{urllib.parse.quote(rel)}",
        "license":source["license"],"status":"pending_review",
        "attribution_required":True,"import_method":"declared_github_source_connector"
    }); seen.add(h); return 1


def read_source(source,rel):
    url=f"https://raw.githubusercontent.com/{source['repo']}/main/{urllib.parse.quote(rel,safe='/') }"
    try:return get(url)
    except Exception:return ""


def main():
    existing={"version":"3.0","generated_at":None,"status":"review_required","candidates":[]}
    if INBOX.exists():
        try:existing=json.loads(INBOX.read_text(encoding="utf-8"))
        except Exception:pass
    seen={x.get("hash") for x in existing.get("candidates",[]) if x.get("hash")}
    for x in existing.get("candidates",[]):
        if x.get("prompt") and not x.get("hash"):seen.add(hashlib.sha256(normalize(x["prompt"]).encode()).hexdigest())
    added=0; touched=[]
    for source in SOURCES:
        files=source["files"][:MAX_FILES_PER_SOURCE]
        for rel in files:
            raw=read_source(source,rel)
            if not raw:continue
            prompts=[]
            if rel.endswith(".csv"):
                try:
                    for row in csv.DictReader(io.StringIO(raw)):
                        p=row.get("prompt") or row.get("Prompt") or ""
                        if p: prompts.append((p,row.get("act") or rel))
                except Exception: pass
            elif rel.endswith(".json"):
                try:
                    obj=json.loads(raw)
                    def walk(v,key=""):
                        out=[]
                        if isinstance(v,dict):
                            for k,val in v.items():out+=walk(val,k)
                        elif isinstance(v,list):
                            for val in v:out+=walk(val,key)
                        elif isinstance(v,str) and len(v)>=80:out.append((v,key))
                        return out
                    prompts=walk(obj)
                except Exception: prompts=extract_text(raw)
            else:
                prompts=[(p,rel) for p in extract_text(raw)]
            before=len(existing["candidates"])
            for p,title in prompts: added+=add(existing,seen,source,rel,p,title)
            if len(existing["candidates"])>before:touched.append(source["id"])
            time.sleep(0.25)
    existing["generated_at"]=datetime.now(timezone.utc).isoformat()
    existing["added_this_run"]=added
    existing["status"]="review_required"
    existing["last_strategy"]="declared_repositories_with_fixed_source_files"
    existing["last_sources"]=touched
    INBOX.parent.mkdir(parents=True,exist_ok=True)
    INBOX.write_text(json.dumps(existing,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"review_required","added":added,"total_candidates":len(existing["candidates"]),"sources_touched":touched},ensure_ascii=False))

if __name__=="__main__":main()
