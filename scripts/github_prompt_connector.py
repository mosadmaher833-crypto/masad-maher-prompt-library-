#!/usr/bin/env python3
"""Discover candidate prompts from public GitHub code into a review inbox.

Uses GitHub's public code-search endpoint through the API. This connector never
publishes directly to data/prompts.json; candidates are written to the inbox
for review first.
"""
import base64
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox" / "github-prompts.json"
QUERIES = [
    '"You are" prompt',
    '"Act as" prompt',
    '"prompt template"',
    '"system prompt"',
]
MAX_RESULTS = 8
MAX_FILE_BYTES = 200_000


def api(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "masad-maher-prompt-library"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def normalize(text):
    return " ".join(str(text or "").lower().split())


def score(text):
    t = normalize(text)
    points = 0
    if len(t) >= 120: points += 2
    if len(t) >= 300: points += 2
    if any(x in t for x in ("role", "goal", "context", "instructions", "output")): points += 2
    if "you are" in t or "act as" in t: points += 1
    if any(x in t for x in ("constraints", "format", "steps", "criteria")): points += 2
    if "http://" in t or "https://" in t: points -= 1
    return max(0, min(10, points))


def extract(text):
    candidates = []
    blocks = re.findall(r"```(?:text|markdown|prompt)?\s*\n(.*?)```", text, re.I | re.S)
    if blocks:
        candidates.extend(blocks)
    for m in re.finditer(r"(?im)^\s*(?:prompt|system prompt)\s*[:\-]\s*(.{80,1500})$", text):
        candidates.append(m.group(1))
    return [c.strip() for c in candidates if len(c.strip()) >= 80]


def main():
    existing = {"version": "1.0", "generated_at": None, "status": "review_required", "candidates": []}
    if INBOX.exists():
        existing = json.loads(INBOX.read_text(encoding="utf-8"))
    seen = {x.get("hash") for x in existing.get("candidates", [])}
    added = 0

    for q in QUERIES:
        url = "https://api.github.com/search/code?" + urllib.parse.urlencode({"q": q, "per_page": MAX_RESULTS})
        try:
            result = api(url)
        except Exception as exc:
            existing["error"] = str(exc)
            continue
        for item in result.get("items", []):
            repo = item.get("repository", {})
            file_url = item.get("html_url")
            try:
                raw_url = item.get("download_url")
                if not raw_url:
                    raw_url = f"https://raw.githubusercontent.com/{repo.get('full_name')}/{repo.get('default_branch','main')}/{item.get('path')}"
                req = urllib.request.Request(raw_url, headers={"User-Agent": "masad-maher-prompt-library"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    raw = r.read(MAX_FILE_BYTES).decode("utf-8", errors="replace")
            except Exception:
                continue
            for prompt in extract(raw):
                h = hashlib.sha256(normalize(prompt).encode("utf-8")).hexdigest()
                if h in seen:
                    continue
                s = score(prompt)
                if s < 8:
                    continue
                existing["candidates"].append({
                    "id": "gh-" + h[:12],
                    "title": item.get("name") or item.get("path"),
                    "category": "prompt-engineering",
                    "tags": ["github", "review"],
                    "prompt": prompt,
                    "quality_score": s,
                    "source": "GitHub",
                    "source_repository": repo.get("full_name"),
                    "source_url": file_url,
                    "license": None,
                    "status": "pending_review",
                })
                seen.add(h)
                added += 1

    existing["generated_at"] = datetime.now(timezone.utc).isoformat()
    existing["added_this_run"] = added
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    INBOX.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "review_required", "added": added, "total_candidates": len(existing["candidates"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
