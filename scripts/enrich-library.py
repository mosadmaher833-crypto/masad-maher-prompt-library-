#!/usr/bin/env python3
"""Normalize the prompt corpus into a canonical, searchable structure.

This script keeps backward compatibility with the existing UI while adding
stable task/modality/model/tags/search metadata and merging duplicate prompts
into one canonical record with multiple source references.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "data/prompts.json"
TAXONOMY = ROOT / "data/taxonomy.json"

MODEL_ALIASES = {
    "nano banana": "Nano Banana", "gemini": "Gemini", "midjourney": "Midjourney",
    "flux": "FLUX", "stable diffusion": "Stable Diffusion", "sdxl": "SDXL",
    "veo": "Veo", "runway": "Runway", "kling": "Kling", "sora": "Sora",
    "seedance": "Seedance", "ltx": "LTX", "wan": "Wan", "chatgpt": "ChatGPT", "claude": "Claude"
}

TASK_MAP = {
    "صور": "image", "image": "image", "فيديو": "video", "video": "video",
    "إعلان": "advertising", "advertising": "advertising", "كتابة": "writing", "محتوى": "writing",
    "تعليم": "education", "بيانات": "data", "برمجة": "programming", "مقاولات": "contracting",
    "عمارة": "architecture", "architecture": "architecture", "تصوير": "photography",
    "prompt-engineering": "prompt-engineering", "أعمال": "business", "apps": "apps"
}


def normalize(text):
    text = str(text or "").lower().replace("ـ", "")
    text = re.sub(r"[\u064B-\u065F]", "", text)
    return " ".join(text.split())


def digest(text):
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def models_for(item):
    hay = normalize(" ".join(str(item.get(k) or "") for k in ("prompt", "title", "model", "tags")))
    found = []
    for alias, name in MODEL_ALIASES.items():
        if alias in hay and name not in found:
            found.append(name)
    return found


def task_for(item):
    category = str(item.get("category") or "")
    for key, value in TASK_MAP.items():
        if normalize(key) in normalize(category):
            return value
    return "prompt-engineering" if "prompt" in normalize(category) else "other"


def merge_sources(a, b):
    out = list(a or [])
    for src in (b or []):
        key = (src.get("source_id"), src.get("source_url"), src.get("source_repository"), src.get("source"))
        if not any((x.get("source_id"), x.get("source_url"), x.get("source_repository"), x.get("source")) == key for x in out):
            out.append(src)
    return out


def source_record(item):
    keys = ("source", "source_id", "source_url", "source_repository", "license", "image_url")
    return {k: item[k] for k in keys if item.get(k) is not None}


def main():
    data = json.loads(PROMPTS.read_text(encoding="utf-8"))
    prompts = data.get("prompts", [])
    canonical = {}
    for item in prompts:
        text = str(item.get("prompt") or "").strip()
        if not text:
            continue
        h = digest(text)
        models = models_for(item)
        task = task_for(item)
        tags = list(dict.fromkeys([str(x) for x in (item.get("tags") or []) if x]))
        tags.extend(x for x in models if x not in tags)
        record = dict(item)
        record["prompt_hash"] = h
        record["task_type"] = task
        record["modality"] = "video" if task == "video" else ("image" if task in {"image", "advertising", "photography", "architecture"} else "text")
        record["models"] = models
        record["tags"] = list(dict.fromkeys(tags))
        record["search_text"] = normalize(" ".join([str(record.get("title") or ""), str(record.get("category") or ""), str(record.get("subcategory") or ""), str(record.get("prompt") or ""), " ".join(tags), " ".join(models)]))
        record["sources"] = [source_record(record)]
        if h not in canonical:
            canonical[h] = record
        else:
            old = canonical[h]
            old["sources"] = merge_sources(old.get("sources"), record.get("sources"))
            old["tags"] = list(dict.fromkeys((old.get("tags") or []) + tags))
            old["models"] = list(dict.fromkeys((old.get("models") or []) + models))
            old["search_text"] = normalize(" ".join([str(old.get("title") or ""), str(old.get("category") or ""), str(old.get("subcategory") or ""), str(old.get("prompt") or ""), " ".join(old["tags"]), " ".join(old["models"])]))

    ordered = list(canonical.values())
    data["version"] = "2.0"
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data["prompt_count"] = len(ordered)
    data["prompts"] = ordered
    PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status":"ok", "before":len(prompts), "after":len(ordered), "merged":len(prompts)-len(ordered)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
