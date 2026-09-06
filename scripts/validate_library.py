import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / 'data' / 'prompts.json'
SOURCES = ROOT / 'data' / 'sources.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    data = load(PROMPTS)
    prompts = data.get('prompts', data) if isinstance(data, dict) else data
    sources_data = load(SOURCES)
    sources = sources_data.get('sources', sources_data) if isinstance(sources_data, dict) else sources_data

    assert isinstance(prompts, list), 'prompts.json must contain a prompts array'
    assert isinstance(sources, list), 'sources.json must contain a sources array'

    ids = set()
    hashes = set()
    errors = []
    warnings = []
    required = ('id', 'title', 'category', 'prompt')

    for i, p in enumerate(prompts, 1):
        if not isinstance(p, dict):
            errors.append(f'#{i}: prompt is not an object')
            continue
        for key in required:
            if not str(p.get(key, '')).strip():
                errors.append(f'#{i}: missing {key}')
        pid = str(p.get('id', '')).strip()
        if pid in ids:
            errors.append(f'duplicate id: {pid}')
        ids.add(pid)
        ph = str(p.get('prompt_hash', '')).strip()
        if ph:
            if ph in hashes:
                errors.append(f'duplicate prompt_hash: {ph}')
            hashes.add(ph)
        prompt = str(p.get('prompt', '')).strip()
        if len(prompt) < 40:
            warnings.append(f'{pid}: prompt is very short')
        score = p.get('quality_score')
        if score is not None:
            try:
                score = float(score)
                if not 0 <= score <= 10:
                    errors.append(f'{pid}: quality_score outside 0-10')
            except (TypeError, ValueError):
                errors.append(f'{pid}: invalid quality_score')
        if p.get('source_url'):
            if not re.match(r'^https://', str(p['source_url']), re.I):
                warnings.append(f'{pid}: source_url is not HTTPS')

    source_ids = set()
    for s in sources:
        if isinstance(s, dict) and s.get('id'):
            if s['id'] in source_ids:
                errors.append(f'duplicate source id: {s["id"]}')
            source_ids.add(s['id'])

    print(f'Validated {len(prompts)} prompts and {len(sources)} sources.')
    if warnings:
        print(f'Warnings: {len(warnings)}')
        for item in warnings[:20]:
            print(f'  - {item}')
    if errors:
        print(f'Errors: {len(errors)}')
        for item in errors[:50]:
            print(f'  - {item}')
        raise SystemExit(1)
    print('Library validation: PASS')


if __name__ == '__main__':
    main()
