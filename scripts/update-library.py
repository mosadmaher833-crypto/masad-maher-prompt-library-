#!/usr/bin/env python3
"""Safe update engine for Masad Maher Prompt Library.

The engine validates local data and declared source connectors.
It does not scrape arbitrary websites. A connector must be explicitly declared
in data/source-rules.json before it can be activated.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "data/prompts.json"
SOURCES = ROOT / "data/sources.json"
RULES = ROOT / "data/source-rules.json"
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


def validate_prompts(prompts):
    seen = set()
    unique = []
    rejected = 0
    for prompt in prompts:
        if not prompt.get("prompt"):
            rejected += 1
            continue
        key = prompt.get("id") or prompt_key(prompt)
        if key in seen:
            rejected += 1
            continue
        seen.add(key)
        unique.append(prompt)
    return unique, rejected


def connector_summary(rules):
    connectors = rules.get("connectors", [])
    enabled = [c for c in connectors if c.get("status") == "enabled"]
    review = [c for c in connectors if c.get("status") == "review_required"]
    return {
        "declared": len(connectors),
        "enabled": len(enabled),
        "review_required": len(review),
        "enabled_sources": [c.get("source_id") for c in enabled],
    }


def main():
    config = read_json(CONFIG)
    data = read_json(PROMPTS)
    sources = read_json(SOURCES)
    rules = read_json(RULES)
    prompts = data.get("prompts", [])

    unique, rejected = validate_prompts(prompts)
    connectors = connector_summary(rules)
    now = datetime.now(timezone.utc).isoformat()

    log = {
        "version": "1.1",
        "last_run": now,
        "status": "dry_run",
        "added": 0,
        "updated": 0,
        "rejected": rejected,
        "source_count": len(sources.get("sources", [])),
        "prompt_count": len(unique),
        "connectors": connectors,
        "auto_publish": bool(config.get("auto_publish", False)),
        "notes": "المرحلة الحالية تتحقق من البيانات وقواعد الموصلات. لا يتم سحب محتوى من مصدر إلا عبر موصل معلن ومفعل."
    }

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
