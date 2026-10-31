# Gate label files

One JSON file per gate clip: `gate/labels/c1.json` … `c3.json`. Schema: `gate/labels_schema.py` (pydantic, extra keys forbidden).
Labels are committed BEFORE any model runs on the clips and are never edited after the first gate run (see `gate/GATE.md`).

## Fields
- `clip_id` — clip file stem (`c1` for `gate/clips/c1.mp4`). `clip_sha256` — sha256 of the clip file (the labeller prints it). `fps` — source video fps.
- `leaks[]`
  - `leak_id` (unique in the clip), `kind` `"visual"|"audio"`, `concept` (plain words), `in_baseline` (bool: would the baseline prompts — face / license plate / phone screen / paper document — cover it?).
  - visual: `visible_ranges` `[[start_s, end_s], …]` (>= 1), `ref_boxes` `[{t_s, x, y, w, h}]` (2–3), `audio` null. Boxes are source-video pixels, top-left origin.
  - audio: `audio {text, digits (exactly 10 ASCII digits), t_start, t_end}` = the labelled spoken span in seconds; no `ref_boxes`; `visible_ranges` empty.
- `safe_controls[]` — `{control_id, description, visible_ranges, ref_boxes}` (things that look sensitive but are not: code in an editor, a book cover, a product logo).

## Workflow (about 10 minutes per 30 s clip)
```sh
# from the repo root
uv run --project veil veil label gate/clips/c1.mp4      # prints sha256, writes gate/frames/c1/labeler.html
open gate/frames/c1/labeler.html
```
In the page: add an item (visual leak / audio leak / safe control), then
- `←`/`→` step one frame (4 fps); `shift`+arrow jumps 2 s.
- Drag on the frame to record a `ref_box` for the selected item at the current time (aim for 2–3 boxes per item, spread over its visible range).
- `[` and `]` mark a visible range start/end (for an audio leak they set `t_start` / `t_end`). `u` removes the last box, `Backspace` the last range.
- Press **Export JSON**, copy the text into `gate/labels/c1.json`.

Validate (also checks the sha256 if `gate/clips/<clip_id>.mp4` exists):
```sh
uv run --project veil python -m gate.validate_labels gate/labels/c1.json
```
Clips and extracted frames are gitignored (`gate/clips/`, `gate/frames/`).

## Notes
- Audio span: label the whole spoken number from first digit onset to last digit offset (listen to the clip while stepping; the labeller is visual, so set the audio span from your waveform/player time).
- Everything must be fictional (e.g. Rohan Kulkarni, 98765 43210, "Flat 12, Sunshine CHS, Fakepur 400099").

## Example (shape only)
```json
{"clip_id": "c1", "clip_sha256": "<64 hex>", "fps": 30,
 "leaks": [
  {"leak_id": "L1", "kind": "visual", "concept": "delivery label with fictional address", "in_baseline": false,
   "visible_ranges": [[3.0, 9.5]],
   "ref_boxes": [{"t_s": 3.5, "x": 420, "y": 300, "w": 180, "h": 90}, {"t_s": 8.0, "x": 430, "y": 310, "w": 180, "h": 90}],
   "audio": null},
  {"leak_id": "A1", "kind": "audio", "concept": "spoken fictional phone number", "in_baseline": false,
   "visible_ranges": [], "ref_boxes": [],
   "audio": {"text": "nau aath saat chhe paanch char teen do ek zero", "digits": "9876543210", "t_start": 12.4, "t_end": 16.1}}],
 "safe_controls": [
  {"control_id": "C1", "description": "code in an editor", "visible_ranges": [[0, 20]],
   "ref_boxes": [{"t_s": 2.0, "x": 40, "y": 60, "w": 500, "h": 300}, {"t_s": 15.0, "x": 40, "y": 60, "w": 500, "h": 300}]}]}
```
