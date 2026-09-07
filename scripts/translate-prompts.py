#!/usr/bin/env python3
"""Translate English prompt fields to Arabic without replacing the original."""
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    query = urllib.parse.urlencode({"client":"gtx","sl":"auto","tl":"ar","dt":"t","q":text})
    req = urllib.request.Request("https://translate.googleapis.com/translate_a/single?" + query, headers={"User-Agent":"Masad-Maher-Prompt-Library/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    return "".join(part[0] for part in data[0] if part and part[0]).strip()

def main() -> None:
    data = json.loads(PROMPTS.read_text(encoding="utf-8"))
    prompts = data.get("prompts", [])
    jobs = {}
    translated = skipped = failed = 0
    for idx, item in enumerate(prompts):
        original = str(item.get("prompt", "")).strip()
        if not original or not is_mostly_english(original):
            if original and not item.get("prompt_ar"):
                item["prompt_ar"] = original
                item["translation_status"] = "not_needed"
            skipped += 1
        elif item.get("prompt_ar") and item.get("translation_status") == "translated":
            skipped += 1
        else:
            jobs[idx] = original
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(translate, text): idx for idx, text in jobs.items()}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                prompts[idx]["prompt_ar"] = future.result()
                prompts[idx]["translation_status"] = "translated"
                prompts[idx]["translated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                translated += 1
            except Exception as exc:
                prompts[idx]["translation_status"] = "failed"
                prompts[idx]["translation_error"] = str(exc)[:300]
                failed += 1
    data["prompts"] = prompts
    data["translation"] = {"language":"ar","translated_count":translated,"skipped_count":skipped,"failed_count":failed,"updated_at":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    PROMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["translation"], ensure_ascii=False))
if __name__ == "__main__": main()
