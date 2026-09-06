#!/usr/bin/env python3
"""Import reusable prompts from permissively licensed public GitHub sources.

Sources are accessed through GitHub's public API, not arbitrary website scraping.
Only prompt-like blocks are extracted, quality-scored, attributed and placed in
an inbox for the normal dedupe/publish pipeline.
"""
import json, os, re, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/inbox/official-github-prompts.json"
API = "https://api.github.com/repos/{repo}/contents/{path}"

TARGETS = [
    {"source_id":"openai", "source":"OpenAI", "repo":"openai/openai-cookbook", "paths":["articles"] , "license":"MIT"},
    {"source_id":"gemini", "source":"Google Gemini", "repo":"google-gemini/cookbook", "paths":["quickstarts/Prompting.ipynb"], "license":"Apache-2.0"},
    {"source_id":"prompt-engineering-guide", "source":"Prompt Engineering Guide", "repo":"dair-ai/Prompt-Engineering-Guide", "paths":["guides/prompts-intro.md","guides/prompts-advanced-usage.md"], "license":"MIT"},
    {"source_id":"microsoft", "source":"Microsoft", "repo":"microsoft/prompts-for-edu", "paths":["Students/Prompts","Educators/Prompts","Staff/Prompts","Administration/Prompts"], "license":"MIT"},
]


def headers():
    h={"Accept":"application/vnd.github+json","User-Agent":"Masad-Maher-Prompt-Library/1.0"}
    token=os.getenv("GITHUB_TOKEN")
    if token: h["Authorization"]=f"Bearer {token}"
    return h


def api(repo,path):
    url=API.format(repo=repo,path=urllib.parse.quote(path,safe="/"))
    req=urllib.request.Request(url,headers=headers())
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def collect_files(repo,path,limit=80):
    data=api(repo,path)
    if isinstance(data,dict): data=[data]
    out=[]
    for item in data:
        if len(out)>=limit: break
        if item.get("type")=="file" and item.get("name","").lower().endswith((".md",".mdx",".ipynb")):
            out.append(item)
        elif item.get("type")=="dir":
            out.extend(collect_files(repo,item["path"],limit-len(out)))
    return out[:limit]


def read_file(item):
    if item.get("download_url"):
        req=urllib.request.Request(item["download_url"],headers=headers())
        with urllib.request.urlopen(req,timeout=30) as r: return r.read().decode("utf-8",errors="ignore")
    return ""


def snippets(text):
    found=[]
    # Markdown fenced blocks are the highest-confidence prompt candidates.
    for block in re.findall(r"```(?:text|prompt|plaintext|\w+)?\s*\n(.*?)```",text,re.I|re.S):
        b=block.strip()
        if 80<=len(b)<=4000 and re.search(r"\b(you are|act as|your task|instruction|generate|write|analyze|create|summarize|classify)\b",b,re.I):
            found.append(b)
    # Explicit Prompt: sections, including Microsoft prompt files.
    for m in re.finditer(r"(?:^|\n)\s*(?:Prompt|Prompt text)\s*:\s*\n?\s*[`\"]?(.{100,4000}?)[`\"]?\s*(?:\n\s*`{0,3}\s*(?:\n|$))",text,re.I|re.S):
        b=m.group(1).strip().strip('`').strip()
        if b and b not in found: found.append(b)
    return found[:12]


def quality(p):
    score=6.0
    if len(p)>=250: score+=0.8
    if len(p)>=600: score+=0.5
    for pat in [r"\b(role|context|goal|task|instructions?)\b",r"\b(output|format|constraints?|requirements?)\b",r"\b(example|examples|input|audience)\b"]:
        if re.search(pat,p,re.I): score+=0.7
    return min(10.0,round(score,1))


def main():
    candidates=[]; seen=set(); stats={}
    for target in TARGETS:
        files=[]
        for path in target["paths"]:
            try: files.extend(collect_files(target["repo"],path))
            except Exception as e: print(f"skip {target['source_id']} {path}: {e}")
        count=0
        for item in files:
            try: text=read_file(item)
            except Exception as e: print(f"read failed {item.get('path')}: {e}"); continue
            if item.get("name","").endswith(".ipynb"):
                try:
                    nb=json.loads(text); text="\n".join("".join(c.get("source",[])) for c in nb.get("cells",[]) if c.get("cell_type") in ("markdown","code"))
                except Exception: pass
            for prompt in snippets(text):
                key=" ".join(prompt.lower().split())
                if key in seen: continue
                seen.add(key)
                q=quality(prompt)
                if q<8: continue
                source_url=f"https://github.com/{target['repo']}/blob/main/{item['path']}"
                candidates.append({
                    "id":f"{target['source_id']}-{len(candidates)+1}","title":f"{target['source']} — {item['name']}",
                    "category":"education" if target['source_id']=="microsoft" else "prompt-engineering",
                    "subcategory":"official-github-prompts","tags":[target['source_id'],"github","imported","licensed"],
                    "prompt":prompt,"quality_score":q,"source":target['source'],"source_id":target['source_id'],
                    "source_repository":target['repo'],"source_url":source_url,"license":target['license'],
                    "status":"pending_review","discovered_at":datetime.now(timezone.utc).isoformat()
                }); count+=1
                if count>=40: break
            if count>=40: break
        stats[target['source_id']]=count
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"generated_at":datetime.now(timezone.utc).isoformat(),"sources":stats,"candidates":candidates},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"sources":stats,"candidates":len(candidates)},ensure_ascii=False))

if __name__=="__main__": main()
