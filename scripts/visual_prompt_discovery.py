#!/usr/bin/env python3
"""Safe visual-prompt discovery connector.

Only declared RSS feeds and explicit manual seeds are consumed. Review-required
sources are never scraped. Candidates are validated, quality-scored and kept in
a separate inbox; nothing from this connector is auto-published.
"""
import hashlib
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data/inbox/visual-prompt-discovery.json"
SEEDS = ROOT / "data/inbox/visual-prompt-discovery-seeds.json"

FEEDS = [
    {"source_id": "reddit-midjourney", "name": "Reddit r/midjourney", "url": "https://www.reddit.com/r/midjourney/.rss", "model": "Midjourney"},
    {"source_id": "reddit-promptengineering", "name": "Reddit r/PromptEngineering", "url": "https://www.reddit.com/r/PromptEngineering/.rss", "model": "Prompt Engineering"},
]

MODEL_WORDS = ("midjourney", "nano banana", "flux", "stable diffusion", "sdxl", "runway", "kling", "sora", "veo")


def normalize(text):
    return " ".join(str(text or "").lower().split())


def valid_https(value):
    try:
        p = urlparse(str(value or ""))
        return p.scheme == "https" and bool(p.netloc)
    except Exception:
        return False


def clean_html(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<img[^>]+(?:src|href)=['\"]([^'\"]+)['\"][^>]*>", r"\nIMAGE_URL:\1\n", value, flags=re.I)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p>|</div>|</li>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_prompt(text):
    raw = clean_html(text)
    patterns = [
        r"(?:prompt(?:\s+text)?|my prompt|prompt i used)\s*[:\-]\s*(.{100,5000}?)(?=\s+(?:negative prompt|model|settings|parameters|source|image|credits)\s*[:\-]|$)",
        r"(?:prompt(?:\s+text)?|my prompt|prompt i used)\s+(.{100,5000}?)(?=\s+(?:negative prompt|model|settings|parameters)\b|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            candidate = match.group(1).strip(" `\"'\t")
            if 100 <= len(candidate) <= 5000:
                return candidate
    return ""


def extract_image(text):
    raw = html.unescape(str(text or ""))
    match = re.search(r"IMAGE_URL:(https?://[^\s]+)", raw, re.I)
    if match and valid_https(match.group(1)):
        return match.group(1).rstrip(")>,\"'")
    for url in re.findall(r"https://[^\s<>'\"]+", raw):
        u = url.rstrip(")>,\"'")
        if re.search(r"\.(?:jpg|jpeg|png|webp)(?:\?|$)", u, re.I) and valid_https(u):
            return u
    return ""


def quality(prompt):
    p = normalize(prompt)
    if len(p) < 100:
        return 0
    score = 5.5
    if len(p) >= 250:
        score += 0.8
    if len(p) >= 500:
        score += 0.7
    if any(w in p for w in ("lighting", "camera", "lens", "composition", "depth", "texture")):
        score += 1.0
    if any(w in p for w in ("cinematic", "photorealistic", "realistic", "detailed", "editorial", "style")):
        score += 1.0
    if any(w in p for w in ("--ar", "--stylize", "negative", "steps", "cfg")):
        score += 0.5
    return min(10.0, round(score, 1))


def fetch_feed(feed):
    req = urllib.request.Request(
        feed["url"],
        headers={"User-Agent": "Masad-Maher-Prompt-Library/visual-discovery/1.0", "Accept": "application/rss+xml, application/atom+xml, text/xml"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_feed(xml_text, feed):
    root = ET.fromstring(xml_text)
    items = []
    for node in root.iter():
        if node.tag.split("}")[-1] not in ("item", "entry"):
            continue
        values = {}
        raw_values = {}
        for child in list(node):
            key = child.tag.split("}")[-1]
            values.setdefault(key, []).append("".join(child.itertext()).strip())
            raw_values.setdefault(key, []).append(ET.tostring(child, encoding="unicode"))
            href = child.attrib.get("href")
            if href:
                values.setdefault(key + "_href", []).append(href)
        title = (values.get("title") or [""])[0]
        link = (values.get("link") or [""])[0]
        if not valid_https(link):
            link = (values.get("link_href") or [""])[0]
        author = (values.get("author") or values.get("creator") or [""])[0]
        description = (raw_values.get("description") or raw_values.get("content") or raw_values.get("summary") or [""])[0]
        prompt = extract_prompt(description)
        image_url = extract_image(description)
        if not prompt or not image_url or not valid_https(link):
            continue
        score = quality(prompt)
        if score < 8:
            continue
        creator = re.sub(r"^/u/", "", author.strip())
        creator_url = f"https://www.reddit.com/user/{creator}/" if creator and re.match(r"^[A-Za-z0-9_-]+$", creator) else ""
        model = feed.get("model")
        lower = normalize(title + " " + description)
        for word in MODEL_WORDS:
            if word in lower:
                model = word
                break
        items.append({
            "id": "visual-" + hashlib.sha256((link + "\n" + normalize(prompt)).encode("utf-8")).hexdigest()[:16],
            "title": title or f"{feed['name']} visual prompt",
            "source_id": feed["source_id"],
            "source": feed["name"],
            "source_url": link,
            "image_url": image_url,
            "prompt_text": prompt,
            "prompt": prompt,
            "creator": creator,
            "creator_url": creator_url,
            "model": model,
            "license": "community content — review reuse permission before publication",
            "quality_score": score,
            "review_status": "pending_review",
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        })
    return items


def load_seeds():
    if not SEEDS.exists():
        return []
    try:
        data = json.loads(SEEDS.read_text(encoding="utf-8"))
        return data.get("items", []) if isinstance(data, dict) else []
    except Exception as exc:
        print(f"seed file ignored: {exc}")
        return []


def main():
    if INBOX.exists():
        try:
            data = json.loads(INBOX.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    existing = data.get("items", []) if isinstance(data, dict) else []
    seen = {x.get("id") for x in existing if x.get("id")}
    seen_prompts = {normalize(x.get("prompt_text") or x.get("prompt")) for x in existing}
    added = 0
    errors = []

    candidates = []
    for feed in FEEDS:
        try:
            candidates.extend(parse_feed(fetch_feed(feed), feed))
        except Exception as exc:
            errors.append(f"{feed['source_id']}: {exc}")

    candidates.extend(load_seeds())
    for item in candidates:
        item.setdefault("review_status", "pending_review")
        item.setdefault("discovered_at", datetime.now(timezone.utc).isoformat())
        prompt = normalize(item.get("prompt_text") or item.get("prompt"))
        if not item.get("source_url") or not item.get("image_url") or not prompt:
            continue
        if not valid_https(item["source_url"]) or not valid_https(item["image_url"]):
            continue
        if len(prompt) < 100 or item.get("review_status") not in {"pending_review", "approved", "rejected"}:
            continue
        if item.get("id") in seen or prompt in seen_prompts:
            continue
        item["prompt_text"] = item.get("prompt_text") or item.get("prompt")
        item["prompt"] = item["prompt_text"]
        item["quality_score"] = float(item.get("quality_score") or quality(item["prompt_text"]))
        if item["quality_score"] < 8:
            continue
        existing.append(item)
        seen.add(item.get("id"))
        seen_prompts.add(prompt)
        added += 1

    data = {
        "version": "1.1",
        "status": "ready_for_review",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "added_this_run": added,
        "errors": errors,
        "items": existing,
        "policy": "review_required; never auto-publish social/community candidates",
    }
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    INBOX.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": data["status"], "added": added, "total": len(existing), "errors": len(errors)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
