#!/usr/bin/env python3
"""Build a compact client-side search index from the canonical prompt corpus."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "data/prompts.json"
INDEX = ROOT / "data/search-index.json"


def normalize(text):
    text = str(text or "").lower().replace("ـ", "")
    text = re.sub(r"[\u064B-\u065F]", "", text)
    return " ".join(text.split())


def main():
    data = json.loads(PROMPTS.read_text(encoding="utf-8"))
    records = []
    inverted = {}
    for p in data.get("prompts", []):
        pid = p.get("id")
        if not pid:
            continue
        text = p.get("search_text") or normalize(" ".join(str(p.get(k) or "") for k in ("title","category","subcategory","prompt","tags","models")))
        tokens = sorted(set(re.findall(r"[\w\u0600-\u06FF][\w\u0600-\u06FF+.#-]{1,}", text)))
        records.append({
            "id": pid,
            "title": p.get("title"),
            "task_type": p.get("task_type"),
            "modality": p.get("modality"),
            "category": p.get("category"),
            "subcategory": p.get("subcategory") or (p.get("subcategories") or []),
            "models": p.get("models", []),
            "tags": p.get("tags", []),
            "quality_score": p.get("quality_score"),
            "tokens": tokens
        })
        for token in tokens:
            inverted.setdefault(token, []).append(pid)
    index = {
        "version":"1.0",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "prompt_count":len(records),
        "records":records,
        "inverted_index":inverted
    }
    INDEX.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"status":"ok","prompt_count":len(records),"tokens":len(inverted)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
