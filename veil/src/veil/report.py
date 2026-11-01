"""receipt.html: a static, self-contained report rendered from audit.json (statuses are never recomputed here)."""
import html
import json
from pathlib import Path

from veil.schemas import AuditArtifact, DiscoverArtifact, RedactArtifact

FOOTER = 'Veil reports what its listed checks found. It cannot prove the absence of identifying information.'
CSS = '''
:root{--bg:#0d0f12;--panel:#14171c;--line:#262b34;--text:#e7e3da;--dim:#9a968d;--amber:#e8b04a;--ok:#6fcf8f;--bad:#e66b5b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 "JetBrains Mono",ui-monospace,Menlo,monospace}
main{max-width:920px;margin:0 auto;padding:32px 16px}
h1{font:600 34px/1.15 Fraunces,Georgia,serif;margin:0 0 4px}h2{font:600 20px Fraunces,Georgia,serif;color:var(--amber);margin:32px 0 8px}
.dim{color:var(--dim)}.panel{background:var(--panel);border:1px solid var(--line);padding:12px 14px;margin:8px 0}
.COVERED{color:var(--ok)}.UNRESOLVED{color:var(--bad)}.NOT_CHECKED{color:var(--amber)}
table{width:100%;border-collapse:collapse}td,th{border-top:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top;font-size:13px}
body{overflow-wrap:anywhere}
@media(max-width:640px){table,tbody,tr,td{display:block;width:100%}tr:first-child:has(th){display:none}
tr{border-top:1px solid var(--line);padding:6px 0}td{border:0;padding:2px 0}h1{font-size:28px}}
footer{margin-top:40px;border-top:1px solid var(--line);padding-top:12px;color:var(--dim);font-size:13px}
'''


def esc(v) -> str:
    return html.escape(str(v))


def load_calls(root: Path) -> list[dict]:
    """Every call ledger in the run dir: calls.json plus ledgers set aside when stages were re-run
    (calls.<label>.json), so a re-run never hides calls already made for this run."""
    return [c for p in sorted(root.glob('calls*.json')) for c in json.loads(p.read_text())]


def ledger_summary(calls: list[dict]) -> str:
    unpriced = sum(c.get('estimated_usd') is None for c in calls)
    return (f'{len(calls)} model calls, {sum(c.get("status") != "completed" for c in calls)} failed, '
            f'est. ${sum(c.get("estimated_usd") or 0 for c in calls):.2f}'
            + (f' ({unpriced} calls without a price estimate)' if unpriced else ''))


def render(root: Path) -> Path:
    audit = AuditArtifact.model_validate_json((root / 'audit.json').read_text())
    red = RedactArtifact.model_validate_json((root / 'redact.json').read_text())
    disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
    calls = load_calls(root)
    counts = {s: sum(f.status == s for f in audit.findings) for s in ('COVERED', 'UNRESOLVED', 'NOT_CHECKED')}
    not_run = [c for c in audit.checks if c.status == 'NOT_CHECKED']
    if counts['UNRESOLVED']:
        headline = f'{counts["UNRESOLVED"]} unresolved finding(s). Review them below before sharing.'
    else:
        headline = 'No unresolved risks found by the checks listed below.'
    if counts['NOT_CHECKED'] or not_run:
        headline += f' {counts["NOT_CHECKED"]} item(s) and {len(not_run)} check(s) were not checked.'
    rows = ''.join(
        f'<tr><td class="{f.status}">{f.status}</td><td>{esc(f.kind)}</td><td>{esc(f.label)}<div class="dim">{esc(f.source)}</div></td>'
        f'<td>{"<br>".join(esc(r) for r in f.reasons)}</td></tr>' for f in audit.findings)
    checks = ''.join(f'<tr><td class="{"COVERED" if c.status == "RAN" else "NOT_CHECKED"}">{esc(c.status)}</td>'
                     f'<td>{esc(c.description)}<div class="dim">{esc(c.detail)}</div></td></tr>' for c in audit.checks)
    spark = [c.sam_prompt for c in disc.concepts if c.source == 'spark']
    ledger = ledger_summary(calls)
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Veil receipt</title><link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@600&family=JetBrains+Mono&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><main>
<h1>Veil receipt</h1><div class="dim">input sha256 {esc(red.input_sha256[:16])}… · output sha256 {esc(red.output_sha256[:16])}…</div>
<div class="panel"><b>{esc(headline)}</b><div class="dim">COVERED {counts["COVERED"]} · UNRESOLVED {counts["UNRESOLVED"]} · NOT_CHECKED {counts["NOT_CHECKED"]}</div></div>
<h2>Findings</h2><table><tr><th>Status</th><th>Kind</th><th>Item</th><th>Why</th></tr>{rows}</table>
<h2>Checks listed</h2><table>{checks}</table>
<h2>Concepts proposed by the model but not found in the video</h2><div class="panel">{esc(", ".join(audit.concepts_without_masks) or "none")}</div>
<h2>Model-proposed concepts</h2><div class="panel dim">{esc(", ".join(spark) or "none")}. Models propose; this report's statuses are computed by code.</div>
<h2>Limitations</h2><div class="panel"><ul>{"".join(f"<li>{esc(x)}</li>" for x in audit.limitations)}</ul></div>
<h2>Cloud processing</h2><div class="panel dim">Frames, video and audio were sent to Meta model APIs for discovery, tracking and transcription ({esc(ledger)}). Processing is not local.</div>
<footer>{FOOTER}</footer></main></body></html>'''
    out = root / 'receipt.html'
    out.write_text(page)
    return out
