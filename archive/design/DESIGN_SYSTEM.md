> For current SHOWME work, read [SHOWME_DESIGN_SYSTEM.md](SHOWME_DESIGN_SYSTEM.md) and [the handoff wireframes](handoff/README.md).

# THREAD visual direction (Day 0)

> **Archived pre-pivot direction:** these visual choices describe THREAD, not SHOWME. SHOWME screen behavior is outlined in [`../docs/SHOWME_APP_PLAN.md`](../docs/SHOWME_APP_PLAN.md). Define a separate visual system after the P0 task and evidence vocabulary stabilize.

## Direction

A living research journal and intelligence map: calm, editorial, evidence-forward, temporal. The AI should feel like it is discovering and investigating, not chatting or announcing verdicts. Avoid generic SaaS card grids, purple AI gradients, and a Notion-like workspace.

## Principles

- Put time and source evidence in the visual hierarchy.
- Use whitespace and typography to make a few meaningful findings feel considered.
- Distinguish source, model hypothesis, counter-evidence, and user-confirmed insight through consistent labels and shapes, not color alone.
- Make connections visible but never more prominent than their supporting evidence.
- Keep uncertainty calm and legible; avoid badges that imply scientific certainty.

## Initial visual hypothesis

Use a warm paper-like neutral base, dark ink text, and one restrained accent for active inquiry, with a distinct secondary signal for counter-evidence. Favor editorial serif display typography paired with a highly legible sans-serif interface face; use a mono face sparingly for dates and provenance. Fine rules, timeline marks, and restrained node/connection motifs can carry the intelligence-map feel. Confirm actual tokens, typefaces, and contrast after the first mockup.

## Hackathon UI constraint

The pre-event board is a visual reference only. Keep the implementation focused on the discovery/investigation workflow; do not make a dashboard the main feature. Lead with one specific project evolution claim and its evidence, then let the creator inspect and challenge it. Charts and archive coverage are supporting context, not the product.

## Interaction cues

- Discovery is an invitation to inspect, not an answer card.
- Evidence opens to source context with date and modality.
- Timeline position communicates sequence; do not rely on color alone.
- Interview feels like a focused reflective prompt, not a general chat surface.
- Confirmed insights receive a clear, human-authored status marker.

## Mockup workflow

Store approved visual references in `mockups/` using numbered, descriptive names. Add a short note for each with intended viewport and key behavior. Update this file with concrete tokens only after the direction is visible and reviewed.

## First visual reference

See [`mockups/00-thread-direction-board.png`](mockups/00-thread-direction-board.png), a six-screen concept board covering Discover, Thread Detail, Evidence Timeline, ECHO investigation, Interview, and Developed Insight. Treat it as a direction-setting reference, not a pixel-perfect production spec; generated UI copy and sample data are illustrative.

### Visible tokens to carry forward

- Canvas: warm ivory; primary text: near-black ink.
- Primary action and active states: deep forest green.
- Counter-evidence: muted terracotta, paired with an explicit text label.
- Display headings: editorial serif; controls and body: readable sans-serif; dates/provenance: restrained monospaced styling.
- Use hairline separators, spacious margins, quiet source metadata, and thin temporal plots.
- Evidence should appear as dated fragments with source type and a path back to the original item.
- Distinguish supporting and counter-evidence with both color and words.

### Screen hierarchy shown in the board

Discover gives the archive timeline and one featured hypothesis the most space. Thread Detail foregrounds the interpretation and its evolution over time. Evidence Timeline makes chronology and opposing evidence inspectable. ECHO keeps the hypothesis visible while inviting challenge. Interview gives one grounded question room to breathe. Developed Insight separates the confirmed interpretation, takeaways, and one artifact.
