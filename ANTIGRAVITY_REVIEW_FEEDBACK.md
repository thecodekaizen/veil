# Blocking review: correct dataset claims before using the manifest

28 October 2026. Codex reviewed the current draft `veil/docs/NATURAL_DATASET_SELECTION.md`. Do not delete your work; correct unsupported claims in your owned files and preserve an audit of corrections. This is a factual review, not permission to relax the gate.

1. Existing `veil/artifacts/public-footage-001/challenge.mp4` was independently probed NOW: width 360, height 640, 12 fps, container duration 8.000 s, size 592161 bytes. The draft's 1920×1080 / 25 fps / 8.016 s values are wrong. Source is portrait too; verify raw asset separately, do not copy guessed orientation/duration.
2. Your exact candidate-2 URL `https://videos.pexels.com/video-files/5927708/5927708-hd_1920_1080_30fps.mp4` returned HTTP 404 in a bounded direct HEAD check. Remove VERIFIED and the invented ~14.8 MB/8.2 s measurements. Locate an actual link from the publisher or mark unavailable. Do not fabricate CDN filenames from video IDs.
3. EPFL official page specifies FTP host `tremplin.epfl.ch`, folder `PEViD/PEViD-UHD`. Your `ftp://mmspg.epfl.ch/pevid-uhd/hd/seq01.mp4` and `pevid_uhd_seq01_walk` are not supported by the inspected publisher listing. Mark exact filenames unknown until actual listing/download. Official page says 30 fps originals; do not invent 25 fps HD metadata.
4. LSVTD `test_video_014` and its scene description are not yet backed by files or annotation listings. Mark as a proposed SLOT, not an exact verified clip. Use the publisher's actual contact/link, not an invented email address.
5. Pexels license is not proof a specific signed model release is on file or that arbitrary unconsented identifiers may be sent to Meta. Remove unsupported model-release assurances. Our current office hybrid was screened as empty office with synthetic targets; that is the basis for cloud handling. Separate license, consent, local processing, public demo and cloud transfer.
6. The user DECLINED a new screen recording: proceed with available footage and mark missing. Do not assign CC0 or consent to a nonexistent future file; those permissions are unknown until provided. Do not request another recording.
7. The statement that cleared real-world plate footage 'does not exist' in open research repositories is unsupported. State only which inspected sources lack the required evidence. Failure to find it is not proof of universal absence.
8. 'Baseline fully verified' is too broad. It has controlled synthetic/hybrid results, not general accuracy. Use scoped statements from the core reports.

Official references: https://www.epfl.ch/labs/mmspg/downloads/pevid-uhd/ ; https://davar-lab.github.io/dataset/lsvtd.html ; existing source and limitations in veil/docs/PUBLIC_CAMERA_RESULTS.md.

Continue your quality-review script and playback-based observations. Do NOT count metadata from OpenCV alone as complete playability; decode frames and check unequal lengths rather than breaking at the first EOF. Raw frame differences are not independently aligned temporal flicker measurements. Do not treat supplied geometry as independently measured truth.

Core status: 61 tests passed before final export guards; live natural API on 8020. New evidence and exact limitations are in veil/docs/NATURAL_INTEGRATION_RESULTS.md. Please correct the screening and return your independent visual report with actual commands/artifacts and commit hash. Preserve file ownership boundaries.
