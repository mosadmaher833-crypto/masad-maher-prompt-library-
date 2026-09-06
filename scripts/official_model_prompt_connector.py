#!/usr/bin/env python3
"""Discover reusable prompt examples from official model repositories.

Only repositories explicitly allowed by data/source-rules.json are auto-published.
Other model providers are tracked as review-only so the library never silently
scrapes or republishes material without a verified license/API route.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "inbox" / "official-model-prompts.json"

SOURCES = [
    {"source_id": "flux", "repo": "black-forest-labs/flux", "status": "enabled", "license": "Apache-2.0", "model": "FLUX"},
    {"source_id": "anthropic", "repo": "anthropics/courses", "status": "review_required", "license": "CC BY-NC 4.0", "model": "Claude"},
    {"source_id": "wan", "repo": "Wan-Video/Wan2.1", "status": "review_required", "license": "model/repository terms vary", "model": "Wan2.1"},
    {"source_id": "ltx", "repo": "Lightricks/LTX-Video", "status": "review_required", "license": "OpenRail-M / current model terms", "model": "LTX-Video"},
    {"source_id": "stable-diffusion", "repo": "CompVis/stable-diffusion", "status": "review_required", "license": "model-specific terms", "model": "Stable Diffusion"},
    {"source_id": "midjourney", "repo": None, "status": "review_required", "license": "no verified public prompt dataset/API", "model": "Midjourney"},
    {"source_id": "runway", "repo": None, "status": "review_required", "license": "generation API, not prompt-discovery API", "model": "Runway"},
    {"source_id": "kling", "repo": None, "status": "review_required", "license": "no verified public prompt-discovery API", "model": "Kling"},
    {"source_id": "sora", "repo": None, "status": "review_required", "license": "no verified public prompt dataset/API", "model": "Sora"},
    {"source_id": "seedance", "repo": None, "status": "review_required", "license": "no verified public prompt dataset/API", "model": "Seedance"},
]


def get(url: str):
    req = Request(url, headers={"User-Agent": "Masad-Maher-Prompt-Library/1.0"})
    token = os.getenv("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def score(text: str) -> int:
    t = text.lower()
    score = 5
    if len(text) >= 80: score += 1
    if len(text) >= 160: score += 1
    for k in ("camera", "lighting", "motion", "scene", "subject", "style", "action", "prompt"):
        if k in t: score += 1
    return min(score, 10)


def extract_prompts(markdown: str):
    # Prefer explicit prompt-labelled blocks and quoted prompt examples.
    blocks = []
    for m in re.finditer(r"(?is)(?:prompt|text-to-video prompt|image prompt)\s*[:\-]\s*(.+?)(?=\n\s*\n|\n#{1,4}\s|$)", markdown):
        text = re.sub(r"\s+", " ", m.group(1)).strip(" `>\t")
        if 80 <= len(text) <= 2500:
            blocks.append(text)
    for m in re.finditer(r"(?s)```(?:text|prompt)?\s*\n(.+?)\n```", markdown):
        text = re.sub(r"\s+", " ", m.group(1)).strip()
        if 80 <= len(text) <= 2500 and score(text) >= 8:
            blocks.append(text)
    seen = set()
    for x in blocks:
        key = re.sub(r"[^a-z0-9]+", " ", x.lower()).strip()
        if key not in seen:
            seen.add(key)
            yield x


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    candidates = []
    now = datetime.now(timezone.utc).isoformat()

    for src in SOURCES:
        if not src.get("repo"):
            continue
        try:
            readme = get(f"https://raw.githubusercontent.com/{src['repo']}/main/README.md")
        except Exception:
            continue
        for idx, prompt in enumerate(extract_prompts(readme)):
            q = score(prompt)
            if q < 8:
                continue
            candidates.append({
                "id": f"{src['source_id']}-official-{idx}-{abs(hash(prompt))}",
                "title": f"{src['model']} official prompt example {idx + 1}",
                "category": "video" if src["source_id"] in {"wan", "ltx", "runway", "kling", "sora", "seedance"} else "image",
                "subcategory": "official-model-prompts",
                "tags": [src["source_id"], "official", "prompt-engineering"],
                "prompt": prompt,
                "quality_score": q,
                "source": src["repo"],
                "source_id": src["source_id"],
                "source_url": f"https://github.com/{src['repo']}",
                "source_repository": src["repo"],
                "model": src["model"],
                "license": src["license"],
                "status": "pending_review" if src["status"] != "enabled" else "approved",
                "discovered_at": now,
                "import_method": "official_github_repository",
            })

    OUT.write_text(json.dumps({"generated_at": now, "candidates": candidates, "sources": SOURCES}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"official-model connector: {len(candidates)} candidates")


if __name__ == "__main__":
    main()
