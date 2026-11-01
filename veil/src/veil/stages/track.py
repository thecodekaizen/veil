"""Track each discovered concept through the video with SAM 3.1 (hosted video input)."""
import base64
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from veil.schemas import (Concept, DiscoverArtifact, MaskData, MaskFrame, Masklet, SkippedConcept, TrackArtifact)
from veil.stages.discover import normalize

MAX_SPARK_CONCEPTS = 10
MIN_SPARK_CONFIDENCE = 0.3
SAM_CONCURRENCY = 3


def plan(concepts: list[Concept], cap: int = MAX_SPARK_CONCEPTS) -> tuple[list[Concept], list[SkippedConcept]]:
    """Baseline concepts always run. Spark concepts run if confidence >= 0.3, best MAX_SPARK_CONCEPTS only.
    Everything else is returned as skipped with a reason (the audit marks these NOT_CHECKED)."""
    run, skipped = [], []
    spark = sorted((c for c in concepts if c.source == 'spark'), key=lambda c: -c.max_confidence)
    keep = set()
    for c in spark:
        if c.max_confidence < MIN_SPARK_CONFIDENCE:
            skipped.append(SkippedConcept(concept_id=c.concept_id, sam_prompt=c.sam_prompt, source=c.source,
                                          reason=f'confidence {c.max_confidence:.2f} < {MIN_SPARK_CONFIDENCE}'))
        elif len(keep) >= cap:
            skipped.append(SkippedConcept(concept_id=c.concept_id, sam_prompt=c.sam_prompt, source=c.source,
                                          reason=f'over cap of {cap} spark concepts (cost guard)'))
        else:
            keep.add(c.concept_id)
    run = [c for c in concepts if c.source == 'baseline' or c.concept_id in keep]
    return run, skipped


def to_masklets(concept_id: str, tracks: dict) -> list[Masklet]:
    out = []
    for track_id, frames in tracks.items():
        mf = []
        for idx in sorted(frames):
            e = frames[idx]
            box = e['box']
            mask = None
            if e['mask']:
                w, h, packed, bounds = e['mask']
                mask = MaskData(width=w, height=h, packed_b64=base64.b64encode(packed).decode(), bounds=bounds)
                box = box or list(bounds)
            if box:
                mf.append(MaskFrame(frame_idx=idx, bbox=tuple(box), mask=mask))
        if mf:
            out.append(Masklet(concept_id=concept_id, track_id=f'{concept_id}:{track_id}', frames=mf))
    return out


def run(discover: DiscoverArtifact, call_sam, frame_count: int, cap: int = MAX_SPARK_CONCEPTS) -> TrackArtifact:
    """call_sam(name, sam_prompt) -> raw tracks dict. Concepts sharing a normalized prompt run once."""
    to_run, skipped = plan(discover.concepts, cap)
    by_prompt: dict[str, list[Concept]] = {}
    for c in to_run:
        by_prompt.setdefault(normalize(c.sam_prompt), []).append(c)
    errors: list[str] = []

    def one(item):
        key, group = item
        try:
            return group, call_sam(f'track-{group[0].concept_id}', group[0].sam_prompt), None
        except Exception as exc:
            return group, None, f'{type(exc).__name__}: {str(exc)[:200]}'

    with ThreadPoolExecutor(SAM_CONCURRENCY) as pool:
        results = list(pool.map(one, by_prompt.items()))
    masklets = []
    for group, tracks, err in results:
        for c in group:
            if err:
                errors.append(f'{c.concept_id}: {err}')
                skipped.append(SkippedConcept(concept_id=c.concept_id, sam_prompt=c.sam_prompt, source=c.source,
                                              reason='SAM call failed: ' + err))
            else:
                masklets.extend(to_masklets(c.concept_id, tracks))
    notes = ('SAM 3.1 hosted video input; tracks/ids come from the model (linking="model"); confidence is null in every '
             'observed response so score is None. Concepts with the same normalized prompt share one SAM call.')
    return TrackArtifact(model_id='sam-3.1', linking='model', masklets=masklets, skipped_concepts=skipped,
                         notes=notes + (' Failures: ' + '; '.join(errors) if errors else ''))
