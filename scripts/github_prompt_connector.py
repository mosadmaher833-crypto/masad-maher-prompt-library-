#!/usr/bin/env python3
"""Discover candidate prompts from public GitHub into a review inbox.

The connector is intentionally review-only. It prefers authenticated GitHub API
requests, checks the dedicated code-search quota before using code search, and
falls back to repository/README discovery when code search is rate-limited.
Candidates never go directly into data/prompts.json.
"""
import hashlib
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
INBOX = ROOT / "data" / "inbox" / "github-prompts.json"
CODE_QUERIES = [
    '"prompt template"',
    '"system prompt"',
    '"You are" prompt',
    '"Act as" prompt',
]
REPO_QUERIES = [
    "prompt engineering",
    "prompt templates",
]
MAX_RESULTS = 5
MAX_REPOS = 3
MAX_FILE_BYTES = 200_000


def headers():
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "masad-maher-prompt-library",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def api(url, retries=3):
    """GET JSON with respectful rate-limit handling."""
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=headers())
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in (403, 429) or attempt >= retries:
                raise
            retry_after = exc.headers.get("Retry-After")
            reset = exc.headers.get("X-RateLimit-Reset")
            if retry_after:
                wait = min(60, max(1, int(float(retry_after))))
            elif exc.headers.get("X-RateLimit-Remaining") == "0" and reset:
                wait = min(90, max(1, int(reset) - int(time.time()) + 1))
            else:
                wait = min(60, 2 ** attempt * 5)
            print(f"Rate limited ({exc.code}); waiting {wait}s before retry {attempt + 1}/{retries}")
            time.sleep(wait)
    raise RuntimeError("GitHub API rate limit retry budget exhausted")


def normalize(text):
    return " ".join(str(text or "").lower().split())


def score(text):
    t = normalize(text)
    points = 0
    if len(t) >= 120:
        points += 2
    if len(t) >= 300:
        points += 2
    if any(x in t for x in ("role", "goal", "context", "instructions", "output")):
        points += 2
    if "you are" in t or "act as" in t:
        points += 1
    if any(x in t for x in ("constraints", "format", "steps", "criteria")):
        points += 2
    if "http://" in t or "https://" in t:
        points -= 1
    return max(0, min(10, points))


def extract(text):
    candidates = []
    blocks = re.findall(r"```(?:text|markdown|prompt)?\s*\n(.*?)```", text, re.I | re.S)
    candidates.extend(blocks)
    for m in re.finditer(r"(?im)^\s*(?:prompt|system prompt)\s*[:\-]\s*(.{80,1500})$", text):
        candidates.append(m.group(1))
    return [c.strip() for c in candidates if len(c.strip()) >= 80]


def fetch_raw(url):
    req = urllib.request.Request(url, headers={"User-Agent": "masad-maher-prompt-library"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read(MAX_FILE_BYTES).decode("utf-8", errors="replace")


def add_candidate(existing, seen, prompt, title, source_url, repository, license_name):
    prompt = prompt.strip()
    h = hashlib.sha256(normalize(prompt).encode("utf-8")).hexdigest()
    if h in seen:
        return False
    s = score(prompt)
    if s < 8:
        return False
    existing["candidates"].append({
        "id": "gh-" + h[:12],
        "title": title,
        "category": "prompt-engineering",
        "tags": ["github", "review"],
        "prompt": prompt,
        "quality_score": s,
        "source": "GitHub",
        "source_repository": repository,
        "source_url": source_url,
        "license": license_name,
        "status": "pending_review",
    })
    seen.add(h)
    return True


def code_search(existing, seen):
    """Use at most one code-search request when that quota is available."""
    try:
        limits = api("https://api.github.com/rate_limit")
        remaining = limits.get("resources", {}).get("code_search", {}).get("remaining", 0)
        if remaining < 1:
            print("Code-search quota unavailable; switching to repository fallback.")
            return 0
    except Exception as exc:
        print(f"Could not inspect code-search quota: {exc}")
        return 0

    q = CODE_QUERIES[datetime.now(timezone.utc).timetuple().tm_yday % len(CODE_QUERIES)]
    url = "https://api.github.com/search/code?" + urllib.parse.urlencode({"q": q, "per_page": MAX_RESULTS})
    try:
        result = api(url)
    except Exception as exc:
        print(f"Code search unavailable: {exc}")
        return 0

    added = 0
    for item in result.get("items", []):
        repo = item.get("repository", {})
        try:
            raw_url = item.get("download_url") or f"https://raw.githubusercontent.com/{repo.get('full_name')}/{repo.get('default_branch', 'main')}/{item.get('path')}"
            raw = fetch_raw(raw_url)
        except Exception:
            continue
        for prompt in extract(raw):
            if add_candidate(existing, seen, prompt, item.get("name") or item.get("path"), item.get("html_url"), repo.get("full_name"), None):
                added += 1
        time.sleep(0.5)
    return added


def repository_fallback(existing, seen):
    """Search repositories (normal search quota) and inspect small README files."""
    added = 0
    for q in REPO_QUERIES:
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": MAX_REPOS})
        try:
            result = api(url)
        except Exception as exc:
            print(f"Repository search unavailable: {exc}")
            continue
        for repo in result.get("items", []):
            full_name = repo.get("full_name")
            branch = repo.get("default_branch", "main")
            raw_url = f"https://raw.githubusercontent.com/{full_name}/{branch}/README.md"
            try:
                raw = fetch_raw(raw_url)
            except Exception:
                continue
            for prompt in extract(raw):
                if add_candidate(existing, seen, prompt, f"{full_name} README prompt", f"https://github.com/{full_name}/blob/{branch}/README.md", full_name, (repo.get("license") or {}).get("spdx_id")):
                    added += 1
            time.sleep(0.5)
        time.sleep(1)
    return added


def main():
    existing = {"version": "1.0", "generated_at": None, "status": "review_required", "candidates": []}
    if INBOX.exists():
        existing = json.loads(INBOX.read_text(encoding="utf-8"))
    seen = {x.get("hash") for x in existing.get("candidates", []) if x.get("hash")}
    # Rebuild hashes for older inbox records that predate the hash field.
    for item in existing.get("candidates", []):
        if not item.get("hash") and item.get("prompt"):
            seen.add(hashlib.sha256(normalize(item["prompt"]).encode("utf-8")).hexdigest())

    added = code_search(existing, seen)
    if added == 0:
        added += repository_fallback(existing, seen)

    existing["generated_at"] = datetime.now(timezone.utc).isoformat()
    existing["added_this_run"] = added
    existing["status"] = "review_required"
    existing["last_strategy"] = "code_search_then_repository_fallback"
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    INBOX.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "review_required", "added": added, "total_candidates": len(existing["candidates"]), "strategy": existing["last_strategy"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
