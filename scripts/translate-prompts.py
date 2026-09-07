#!/usr/bin/env python3
"""Translate English prompt fields to Arabic without replacing the original.

Uses Google's public translation endpoint with conservative rate limiting. The
workflow keeps the English source in `prompt` and stores the Arabic rendering
in `prompt_ar` so attribution/source text is never lost.
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "data" / "prompts.json"


def is_mostly_english(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    latin = sum("A" <= c <= "Z" or "a" <= c <= "z" for c in letters)
    return latin / len(letters) >= 0.55


def translate(text: str) -> str:
    query = urllib.parse.urlencode({
        "client": "gtx",
        "sl": "auto",
        "tl": "ar",
        "dt": "t",
        "q": text,
    })
    url = "https://translate.googleapis.com/translate_a/single?" + query
    req = urllib.request.Request(url, headers={"User-Agent": "Masad-Maher-Prompt-Library/1.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        data = json.loads(response.read().decode("utf-8"))
    return "".join(part[0] for part in data[0] if part and part[0]).strip()


def main() -> None:
    data = json.loads(PROMPTS.read_text(encoding="utf-8"))
    prompts = data.get("prompts", data if isinstance(data, list) else [])
    translated = 0
    skipped = 0
    failed = 0

    for item in prompts:
        original = str(item.get("prompt", "")).strip()
        if not original or not is_mostly_english(original):
            if original and not item.get("prompt_ar"):
                item["prompt_ar"] = original
                item["translation_status"] = "not_needed"
            skipped += 1
            continue
        if item.get("prompt_ar") and item.get("translation_status") == "translated":
            skipped += 1
            continue
        try:
            item["prompt_ar"] = translate(original)
            item["translation_status"] = "translated"
            item["translated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            translated += 1
            time.sleep(0.25)
        except Exception as exc:
            item["translation_status"] = "failed"
            item["translation_error"] = str(exc)[:300]
            failed += 1

    if isinstance(data, dict):
        data["prompts"] = prompts
        data["translation"] = {
            "language": "ar",
            "translated_count": translated,
            "failed_count": failed,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Arabic translation: translated={translated}, skipped={skipped}, failed={failed}")


if __name__ == "__main__":
    main()
