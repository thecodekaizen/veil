# Design SHOWME

SHOWME-specific working direction, October 28. `DESIGN_SYSTEM.md` is archived THREAD material. Existing CSS is the implementation authority for exact current tokens; these rules guide refinement.

## Prioritize the work area

Use a dark neutral workspace, readable light text and restrained green/amber/red signals. Put the camera/video or simulation scene first, the relevant action second and evidence within reach. Keep three mode tabs visible. Do not build a dashboard or generic chat screen.

Use a readable sans-serif interface face; reserve mono for times/IDs. Use clear sentence-case headings. Aim for 16px body text, 1.5 line-height and 44px touch targets. Preserve contrast and keyboard focus. Never encode status only in color.

## Give states distinct meaning

| State | Presentation |
| --- | --- |
| Candidate | “Review proposed model” and source evidence; no success checkmark |
| Current match | Name the matched state and observation time |
| Historical match | “Last matched”; explain why current state is uncertain |
| Possible difference | Amber label, evidence and uncertainty; no unsupported safety command |
| Recovery reported | Link later evidence and affected parts; do not imply independent verification |
| Simulation | Persistent “Simulated state” label; distinct border/header from camera |
| Unsupported | Explain missing evidence/mapping and offer supported next action |
| Rejected output | Show a recoverable analysis error; preserve previous trustworthy state |

## Write concrete controls

Use “Record demonstration”, “Review proposed steps”, “Use reviewed model”, “Check this frame”, “Analyze learner video”, “Inspect difference”, “Show supporting frame”, “Preview action order”, “Run simulation”, “Return to task”. Avoid “unlock”, “seamless”, “intelligent insights” and generic “Get started”.

Before paid actions, identify the file/image sent and provider. Keep routine implementation detail out of the main task instructions. Expose provenance in an expandable evidence area.

## Layout and movement

Desktop: primary work area plus a narrower task/evidence rail. Mobile: work area then current guidance; avoid dense multi-column layouts. Keep controls stable during analysis. Use short transitions for state change; honor reduced motion. Animation illustrates model output, never supplies correctness.

## Component states

Every media/action component needs empty, selected, loading, success, uncertain, error and disabled-with-reason behavior. Every overlay needs source frame/time, selected object and an empty-detection state. Camera indicators must accurately distinguish preview, recording and analysis.

See `handoff/README.md` for editable wireframes, existing concepts and actual screenshots.
