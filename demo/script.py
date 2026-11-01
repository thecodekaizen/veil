"""Phase 2 script source. Writes script.md + plan.json['script'] and checks the word budget.
Every claim cites its evidence file (ev). Run: python3 script.py"""
import json, re
from pathlib import Path

WPM = 150
TARGET_S = 150
L = [  # id, beat, VO, on_screen, emphasis, pause_after_ms, evidence
 ('h1','Hook',"This clip tells a stranger my name. My building. And my phone number.",
  "c2 input playing full-bleed; notification 'Rohan Kulkarni' and gold 'KULKARNI — 12' visible; kinetic words NAME / BUILDING / NUMBER",["name","building","phone number"],500,"runs-postgate/c2 input; c3 audio"),
 ('h2','Hook',"All fictional. But creators post clips like this every day.",
  "Caption chip: 'fictional data · composited clip'",["every day"],300,"gate/GATE.md (composited clips)"),
 ('h3','Problem',"A name on a parcel. A society board behind you. A number you say out loud.",
  "Three quick crops from c1/c2/c3: label, board, waveform",["out loud"],300,"gate/labels/c1-c3.json"),
 ('p1','Problem',"Most redaction tools look for a fixed list. Faces. License plates. Screens. Documents.",
  "Kinetic list of four classes, each ticking off",["fixed list"],250,"eval/results/final/heldout_results.md baseline concepts"),
 ('p2','Problem',"On my held-out clips, that list found zero of four planted leaks.",
  "Big stat card: 0 / 4",["zero of four"],600,"heldout_results.md: baseline-only 0/4"),
 ('a1','Aha',"So Veil asks a different question. What, in this video, could identify you?",
  "Cut to Veil UI (c2), floating window",["this video"],300,"DemoApp"),
 ('a2','Aha',"Muse Spark looks at keyframes and proposes candidates, each with a reason. The notification shows a full name. The gold plate shows a surname and a flat number.",
  "Zoom on amber Spark boxes + callouts with 'why' text from manifest",["Muse Spark","reason"],250,"discover.json why_identifying"),
 ('a2b','Aha',"None of these is a face or a license plate. The model has to understand the scene.",
  "Hold on callouts; small grey 'baseline: face · plate' chips with no box on the name",["understand the scene"],300,"discover.json; c2 baseline concepts"),
 ('a3','Aha',"SAM 3.1 tracks each one through every frame. And the output covers exactly those regions.",
  "Scrub slider 6s→12s; output pane shows covers following; timeline bars",["SAM 3.1","every frame"],300,"track_final.json; redact.json"),
 ('a4','Aha',"With Spark in the loop, three out of four were found. Then I re-ran the whole pipeline three times: discovery passed every run.",
  "Stat card: 0/4 → 3/4, small line 'missed: delivery-box label'",["three of four","missed"],600,"heldout_results.md: baseline+Spark 3/4, L1 missed"),
 ('f1','Proof: verify',"Then code checks the work. Veil decodes its own output and confirms the covers are really there.",
  "Findings rows: 'cover verified in decoded output on all 557 masked frames'",["decodes its own output"],250,"audit.json"),
 ('f1b','Proof: verify',"It re-reads the output with local OCR, and runs a face detector on sampled frames.",
  "Checks listed panel: RAN rows",["local OCR","face detector"],250,"audit.json checks"),
 ('f2','Proof: verify',"And models make mistakes. Here, SAM put the name mask on a block of code.",
  "Zoom on Mask check table: REJECTED row",["mistakes"],200,"verify.json"),
 ('f3','Proof: verify',"Local OCR read the mask, found code instead of the name Spark claimed, and threw it out.",
  "Highlight OCR text 'def total(items)' vs claimed 'KULKARNI'",["threw it out"],500,"verify.json rejected spark-name-overlay-label:0"),
 ('v1','Proof: voice',"Spoken numbers too. Muse Voice Transcribe hears a phone number read out in Hindi, and Veil mutes it.",
  "c3 UI (?run=c3): transcript in Devanagari, red mute bar on timeline",["Hindi","mutes it"],250,"runs-postgate/c3 listen.json, redact.json"),
 ('v2','Proof: voice',"Then it transcribes the output again. No digit run left.",
  "Findings row: 're-transcription of the output found no phone-like digit run'",["again"],300,"c3 audit.json"),
 ('v3','Proof: voice',"But Voice still gets digits wrong, and the mute window met my limit in only one of three runs.",
  "Callout on garbled digits; small card 'over-cover 2.85 s · limit 2.5 s'",["wider than my own limit"],600,"gate/postgate/GATE_RESULT.md G4b"),
 ('r1','Payoff',"That's the point. Veil never says a video is safe.",
  "Headline panel: 'unresolved finding(s). Review them before sharing.'",["never says"],250,"DemoApp headline"),
 ('r2','Payoff',"Every item is covered, unresolved, or not checked. And it tells you why.",
  "Findings table: COVERED / UNRESOLVED / NOT_CHECKED rows with reasons",["covered","unresolved","not checked"],400,"audit.json statuses"),
 ('r2b','Payoff',"In this run, two items are unresolved: a plate track with gaps, and a face-like region. Nothing was left unchecked.",
  "Zoom: UNRESOLVED rows (red) and NOT_CHECKED rows (amber) with reasons",["two","Eight"],400,"runs-postgate/c2 audit.json"),
 ('r3','Payoff',"I held myself to that too. I wrote a test gate before running it. It failed. And false flags still fail two of three re-runs. It's all in the repo.",
  "GATE_RESULT.md FAIL table → post-gate table (G2 PASS post-gate, G4b FAIL)",["failed","post-gate","still fails"],600,"gate/GATE_RESULT.md; gate/postgate/GATE_RESULT.md"),
 ('u1','Payoff',"Every model call is on a ledger. Seven hundred and fifty-one calls, about two dollars forty per clip.",
  "Ledger section of the live site: per-model calls, latency, cost",["ledger"],400,"eval/repeats/summary.json"),
 ('c0','CTA',"Try it live, read the receipt, and decide before you post.",
  "Terminal: 'veil run clip.mp4 --run-id demo' then receipt",["decide"],300,"veil/src/veil/cli.py"),
 ('c1','CTA',"Models propose, and code decides. Veil, built solo, with Muse Spark, SAM 3.1, and Muse Voice.",
  "Outro: Veil wordmark, three model chips, repo URL, footage attribution",["Models propose","Code decides"],1200,"README"),
]
words = lambda s: len(re.findall(r"[\w'’.-]+", s))
total = sum(words(x[2]) for x in L)
budget = TARGET_S * WPM / 60
beats = {}
for x in L: beats[x[1]] = beats.get(x[1], 0) + words(x[2])
read_s = total / WPM * 60 + sum(x[5] for x in L) / 1000
md = [f"# Script: Veil (2:30 judge cut)\n", f"Words: **{total}** (budget {budget:.0f} ±10% = {budget*.9:.0f}–{budget*1.1:.0f}). "
      f"Est. read time at {WPM} wpm incl. pauses: **{read_s:.0f} s**.\n", "| Beat | words | est. s |", "|---|---|---|"]
md += [f"| {b} | {n} | {n/WPM*60:.1f} |" for b, n in beats.items()]
md += ["", "| id | VO | On screen | Emphasis | Pause | Evidence |", "|---|---|---|---|---|---|"]
md += [f"| {i} | {vo} | {os_} | {', '.join(e)} | {p} ms | `{ev}` |" for i, b, vo, os_, e, p, ev in L]
md += ["", "## Alternative hooks", "- **B:** \"Here's what a stranger learns from twenty-five seconds of my street.\" (on screen: findings ticking in)",
       "- **C:** \"Blurring faces isn't enough. This clip has no face problem, and it still gives me away.\" (on screen: baseline face/plate boxes find nothing)",
       "", "## Must not say", "safe (except \"never says a video is safe\"), certified, guaranteed, private, leak-free, any competitor name, any gate PASS without 'post-gate'."]
Path('script.md').write_text('\n'.join(md) + '\n')
plan = json.loads(Path('plan.json').read_text())
plan['target_length_s'] = TARGET_S; plan['voice_mode'] = 'record_myself'; plan['music'] = 'user-provided demo/audio/music.*'
plan['phases']['1'] = 'done'; plan['phases']['2'] = 'gate'
plan['open_questions'] = ['brand logo (optional)']
plan['script'] = [dict(id=i, beat=b, text=vo, on_screen=o, emphasis=e, pause_after_ms=p, evidence=ev) for i, b, vo, o, e, p, ev in L]
Path('plan.json').write_text(json.dumps(plan, indent=1, ensure_ascii=False))
print(total, round(budget), f'{read_s:.0f}s', 'OK' if abs(total - budget) <= .1 * budget else 'OUT OF BUDGET')
