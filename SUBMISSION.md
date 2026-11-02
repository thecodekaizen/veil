# Submission: Veil (form answers, ready to paste)

Form: https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit · Deadline: Nov 4, 2026, 9:00 PM ET (Nov 5, 7:30 AM IST).
Every number below is from a committed file in this repo. Fields marked **(your call)** are your opinions: the text is a suggestion based on what happened in this build.

---

## 1. Project and team

**1. Team Name:** Veil

**2. Team Members:** (pre-filled; solo)

**3. Track:** Indie Developer

**4. Problem statement:** **Build for Your World.** Veil solves a problem creators face before every post: what in this clip gives me away?

**5. X post link (Most Viral, optional):** (your call; draft post at the end of this file)

---

## 2. Project materials

**6. Project Description**

> Veil finds what in your video could identify you, before you post it.
>
> A 25-second street clip can show a stranger your full name in a notification, your surname and flat number on a door plate, and a phone number you say out loud in Hindi. Standard redaction looks for faces, plates, screens and documents; on our test clips it found none of the four planted private details.
>
> Veil asks a different question. Muse Spark reads keyframes and proposes what in *this specific video* could identify the creator, each with a written reason. SAM 3.1 tracks every proposal through every frame. Muse Voice Transcribe hears spoken numbers in Hindi or English. Then deterministic code redacts, decodes the exported file and checks it: covers verified pixel by pixel, local OCR, a face detector, and re-transcription of the audio. A mask check uses OCR to reject masks that landed on the wrong object. Every finding ends as COVERED, UNRESOLVED or NOT_CHECKED, never "safe". A natural mode re-renders the text with fictional names instead of black boxes, and audits that file too. Discovery can also run on Muse Glimmer, Meta's open-weight model, locally, so keyframes never leave the machine.
>
> Results (3 composited test clips, fictional data): standard detection 0 of 4; Veil 11 of 12 across three full runs, then 12 of 12 after one post-gate fix. We pre-registered a pass/fail gate before any model ran. It failed, and we publish that alongside every later result. Audio timing still fails our own test.
>
> Live demo: https://thecodekaizen.github.io/veil/

**7. Public GitHub Repository URL:** https://github.com/thecodekaizen/veil

**8. 3-Minute Demo Video URL:** https://thecodekaizen.github.io/veil/video/veil-demo.mp4 (2:17). Optionally also upload it to YouTube (unlisted) and use that link, since some judges prefer a streaming player; keep the same file.

**9. Describe your use of Meta products to build the submitted project**

> Veil uses four Meta models, each for a step that a fixed rule could not do:
> - **Muse Spark 1.3** (Meta Model API, Responses with a strict JSON schema): open-vocabulary discovery. For each keyframe it proposes what could identify the creator, with a written reason and a segmentation prompt. 225 calls across three full runs, median 3.6 s.
> - **SAM 3.1** (Meta Model API, hosted video input): turns every proposal into masks tracked through the whole clip, plus reversed tracking to fix late track starts. 220 calls, median 19 s. Failed stream calls are retried explicitly and logged.
> - **Muse Voice Transcribe 1.0**: hears spoken digits in Hindi, English and Hinglish in 2-second windows. It also re-transcribes the exported audio to confirm the number is gone. 306 calls, median 1.9 s.
> - **Muse Glimmer 30B** (open weights, Apache-2.0): runs on the author's laptop via llama.cpp as a drop-in discovery provider, with the same prompt, schema and scorer, so keyframes never leave the device. On gate clip c2 it found both planted details and did not flag the decoy.
>
> Deterministic code checks every model output: schema validation, an OCR mask-vs-claim check, cover verification in the decoded output, a digit-run validator, and output re-transcription. Every call is recorded in a ledger with model, latency, usage and estimated cost (about $2.41 per 25-second clip).

**10. Why are Meta's models important to your solution?**

> Without them the product doesn't exist. What identifies a person depends on the video: a name in a notification, a door plate, a society board, a number said aloud. Our measurement: the fixed classes (face, plate, screen, document) found 0 of 4 planted details; with Muse Spark's open-vocabulary proposals Veil found 11 of 12 across three runs, and 12 of 12 after one fix. SAM 3.1 makes those proposals into pixel-accurate tracks through every frame, which is what lets Veil cover a moving door plate, not just a box on one frame. Muse Voice brings speech in Indian languages into scope. Muse Glimmer matters because this is privacy software: running discovery on open weights, on the user's own machine, means the most sensitive footage never has to be uploaded for that step. The design principle is "models propose, code decides": the Meta models do the perception, and deterministic checks decide what is reported as covered.

**11. Feedback on partner technologies (optional)**

> We did not use Baseten, Modal or Fireworks. Muse Glimmer ran locally with llama.cpp 0.8.0 on an Apple M4 Pro (24 GB): an official GGUF build and vision projector made the open-weight path straightforward. A 30B model at 3-bit swaps on 24 GB, about 9 minutes per keyframe with several timeouts, so partner-served inference would be the practical route for full runs.

---

## 3. Meta Model API feedback

**12. How likely are you to build with Meta Model API?** **(your call)**: suggested *Likely*.

**13. Overall opinion of Meta Model API?** **(your call)**: suggested *Positive*. The strict JSON schema on Muse Spark and video input to SAM 3.1 worked well. Pain points: SAM streams failing mid-response, and Voice returning turn-level timestamps only.

**14. Permission to use, publish, share and promote materials:** **(your call)** consent checkbox.

---

## 4. Developer survey (optional) (your call on all)

**15. Recommend Meta Model API (0–5):** suggested *4*.

**16. Recommend Muse Code (0–5):** we did not use Muse Code; leave it blank, or choose the lowest/"not used" option if the form forces one.

**17. Biggest obstacle:** suggested *reliability of model calls*. SAM 3.1 stream errors (13–40 failed calls per three-run set, recovered by logged retries) and Muse Voice having no word-level timestamps, which limits how precisely a spoken number can be muted.

**18. Compared with other models:** we did not run a controlled comparison against other vendors' models; answer *not compared* (or skip).

**19–20. What matters most when choosing a model:** suggested *reliability / accuracy*. Specify: "Predictable structured output, and timestamps precise enough to act on (word-level for speech)."

**21. What makes switching difficult:** suggested *integration work and re-validation*. Every provider change means re-running the evaluation; Veil's ledger and gate scorer make that measurable.

**22. What could stop production use:** suggested *latency and reliability* (SAM median 19 s and p90 about 4.5 min per call; mid-stream failures) and *data privacy* (uploading user footage). Open weights address the privacy part.

---

## Draft X post (optional, for Most Viral)

> This 25-second clip shows a stranger my name and my flat number. A face-and-plate blur misses both.
>
> I built Veil for the Meta Global AI Developer Hackathon: Muse Spark finds what identifies *you*, SAM 3.1 tracks it, Muse Voice hears the number you say, and code checks the exported file before you post. Discovery even runs on Muse Glimmer, locally.
>
> Live: thecodekaizen.github.io/veil · Code: github.com/thecodekaizen/veil

---

## Facts for judges (also in the README)

- **Built during the hackathon:** Veil code dates from commit `610a395` (Oct 28, 2026). The repository started Oct 25 with docs for an earlier idea (THREAD, in `archive/`, not used). History is not rewritten. The repo was re-homed on Nov 1 with identical commits (see the README).
- **Honest limitations:** the pre-registered gate FAILED. Post-gate results are labelled and use the same composited clips. Audio timing still fails in 3 of 3 new runs. Local OCR is macOS-only. Processing takes a median of about 18 min of model calls per clip. Hosted stages send media to Meta's API. Veil makes no privacy guarantee.
- **Demo media:** street footage CC BY-SA 3.0 (Subhashish Panigrahi, Fowler&fowler, Wikimedia Commons), composited with fictional data. Narration: Kokoro AI voice. Music: original, generated in code.
