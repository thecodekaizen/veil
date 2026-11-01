"""Builds voice/teleprompter.html from plan.json. Run: python3 make_teleprompter.py"""
import html, json
from pathlib import Path
plan = json.loads(Path('plan.json').read_text())
lines = [{'id': l['id'], 'beat': l['beat'], 'text': l['text'], 'emphasis': l['emphasis'], 'pause': l['pause_after_ms']} for l in plan['script']]
page = Path('teleprompter.template.html').read_text().replace('__LINES__', json.dumps(lines, ensure_ascii=False))
Path('voice/teleprompter.html').write_text(page)
print(f'{len(lines)} lines -> voice/teleprompter.html')
