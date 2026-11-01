# Submission: VEIL

- **Title:** VEIL, an identity-leak audit for creator videos
- **Category:** Indie Developer / Build for Your World
- **Pitch:** Spark finds what in *your* video could identify you, SAM 3.1 tracks it, Voice hears the spoken phone number, deterministic code redacts and then re-checks the exported file, and says plainly what stays UNRESOLVED.
- **Problem:** Creators filming street or delivery content leak names, address labels, notification banners and spoken numbers. Fixed-class redaction tools (faces, plates) do not know what is identifying in *this* video; on our held-out clips a fixed face/plate/phone/document baseline found 0/4 planted leaks.
- **Meta models:** Muse Spark 1.3 (open-vocabulary discovery with reasons), SAM 3.1 (video mask tracking, also reversed tracking for track-start fixes), Muse Voice Transcribe (spoken digits, Hindi/English). Each carries a capability; see EVALUATION.md section 2. Open-weight (Spark Open): **not used, no bonus claim.**
- **Novelty:** per-video open-vocabulary identity-leak discovery + output re-check with independent local OCR/face detection + abstention (COVERED / UNRESOLVED / NOT_CHECKED) + receipts. Not claimed: that no competing product exists (Sighthound, Motion DSP, SecuRedact, YouTube Custom Blurring do detect/track/blur).
- **Architecture:** Python 3.12 / FastAPI / pydantic stages writing JSON artifacts (keyframes -> discover -> track -> extend -> [verify] -> listen -> redact -> audit -> report), React static demo UI.
- **Engineering contribution (during hackathon, from 2026-10-28):** the whole `veil/` engine, gate and eval harness, post-gate verify and voiced-refine stages. Repo history starts 2026-10-25 with THREAD docs/experiments (not used by Veil; in `archive/`). Flag for organizer clarification.
- **Impact:** privacy for creators; unvalidated with real users.
- **Honest limitations:** frozen gate FAIL (G2, G4b); post-gate fixes narrow and labelled; G4b still failing; clips composited; macOS-only local OCR; cloud processing (media is sent to Meta); no certification claim.
- **Repository URL:** https://github.com/thecodekaizen/veil (remote configured; **public visibility not verified**)
- **Deployment URL:** NOT AVAILABLE (not deployed)
- **Demo URL:** NOT AVAILABLE (video not recorded)
