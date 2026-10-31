# Proof-of-magic recording card

**Purpose:** Prepare one small, private, repeatable video experiment for the SHOWME CLI. This is not product UI and not a demo claim.

## Task

Use a mug and a coaster (or a stiff, high-contrast card larger than the mug base). Mark a target area on a plain tabletop with a sheet of paper. The demonstrated end state is the coaster on the target and the mug resting on the coaster. Keep the coaster visibly wider than the mug so the layer can be seen in an overhead view.

This task is intentionally tiny. It tests whether the model can track a visible relation and recognize a correction. It does **not** establish general physical understanding or prove that one observed action order is universally required.

## Record three uncut clips

Use a fixed overhead or high-angle camera. Show only the hands and work surface. Keep all objects in frame, use good light, and pause for two seconds at each important state. No narration, on-screen labels, or edits for this first visual-only test.

1. **Demonstration:** Start with the mug and coaster apart. Place the coaster on the marked target, then put the mug on it. End with hands away and the full stack visible.
2. **Correct attempt:** Reset to the same initial state, but move the mug and coaster to different starting positions. Perform the same task and pause on the final state.
3. **Mistake and recovery:** Reset again. Put the mug directly on the target without the coaster and hold that state for two seconds. Then lift the mug, place the coaster on the target, replace the mug, and hold the corrected state for two seconds.

Aim for 8–20 seconds per clip. Keep the camera position and target fixed; only starting object positions should change in the correct attempt.

## Before any model call

Create a separate local answer key from your own recordings. Do this before looking at any model output. The key is for scoring only and must never be sent to Muse or saved in run artifacts.

Use neutral clip IDs (for example, `clip-a.mp4`, `clip-b.mp4`, `clip-c.mp4`). Do not put words such as `correct`, `error`, or `recovery` in filenames. Keep the ID-to-condition mapping in the private answer key.

For each clip, write down:

- the visible starting state;
- the action and resulting state;
- for the mistake clip, the incorrect relation and the recovery action;
- the approximate time when each state is visible.

**Acceptance checks:** all three clips are continuous; the coaster/mug relationship is visible; the correct attempt uses changed starting positions; the mistake is visibly distinct and followed by an unmistakable recovery; the private answer key is saved before model inference.

## Privacy and files

Keep recordings, the answer key, extracted frames, and raw model responses outside Git. If you share clips for analysis, hands-only framing is preferred. Never record faces, private documents, screens, or unrelated personal material.
