"""Phase 2 script source. Writes script.md + plan.json['script'] and checks the word budget.
Every claim cites its evidence file (ev). Run: python3 script.py"""
import json, re
from pathlib import Path

WPM = 150
TARGET_S = 135
L = [  # id, beat, VO, on_screen, emphasis, pause_after_ms, evidence  (v3: impact-first, real product, honest in one breath)
 ('h1','Hook',"This clip tells a stranger my name, my building, and my phone number.",
  "c2 input full-bleed; kinetic NAME / BUILDING / NUMBER",["name","building","phone number"],400,"runs-rep/r1/c2 input; c3 audio"),
 ('h2','Hook',"All fictional. But creators post clips like this every day, and nobody re-watches every frame.",
  "Chip: fictional data, composited clip",["every frame"],300,"gate/GATE.md (composited clips)"),
 ('i1','Impact',"In these twenty-five seconds, a full name is on screen for twenty-three seconds. A flat number, for twenty-two.",
  "Two exposure bars over the clip: name 23.3 s, flat number 22.3 s",["twenty-three","twenty-two"],400,"runs-rep/r1/c2 manifest: frames 22-603 and 47-603 at 25 fps"),
 ('p1','Problem',"Face and plate detectors flag none of it. On my test clips, a fixed list found zero of four planted leaks.",
  "Card: Face and plate detectors 0 / 4",["none of it","zero of four"],300,"eval/results/final/heldout_results.md"),
 ('p2','Problem',"Veil found three of four on its first run, and all four in two of three full re-runs.",
  "Card: Veil 3 / 4 then 4 / 4 in 2 of 3 re-runs",["all four"],500,"gate/GATE_RESULT.md; gate/repeats/r1-r3"),
 ('a1','Aha',"Here's the live product. Veil asks one question: what, in this video, could identify you?",
  "Live site hero, drag the before/after divider",["identify you"],300,"thecodekaizen.github.io/veil"),
 ('a2','Aha',"Muse Spark looks at keyframes and proposes candidates, each with a reason. The notification shows a full name. The gold plate shows a surname and a flat number.",
  "Desk: Spark evidence frames + callouts quoting the model's why text",["Muse Spark","reason"],250,"runs-rep/r1/c2 discover.json why_identifying"),
 ('a3','Aha',"SAM 3.1 tracks each one through every frame, and the export covers exactly those regions.",
  "Desk: click a track, covers follow in the export",["SAM 3.1","every frame"],300,"track_final.json; redact.json"),
 ('f1','Verify',"Then code checks the work. Veil decodes its own export and verifies the cover on every masked frame.",
  "Desk findings: cover verified in decoded output on all 557 masked frames",["checks the work"],300,"runs-rep/r1/c2 audit.json"),
 ('f2','Verify',"Models make mistakes. Here, SAM put the name mask on a block of code.",
  "Mask check: REJECTED rows",["mistakes"],200,"runs-rep/r1/c2 verify.json"),
 ('f3','Verify',"Local OCR read the mask, found code instead of the name Spark claimed, and threw it out.",
  "OCR text 'def total(items)' vs claimed 'KULKARNI'",["threw it out"],400,"runs-rep/r1/c2 verify.json rejected x3"),
 ('n1','Natural',"And if black boxes ruin the shot, switch to natural. Veil re-renders the text with fictional names, then runs the same OCR audit to check the real ones are gone.",
  "Desk: Covers to Natural toggle; divider across the notification: Rohan Kulkarni becomes Aarav Sharma, KULKARNI 12 becomes SHARMA 87",["natural","fictional names"],400,"runs-rep/r1/c2 natural.json (audit COVERED, 0 residual words)"),
 ('v1','Voice',"Spoken numbers too. Muse Voice Transcribe hears a phone number said in Hindi. Veil mutes it, then transcribes the export again to confirm.",
  "Desk c3: Devanagari transcript, mute bar, COVERED spoken number",["Hindi","mutes it"],400,"runs-rep/r1/c3 listen.json, audit.json"),
 ('g1','Open weights',"Discovery can also run on open weights. Muse Glimmer runs right on this laptop, so for this step the frames never leave the device. On this clip it found both leaks, and left the code panel alone.",
  "Glimmer: llama-server on the laptop, its proposals on c2 keyframes",["open weights","never leave","both leaks"],400,"runs-glimmer/c2s; gate/glimmer; eval/glimmer/summary.md"),
 ('r1','Payoff',"Every finding ends as covered, unresolved, or not checked. Veil never gives a clean bill of health. It shows you what's left to review.",
  "Desk verdict banner and Unresolved filter",["what's left to review"],300,"runs-rep/r1/c2 audit.json"),
 ('e1','Evidence',"And I measured it: three full re-runs with every check on, seven hundred and fifty-one logged model calls, about two dollars forty per clip. The full results, including what still fails, are in the repo.",
  "Live site: ledger, then results table",["measured it","what still fails"],400,"eval/repeats/summary.json; gate/"),
 ('c0','CTA',"Try it live, read the receipt, and decide before you post.",
  "Live site final CTA, URL chip",["decide"],300,"thecodekaizen.github.io/veil"),
 ('c1','CTA',"Veil. Models propose. Code decides.",
  "Outro: wordmark, model chips, URLs, credits",["Code decides"],1200,"README"),
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
