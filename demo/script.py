"""Phase 2 script source. Writes script.md + plan.json['script'] and checks the word budget.
Every claim cites its evidence file (ev). Run: python3 script.py"""
import json, re
from pathlib import Path

WPM = 150
TARGET_S = 125
L = [  # v4: story-first (STORYBOARD_v4.md). id, beat, VO, on_screen, emphasis, pause_after_ms, evidence
 ('h1','Hook',"This street clip is about to be posted.",
  "c2 playing; About to be posted.",["about to be posted"],250,"runs-rep/r1/c2 input"),
 ('h2','Hook',"It shows a stranger my full name, and my flat number.",
  "amber boxes on the notification and door plate",["full name","flat number"],400,"runs-rep/r1/c2 redact.json boxes"),
 ('x1','Contrast',"A standard redaction tool looks for faces and plates. It covers one car's plate, and misses both.",
  "real standard-class export of the same run",["faces and plates","one car's plate","misses both"],600,"runs-rep/r1/c2/output_fixed_classes.mp4"),
 ('o1','One line',"Veil finds what identifies you in this specific video. Not just faces and plates. Then it covers it, before you post.",
  "Veil wordmark; side by side standard vs Veil",["this specific video","covers it"],1500,"runs-rep/r1/c2 output.mp4"),
 ('l1','Live',"Here's the live product. Drag across, and see exactly what changed.",
  "live site hero: divider dragged across input vs export",["live product"],500,"thecodekaizen.github.io/veil"),
 ('a2','Find',"Muse Spark reads the clip, and proposes what could identify you, with a reason.",
  "desk: Spark boxes + verbatim reason",["Muse Spark","with a reason"],1700,"runs-rep/r1/c2 discover.json"),
 ('a3','Find',"SAM 3.1 tracks each one, through every frame.",
  "desk tracks panel",["SAM 3.1","every frame"],1300,"runs-rep/r1/c2 track_final.json"),
 ('v1','Listen',"It listens, too. Muse Voice hears a phone number said in Hindi, and Veil mutes it.",
  "desk c3: transcript, mute bar",["Hindi","mutes it"],400,"runs-rep/r1/c3 listen.json, redact.json"),
 ('v2','Listen',"Then it transcribes the export again, to confirm.",
  "findings: COVERED spoken phone-like number (re-transcription found no digit run)",["confirm"],1500,"runs-rep/r1/c3 audit.json"),
 ('au','Audit',"Then Veil audits its own export.",
  "desk verdict banner",["audits"],250,"runs-rep/r1/c2 audit.json"),
 ('au2','Audit',"Five items covered. Two left for you to review.",
  "verdict: 5 COVERED, 2 UNRESOLVED, 0 NOT CHECKED",["Five items covered","Two left"],450,"runs-rep/r1/c2 audit.json"),
 ('f3','Audit',"It reads every mask with OCR. Here, SAM grabbed a code panel, so Veil threw that mask out.",
  "mask check: REJECTED row",["threw that mask out"],1700,"runs-rep/r1/c2 verify.json"),
 ('r1','Audit',"Every finding ends covered, unresolved, or not checked. Never a blanket all clear.",
  "findings, Unresolved filter",["unresolved","all clear"],350,"runs-rep/r1/c2 audit.json"),
 ('n1','Audit',"Prefer no black boxes? Natural mode swaps in fictional names, and runs the audit again.",
  "desk Natural toggle",["fictional names"],1300,"runs-rep/r1/c2 natural.json"),
 ('p1','Proof',"I planted four private details across three test clips. Standard detection found none.",
  "proof card: test set; standard 0 of 4",["four private details","found none"],300,"eval/results/final/heldout_results.md"),
 ('p2','Proof',"Over three full runs, Veil found eleven of twelve. One run missed a parcel label, and its audit didn't catch it.",
  "stat hit: 4/4, 3/4, 4/4 cells; the miss outlined",["eleven of twelve","didn't catch it"],350,"gate/repeats/r1-r3; runs-rep/r2/c1 audit.json"),
 ('p2b','Proof',"After one fix to the mask check, three new runs found all twelve. Audio timing still fails my own test.",
  "stat hit: post-gate v2 row 12 of 12; audio caveat",["all twelve","still fails"],450,"gate/repeats-v2; eval/repeats-v2/summary.md"),
 ('p3','Proof',"Every model call is logged: seven hundred and fifty-one calls, about two dollars forty per clip.",
  "live site ledger",["logged"],450,"eval/repeats/summary.json"),
 ('g1','Open weights',"Discovery also runs on Muse Glimmer, right on this laptop. The frames never leave it.",
  "Glimmer card",["Muse Glimmer","never leave it"],900,"runs-glimmer/c2s; eval/glimmer/summary.md"),
 ('g2','Open weights',"On this clip it found both details, and left the code panel alone.",
  "Glimmer card result line",["both details"],500,"gate/glimmer; eval/glimmer/summary.md"),
 ('c1','Close',"Veil. Find what identifies you, before you post.",
  "end on the after frame, wordmark, URLs",["before you post"],1300,"README"),
 ('c2','Close',"Try it live, at the link below.",
  "URLs on the after frame",["Try it live"],1500,"thecodekaizen.github.io/veil"),
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
