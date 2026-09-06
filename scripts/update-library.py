#!/usr/bin/env python3
"""Update engine for Masad Maher Prompt Library.

Validates the local library, imports candidates from explicitly enabled
connectors, removes duplicates, preserves rich source metadata, and records a
complete update log. No arbitrary website scraping is performed here.
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


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(text):
    return " ".join(str(text or "").lower().split())


def prompt_hash(prompt):
    return hashlib.sha256(normalize(prompt).encode("utf-8")).hexdigest()


def validate_and_dedupe(prompts):
    seen_ids = set()
    seen_hashes = set()
    unique = []
    rejected = 0
    for item in prompts:
        text = str(item.get("prompt") or "").strip()
        if not text:
            rejected += 1
            continue
        pid = str(item.get("id") or "").strip()
        h = prompt_hash(text)
        if (pid and pid in seen_ids) or h in seen_hashes:
            rejected += 1
            continue
        if pid:
            seen_ids.add(pid)
        seen_hashes.add(h)
        item["prompt_hash"] = h
        unique.append(item)
    return unique, rejected, seen_ids, seen_hashes


def connector_summary(rules):
    connectors = rules.get("connectors", [])
    enabled = [c for c in connectors if c.get("status") == "enabled"]
    review = [c for c in connectors if c.get("status") == "review_required"]
    return {
        "declared": len(connectors),
        "enabled": len(enabled),
        "review_required": len(review),
        "enabled_sources": [c.get("source_id") for c in enabled],
    }, {c.get("source_id") for c in enabled}


def source_is_enabled(item, enabled_sources):
    source = normalize(item.get("source"))
    source_id = normalize(item.get("source_id"))
    repo = normalize(item.get("source_repository"))
    if source_id in enabled_sources:
        return True
    if source == "github" and "github" in enabled_sources:
        return True
    if repo and "github" in enabled_sources:
        return True
    return False


def import_inbox(data, config, enabled_sources):
    added = 0
    rejected = 0
    imported = []
    min_quality = int(config.get("rules", {}).get("minimum_quality_for_auto_publish", config.get("min_quality_score", 8)))
    inbox_files = config.get("inbox_files", [])
    current = data.get("prompts", [])
    _, _, existing_ids, existing_hashes = validate_and_dedupe(current)

    for relative in inbox_files:
        path = ROOT / relative
        if not path.exists():
            continue
        inbox = read_json(path)
        candidates = inbox.get("candidates", [])
        for item in candidates:
            if item.get("status") not in ("pending_review", "approved", "ready"):
                continue
            if not source_is_enabled(item, enabled_sources):
                continue
            try:
                quality = float(item.get("quality_score", 0))
            except (TypeError, ValueError):
                quality = 0
            if quality < min_quality:
                rejected += 1
                continue
            text = str(item.get("prompt") or "").strip()
            if not text:
                rejected += 1
                continue
            h = prompt_hash(text)
            pid = str(item.get("id") or "imported-" + h[:12])
            if pid in existing_ids or h in existing_hashes:
                continue

            # Preserve the useful metadata supplied by the connector rather
            # than reducing every imported record to only title/prompt/source.
            record = {
                "id": pid,
                "title": item.get("title") or "Prompt مستورد",
                "category": item.get("category") or "prompt-engineering",
                "subcategory": item.get("subcategory"),
                "tags": item.get("tags") or ["imported"],
                "prompt": text,
                "quality_score": quality,
                "source": item.get("source") or "Unknown",
                "source_id": item.get("source_id"),
                "source_repository": item.get("source_repository"),
                "source_url": item.get("source_url"),
                "image_url": item.get("image_url"),
                "model": item.get("model"),
                "model_version_ids": item.get("model_version_ids"),
                "width": item.get("width"),
                "height": item.get("height"),
                "seed": item.get("seed"),
                "negative_prompt": item.get("negative_prompt"),
                "license": item.get("license"),
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "import_method": "enabled_connector_auto_publish",
            }
            record = {k: v for k, v in record.items() if v is not None}
            current.append(record)
            existing_ids.add(pid)
            existing_hashes.add(h)
            imported.append(pid)
            added += 1

    data["prompts"] = current
    return data, added, rejected, imported


def main():
    config = read_json(CONFIG)
    data = read_json(PROMPTS)
    sources = read_json(SOURCES)
    rules = read_json(RULES)
    connectors, enabled_sources = connector_summary(rules)

    before = len(data.get("prompts", []))
    if config.get("auto_publish"):
        data, imported, import_rejected, imported_ids = import_inbox(data, config, enabled_sources)
    else:
        imported, import_rejected, imported_ids = 0, 0, []
    unique, dedupe_rejected, _, _ = validate_and_dedupe(data.get("prompts", []))
    data["prompts"] = unique
    after = len(unique)
    rejected = import_rejected + dedupe_rejected
    now = datetime.now(timezone.utc).isoformat()

    log = {
        "version": "1.3",
        "last_run": now,
        "status": "completed_auto_publish" if config.get("auto_publish") else "dry_run",
        "added": imported,
        "updated": 0,
        "rejected": rejected,
        "deduplicated": max(0, before + imported - after),
        "source_count": len(sources.get("sources", [])),
        "prompt_count": after,
        "connectors": connectors,
        "auto_publish": bool(config.get("auto_publish", False)),
        "imported_ids": imported_ids[:100],
        "notes": "النشر التلقائي محصور في الموصلات المعلنة والمفعلة وبجودة دنيا 8/10، مع الاحتفاظ برابط المصدر وبيانات الصورة/النموذج والترخيص عند توفرها."
    }

    write_json(PROMPTS, data)
    write_json(LOG, log)
    print(json.dumps(log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
