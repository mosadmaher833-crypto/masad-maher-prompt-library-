#!/usr/bin/env python3
"""Safe update engine for Masad Maher Prompt Library.

This first version prepares the update pipeline without scraping arbitrary sites.
It validates local data, removes exact duplicate prompts, and records a dry-run log.
External sources should be integrated through approved public APIs/RSS/endpoints.
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "data/prompts.json"
SOURCES = ROOT / "data/sources.json"
LOG = ROOT / "data/update-log.json"
CONFIG = ROOT / "data/update-config.json"


def read_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize(text):
    return " ".join(str(text or "").lower().split())


def prompt_key(prompt):
    raw = normalize(prompt.get("prompt"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main():
    config = read_json(CONFIG)
    data = read_json(PROMPTS)
    sources = read_json(SOURCES)
    prompts = data.get("prompts", [])

    seen = set()
    unique = []
    rejected = 0
    for p in prompts:
        if not p.get("prompt"):
            rejected += 1
            continue
        key = p.get("id") or prompt_key(p)
        if key in seen:
            rejected += 1
            continue
        seen.add(key)
        unique.append(p)

    now = datetime.now(timezone.utc).isoformat()
    log = {
        "version": "1.0",
        "last_run": now,
        "status": "dry_run",
        "added": 0,
        "updated": 0,
        "rejected": rejected,
        "source_count": len(sources.get("sources", [])),
        "prompt_count": len(unique),
        "auto_publish": bool(config.get("auto_publish", False)),
        "notes": "المرحلة الحالية تحقق من البيانات محليًا ولا تسحب محتوى عشوائيًا من المواقع."
    }

    # Preserve data unless a future source adapter explicitly supplies new records.
    if len(unique) != len(prompts):
        data["prompts"] = unique
        with PROMPTS.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    with LOG.open("w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(json.dumps(log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
