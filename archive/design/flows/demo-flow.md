# SHOWME three-minute demo plan

**Goal:** make the Teach → Do → Simulate loop understandable through one physical task, while showing only behavior that survives the evaluation in [`SHOWME_BUILD_PLAN.md`](../../docs/SHOWME_BUILD_PLAN.md).

**Current status:** this is a recording plan, not a validated capability claim. Physical-task footage and evaluation are still pending. The current app's Do observations are explicit snapshots or analysis of a separate recording; it does not continuously track or intervene live. Current Simulate is a deterministic procedural state preview, not geometry/physics simulation.

## Final cut, if every gate passes

| Time | Picture / action | Spoken line / purpose |
|---|---|---|
| 0:00–0:12 | Open on a real learner workspace. Let the task fill frame. | “Tutorials can show you what to do. They can’t see what you’re doing.” |
| 0:12–0:35 | Show a short expert demonstration, then SHOWME's candidate process model with a few timestamped evidence links. | “Show it once. SHOWME proposes the parts, actions, and states it observed. The expert reviews what the clip supports.” |
| 0:35–0:55 | Switch to the separate learner attempt. Show a correct state accepted with its cited frame. | “Now a different attempt. This state matches the reviewed model.” Only say this after the matched control is accepted in repeated runs. |
| 0:55–1:30 | Show the deliberate mistake in the actual workspace, then the matching paused clip frame and SAM overlay if validated. | “Here the learner diverges. SHOWME points to the relevant part and explains the evidence.” Never imply SAM proves the process error. |
| 1:30–1:52 | Show the recovery clip and the later state check/event. | “The learner corrects it. SHOWME recognizes the state is back on a valid path.” Include only after the separate recovery run passes without answer-key leakage. |
| 1:52–2:30 | Enter Simulate from the same skill. Change one bounded action, step through the task-specific visual result, compare with reference, then return to Do. | “What if I put this part on first? The same Skill Model drives this alternate sequence.” State the known constraint's provenance. |
| 2:30–2:48 | Briefly show evidence/provenance and model boundary. | “The model separates what the clip showed from what remains a hypothesis. This is one constrained task, not general physics.” |
| 2:48–3:00 | End on the live physical task and SHOWME name/tagline. | “SHOWME captures human know-how, so another person can learn by doing.” |

## Current-prototype fallback

If live state tracking or recovery has not passed, keep the demo honest and still show the product loop:

1. Show Teach recording/upload, the real inference call, and human review of the candidate with its evidence. Label model output as a proposal.
2. In Do, explicitly select **Observe attempt** on the separate learner clip. Show the returned events and timestamps beside the source footage. Describe them as model-reported observations until evaluated against the independent answer key.
3. If a difference is reported, seek to its timestamp. Use **Find … in frame** only if the task footage confirms that the SAM overlay selects the intended object; otherwise show the raw frame and disclose that object finding is not yet validated.
4. Show a recovery classification only if the matched recovery clip passes the blind evaluation. Otherwise use the time to show an uncertainty or missed detection and explain the limitation.
5. Simulate may be shown as a procedural preview only. Label the current stacked-mount scene as an illustrative fixture. Do not call it physical simulation or claim its constraint was learned from video.
6. Close with the concrete next proof: demonstrate, compare a correct attempt, catch one recoverable mistake, and observe recovery using the same selected physical task.

The fallback is a prototype walkthrough, not a substitute claim that the two hero moments already work.

## Recording checklist

- Capture screen and workspace together for the critical mistake/recovery sequence so the source video, app evidence, and physical outcome can be compared.
- Start from a clean browser session and the same reviewed Skill Model. Keep learner clips B, C, and D separate; use neutral filenames and never expose the human labels to model calls.
- Preserve raw requests, model outputs, usage, latency, and the independent scorecard outside the public repo. Use only consented footage cleared for public release.
- Prefer one continuous take for the physical mistake and correction. Editing may improve pacing, but must not hide an incorrect model response or present a staged overlay as model output.
- Rehearse the chosen cut twice from a clean start. Confirm total runtime is under three minutes and every spoken capability statement has a matching evaluation result.

## Demo gates

- **Teach:** candidate has timestamped evidence, a human-reviewed model, and visible distinction between observation and proposed dependency.
- **Do:** same skill accepts the matched correct attempt, detects the deliberately withheld divergence with cited evidence, and reports no unsupported certainty.
- **Grounding:** SAM selects the right object/location in repeated selected-task frames; otherwise omit the overlay.
- **Recovery:** the model recognizes the separately recorded recovery without access to its label.
- **Simulate:** same reviewed Skill Model; deterministic repeatable alternate; rendered state matches the simulator output; every enforced constraint has a disclosed source. Do not present the current fixture as task-specific geometry.

If a gate fails, cut that capability or state the limitation on screen. Do not hide a failure behind UI polish or editing.
