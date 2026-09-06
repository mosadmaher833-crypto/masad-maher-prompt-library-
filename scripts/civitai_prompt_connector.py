#!/usr/bin/env python3
"""Discover reusable, SFW image prompts from Civitai's public API.

Uses only the documented public GET /api/v1/images endpoint. No HTML scraping,
no authentication, and no restricted/NSFW content. Results are written to the
inbox for the normal dedupe/quality pipeline.
"""
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/inbox/civitai-prompts.json"
API = "https://civitai.com/api/v1/images"


def fetch(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Masad-Maher-Prompt-Library/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def score(prompt, meta):
    text = str(prompt or "").strip()
    if len(text) < 100:
        return 0
    value = 5.0
    if len(text) >= 220:
        value += 1
    if len(text) >= 450:
        value += 0.5
    features = [
        r"\b(cinematic|editorial|professional|photograph|photography|portrait)\b",
        r"\b(lighting|light|backlight|rim light|soft light|volumetric)\b",
        r"\b(camera|lens|35mm|50mm|85mm|depth of field|bokeh)\b",
        r"\b(composition|framing|close[- ]?up|wide shot|full body|symmetrical)\b",
        r"\b(detail|high detail|texture|sharp|realistic|photorealistic)\b",
        r"\b(color grading|film grain|hdr|raw|analog)\b",
    ]
    for pattern in features:
        if re.search(pattern, text, re.I):
            value += 0.6
    if meta.get("civitaiResources"):
        value += 0.4
    return min(10.0, round(value, 1))


def category(prompt):
    p = prompt.lower()
    if any(x in p for x in ("product", "bottle", "packaging", "advertising")):
        return "advertising"
    if any(x in p for x in ("architecture", "building", "interior", "exterior")):
        return "architecture"
    if any(x in p for x in ("food", "dish", "restaurant", "cuisine")):
        return "food"
    if any(x in p for x in ("fashion", "editorial", "runway", "outfit")):
        return "fashion"
    if any(x in p for x in ("landscape", "mountain", "forest", "nature")):
        return "photography"
    return "image"


def main():
    candidates = []
    seen = set()
    try:
        data = fetch({
            "limit": 100,
            "sort": "Newest",
            "period": "Week",
            "nsfw": "None",
            "browsingLevel": 1,
            "type": "image",
            "withMeta": "true",
        })
    except Exception as exc:
        print(f"Civitai request failed: {exc}")
        data = {"items": []}

    for item in data.get("items", []):
        if str(item.get("nsfwLevel", "None")).lower() not in ("none", "0", "false"):
            continue
        meta = item.get("meta") or {}
        prompt = str(meta.get("prompt") or "").strip()
        if not prompt:
            continue
        key = " ".join(prompt.lower().split())
        if key in seen:
            continue
        seen.add(key)
        quality = score(prompt, meta)
        if quality < 8:
            continue

        image_id = item.get("id")
        source_url = f"https://civitai.com/images/{image_id}" if image_id else "https://civitai.com/"
        candidates.append({
            "id": f"civitai-{image_id}",
            "title": f"Civitai prompt {image_id}",
            "category": category(prompt),
            "subcategory": "ai-image-prompts",
            "tags": ["civitai", "ai-image", "imported", "api"],
            "prompt": prompt,
            "quality_score": quality,
            "source": "Civitai",
            "source_id": "civitai",
            "source_url": source_url,
            "image_url": item.get("url"),
            "model": meta.get("Model") or meta.get("model"),
            "model_version_ids": item.get("modelVersionIds", []),
            "width": item.get("width"),
            "height": item.get("height"),
            "seed": meta.get("seed"),
            "negative_prompt": meta.get("negativePrompt"),
            "license": "See original Civitai item and creator/model license",
            "status": "pending_review",
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source": "Civitai",
        "source_id": "civitai",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": API,
        "candidates": candidates,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source": "civitai", "candidates": len(candidates)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
