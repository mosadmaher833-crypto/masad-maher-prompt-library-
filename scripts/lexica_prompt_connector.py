#!/usr/bin/env python3
"""Discover public prompts from Lexica's documented JSON search API.

Lexica documents a public GET search endpoint that returns prompt, image, model,
and gallery metadata. This connector only uses that documented API.
"""
import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox" / "lexica-prompts.json"
QUERIES = [
    "cinematic portrait",
    "product advertising",
    "fashion editorial",
    "architecture photography",
    "fantasy cinematic",
    "food photography",
    "luxury product",
    "anime character",
    "film still",
    "3d render",
]
MAX_RESULTS = 50
MIN_PROMPT_LENGTH = 80


def normalize(text):
    return " ".join(str(text or "").lower().split())


def quality(prompt):
    t = normalize(prompt)
    score = 0
    if len(t) >= 120:
        score += 2
    if len(t) >= 300:
        score += 2
    if any(x in t for x in ("lighting", "camera", "lens", "composition", "cinematic", "photography")):
        score += 2
    if any(x in t for x in ("style", "detailed", "high detail", "texture", "realistic")):
        score += 2
    if any(x in t for x in ("--ar", "--stylize", "negative", "steps", "cfg")):
        score += 1
    if len(t) < 80:
        score = 0
    return min(10, score)


def fetch(query):
    url = "https://lexica.art/api/v1/search?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"User-Agent": "masad-maher-prompt-library/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    existing = {"version": "1.0", "generated_at": None, "status": "review_required", "candidates": []}
    if INBOX.exists():
        existing = json.loads(INBOX.read_text(encoding="utf-8"))
    seen = {x.get("hash") for x in existing.get("candidates", []) if x.get("hash")}
    added = 0

    # Rotate the starting query so daily runs cover different subjects.
    day = datetime.now(timezone.utc).timetuple().tm_yday
    ordered = QUERIES[day % len(QUERIES):] + QUERIES[:day % len(QUERIES)]
    for query in ordered[:4]:
        try:
            payload = fetch(query)
        except Exception as exc:
            existing["error"] = str(exc)
            continue
        for item in payload.get("images", [])[:MAX_RESULTS]:
            prompt = str(item.get("prompt") or "").strip()
            if len(prompt) < MIN_PROMPT_LENGTH:
                continue
            h = hashlib.sha256(normalize(prompt).encode("utf-8")).hexdigest()
            if h in seen:
                continue
            score = quality(prompt)
            if score < 8:
                continue
            existing["candidates"].append({
                "id": "lexica-" + h[:12],
                "title": f"Lexica — {query}",
                "category": "image",
                "subcategory": "ai-image-prompts",
                "tags": ["lexica", "image", query],
                "prompt": prompt,
                "quality_score": score,
                "source": "Lexica",
                "source_id": "lexica",
                "source_url": item.get("gallery") or f"https://lexica.art/prompt/{item.get('id')}",
                "image_url": item.get("src"),
                "model": item.get("model"),
                "width": item.get("width"),
                "height": item.get("height"),
                "seed": item.get("seed"),
                "status": "pending_review",
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            })
            seen.add(h)
            added += 1

    existing["generated_at"] = datetime.now(timezone.utc).isoformat()
    existing["added_this_run"] = added
    existing["status"] = "ready_for_auto_publish"
    existing["last_strategy"] = "lexica_documented_search_api"
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    INBOX.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": existing["status"], "added": added, "total_candidates": len(existing["candidates"]), "strategy": existing["last_strategy"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
