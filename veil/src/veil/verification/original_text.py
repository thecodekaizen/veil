"""Check original identifiers in independently decoded export OCR, not edit metadata."""
import hashlib
import re
from pathlib import Path
from veil.verification.ocr import inspect_text


def normalized_text(value):
    return ''.join(c for c in value if c.isalnum()).upper()


def original_matches(rows, identifiers, minimum_fragment=4):
    if minimum_fragment < 4:
        raise ValueError('Fragments below four characters are not meaningful privacy tests')
    values=[normalized_text(v) for v in identifiers]
    if not values or any(len(v)<minimum_fragment for v in values):
        raise ValueError('Supply original identifiers with at least four characters')
    hits=[]
    for row in rows:
        observed=normalized_text(row['text'])
        for index,value in enumerate(values):
            fragments=sorted({value[i:i+minimum_fragment] for i in range(len(value)-minimum_fragment+1)} &
                             {observed[i:i+minimum_fragment] for i in range(max(0,len(observed)-minimum_fragment+1))})
            if fragments:
                hits.append({'time_ms':row['time_ms'],'original_identifier_index':index,
                    'full_identifier':value in observed,'matching_fragments':fragments,'observed_text':row['text']})
    return hits



def short_numeric_warnings(rows, identifiers):
    """Do not quietly clear a visible 2–3 digit fragment just because it is short.

    These may be unrelated numbers: require review, not a claim of proven leak.
    """
    warnings=[]
    for row in rows:
        for token in re.findall(r'(?<!\d)\d{2,3}(?!\d)',row['text']):
            for index,value in enumerate(identifiers):
                if token in normalized_text(value):
                    warnings.append({'time_ms':row['time_ms'],'original_identifier_index':index,
                        'possible_numeric_fragment':token,'observed_text':row['text']})
    return warnings


def audit_original_text(export: Path, frames, identifiers, width, height, cache: Path):
    # Caller supplies separately decoded exported frames; no masks or renderer decisions.
    ocr=inspect_text(frames,width,height,cache,include_text_rows=True)
    hits=original_matches(ocr.get('text_rows',[]),identifiers)
    short=short_numeric_warnings(ocr.get('text_rows',[]),identifiers)
    report={'export_sha256':hashlib.sha256(export.read_bytes()).hexdigest(),
        'status':'review_incomplete' if ocr['status']!='completed' else
                 ('residual_observed' if hits else ('possible_short_fragment_requires_review' if short else 'no_original_identifier_observed_in_checked_frames')),
        'frames_checked':len(frames),'full_identifier_recovered_frames':len({r['time_ms'] for r in hits if r['full_identifier']}),
        'residual_findings':hits,'possible_short_numeric_fragments':short,'needs_manual_review':True,
        'auditor_version':'original-text-v2-short-numeric-review',
        'scope':'Local independent OCR on supplied exported frames, normalized planted values and contiguous four-character fragments. Short numeric matches require review; single-character leakage is not ruled out. Not proof against all recovery methods.'}
    return report,ocr



def audit_export_text(export: Path, identifiers, root: Path, cache: Path, max_frames=512):
    """Decode the exact export internally; never accept a caller's substitute frames."""
    import cv2
    from veil.providers.common import save
    original_matches([],identifiers)  # Validate supplied values before processing media.
    root.mkdir(parents=True,exist_ok=False)
    cap=cv2.VideoCapture(str(export))
    if not cap.isOpened():raise ValueError('Cannot open exported video for audit')
    frames=[];fps=cap.get(cv2.CAP_PROP_FPS)
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps<=0:cap.release();raise ValueError('Invalid exported frame rate')
    try:
        while True:
            ok,image=cap.read()
            if not ok:break
            if len(frames)>=max_frames:raise ValueError('All-frame audit budget exceeded; no silent sampling')
            path=root/f'frame-{len(frames):05}.png'
            if not cv2.imwrite(str(path),image):raise ValueError('Cannot save export audit frame')
            frames.append((round(len(frames)/fps*1000),path))
    finally:cap.release()
    if not frames:raise ValueError('Export has no decoded frames')
    try:
        report,ocr=audit_original_text(export,frames,identifiers,width,height,cache)
    except Exception as exc:
        report={'export_sha256':hashlib.sha256(export.read_bytes()).hexdigest(),
                'status':'review_incomplete','frames_checked':0,'residual_findings':[],
                'error_type':type(exc).__name__,'needs_manual_review':True}
        ocr={'status':'failed','error_type':type(exc).__name__}
    report.update(frame_count=len(frames),sample_times_ms=[t for t,_ in frames],sampling='every_decoded_frame')
    save(root/'ocr.json',ocr);save(root/'report.json',report)
    return report
