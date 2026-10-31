"""Bounded local natural editing: observe source, render, audit export, fallback.

No API accepts a server asset path or per-frame replacement geometry. Templates
are generated locally once; user seeds or contour candidates initialize LK.
"""
import os
from pathlib import Path
from typing import Literal
import cv2
import numpy as np
from pydantic import Field
from veil.core.models import StrictModel, FiniteFloat, Timeline
from veil.media.surface import SurfaceReplacement, perspective
from veil.media.surface_tracking import track_surface
from veil.media.redact import render
from veil.media.inspect import decode_export
from veil.verification.original_text import audit_export_text, normalized_text
from veil.providers.common import save


class SurfaceSeed(StrictModel):
    track_id: str = Field(min_length=1,max_length=100)
    start_frame: int = Field(default=0,ge=0)
    corners: list[tuple[FiniteFloat,FiniteFloat]] | None = Field(default=None,min_length=4,max_length=4)
    kind: Literal['plate','screen','document'] = 'plate'
    original_identifiers: list[str] = Field(min_length=1,max_length=16)


class NaturalRequest(StrictModel):
    media_is_synthetic_or_consented: Literal[True]
    timeline: Timeline | None = None
    surfaces: list[SurfaceSeed] = Field(min_length=1,max_length=8)


def validate_request(request, timeline, media):
    if len({s.track_id for s in request.surfaces})!=len(request.surfaces):
        raise ValueError('Use one seed per track')
    tracks={t.id:t for t in timeline.visual_tracks}
    if len(tracks)!=len(timeline.visual_tracks):raise ValueError('Track IDs must be unique')
    count=round(media['duration_ms']*media['fps']/1000)
    if count>512:raise ValueError('Natural pilot requires at most 512 frames for all-frame local audit')
    if count*media['width']*media['height']>256_000_000:
        raise ValueError('Natural pilot exceeds bounded decoded-pixel audit budget')
    for s in request.surfaces:
        if s.track_id not in tracks:raise ValueError('Seed must name an existing protective track')
        track=tracks[s.track_id]
        if track.category not in ('license_plate','phone_number') or track.action!='cover':
            raise ValueError('Natural replacement requires a plate/text cover track')
        if s.kind=='plate' and track.category!='license_plate':raise ValueError('Plate template requires a plate track')
        if not any(r.frame==s.start_frame for r in track.regions):raise ValueError('Seed is outside protective track lifetime')
        if len({r.frame for r in track.regions})!=len(track.regions):raise ValueError('Repeated protection frame')
        if any(not 4<=len(normalized_text(v))<=128 for v in s.original_identifiers):
            raise ValueError('Original identifiers must normalize to 4–128 characters')
        if s.corners is not None:perspective(s.corners,(280,84),(media['width'],media['height']))


def contour_corners(image, box):
    """A geometric proposal inside a protective region, never a privacy verdict."""
    h,w=image.shape[:2];x1,y1,x2,y2=box
    x1,y1=max(0,int(x1)),max(0,int(y1));x2,y2=min(w,int(np.ceil(x2))),min(h,int(np.ceil(y2)))
    crop=image[y1:y2,x1:x2]
    if not crop.size:return None
    gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    edges=cv2.Canny(cv2.GaussianBlur(gray,(3,3),0),50,150)
    contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    candidates=[]
    for contour in contours:
        polygon=cv2.approxPolyDP(contour,.025*cv2.arcLength(contour,True),True)
        if len(polygon)!=4 or cv2.contourArea(polygon)<crop.shape[0]*crop.shape[1]*.25:continue
        points=polygon.reshape(4,2).astype(np.float32)+[x1,y1]
        center=points.mean(axis=0);points=points[np.argsort(np.arctan2(points[:,1]-center[1],points[:,0]-center[0]))]
        points=np.roll(points,-np.argmin(points.sum(axis=1)),axis=0)
        try:perspective(points,(280,84),(w,h))
        except ValueError:continue
        candidates.append(points)
    return max(candidates,key=lambda p:cv2.contourArea(p.astype(np.float32))).tolist() if candidates else None


def make_asset(path, kind, corners):
    points=np.asarray(corners,dtype=float) if corners is not None else np.array([[0,0],[280,0],[280,84],[0,84]])
    horizontal=(np.linalg.norm(points[1]-points[0])+np.linalg.norm(points[2]-points[3]))/2
    vertical=(np.linalg.norm(points[3]-points[0])+np.linalg.norm(points[2]-points[1]))/2
    ratio=float(np.clip(horizontal/max(vertical,1),.35,5))
    width=420;height=int(np.clip(round(width/ratio),84,900))
    color=(225,230,232) if kind!='screen' else (42,39,33)
    image=np.full((height,width,3),color,np.uint8)
    cv2.rectangle(image,(3,3),(width-4,height-4),(95,95,95),2)
    words=['DEMO'] if kind=='plate' else ['PRIVATE','DEMO']
    for i,word in enumerate(words):
        scale=min(1.6,width/(len(word)*27));size=cv2.getTextSize(word,cv2.FONT_HERSHEY_SIMPLEX,scale,2)[0]
        y=int(height*(i+1)/(len(words)+1)+size[1]/2)
        cv2.putText(image,word,((width-size[0])//2,y),cv2.FONT_HERSHEY_SIMPLEX,scale,
                    (28,28,28) if kind!='screen' else (210,220,225),2,cv2.LINE_AA)
    if not cv2.imwrite(str(path),image):raise ValueError('Cannot write replacement asset')
    return ' '.join(words)


def quality_review(source, output, timeline):
    a=cv2.VideoCapture(str(source));b=cv2.VideoCapture(str(output));rows=[];black=[]
    regions={}
    for track in timeline.visual_tracks:
        for r in track.regions:regions.setdefault(r.frame,[]).append(r.box)
    try:
        i=0
        while True:
            oa,fa=a.read();ob,fb=b.read()
            if oa!=ob:raise ValueError('Source/output frame counts differ')
            if not oa:break
            mask=np.zeros(fa.shape[:2],np.uint8)
            for x1,y1,x2,y2 in regions.get(i,[]):
                cv2.rectangle(mask,(max(0,int(x1)-28),max(0,int(y1)-28)),
                    (min(fa.shape[1]-1,int(np.ceil(x2))+28),min(fa.shape[0]-1,int(np.ceil(y2))+28)),255,-1)
            outside=mask==0
            diff=float(np.abs(fa.astype(float)-fb)[outside].mean()) if outside.any() else None
            is_black=float((fb.max(axis=2)<40).mean())>.95
            if is_black:black.append(i)
            rows.append({'frame':i,'outside_protective_region_mean_absolute_difference':diff})
            i+=1
    finally:a.release();b.release()
    values=[r['outside_protective_region_mean_absolute_difference'] for r in rows if r['outside_protective_region_mean_absolute_difference'] is not None]
    return {'status':'review_required','frames_checked':len(rows),'near_full_frame_blackouts':black,
        'outside_region_difference_mean_0_255':float(np.mean(values)) if values else None,
        'frame_diagnostics':rows,'blinded_preference':'not_run','needs_human_review':True,
        'limitations':['Mask-derived exclusion region is a utility diagnostic, not independent localization truth',
            'Re-encoding changes background pixels','No automated beauty or flicker acceptance is asserted']}


def execute_natural(root, request, timeline, media):
    """Called under the existing per-job lock; returns a candidate for promotion."""
    source=root/'input.mp4';work=root/'natural';work.mkdir(exist_ok=False)
    cache=Path(os.getenv('VEIL_OCR_CACHE','artifacts/private/ocr-cache'))
    values=[value for s in request.surfaces for value in s.original_identifiers]
    owners=[s.track_id for s in request.surfaces for _ in s.original_identifiers]
    source_check=audit_export_text(source,values,work/'source-check',cache)
    save(work/'source-check.json',source_check)
    report={'status':'review_required','source_check':source_check,'needs_human_review':True,
        'general_privacy_audit':'not_run','cloud_calls':0,'additional_api_cost_usd':0}
    observed={hit['original_identifier_index'] for hit in source_check['residual_findings'] if hit['full_identifier']}
    if source_check['status']=='review_incomplete' or observed!=set(range(len(values))):
        report['reason']='Source OCR must independently observe every supplied full identifier before targeted export clearance'
        save(work/'report.json',report);return None,report
    tracks={t.id:t for t in timeline.visual_tracks};plans=[];tracking={}
    for index,seed in enumerate(request.surfaces):
        track=tracks[seed.track_id];corners=seed.corners
        if corners is None:
            cap=cv2.VideoCapture(str(source));cap.set(cv2.CAP_PROP_POS_FRAMES,seed.start_frame);ok,image=cap.read();cap.release()
            if not ok:raise ValueError('Cannot read source seed frame')
            region=next(r for r in track.regions if r.frame==seed.start_frame)
            corners=contour_corners(image,region.box)
        asset=work/f'asset-{index}.png';words=make_asset(asset,seed.kind,corners)
        collision=any(any(normalized_text(v)[i:i+4] in normalized_text(words) for i in range(len(normalized_text(v))-3)) for v in seed.original_identifiers)
        if corners is None or collision:
            geometry=[];detail={'status':'opaque_fallback','reason':'No surface contour' if corners is None else 'Template conflicts with original identifier'}
        else:
            geometry,detail=track_surface(source,corners,start_frame=seed.start_frame)
            protected={r.frame for r in track.regions};geometry=[g for g in geometry if g.frame in protected]
        detail['initialization']='client_first_frame_corners' if seed.corners is not None else 'automatic_local_contour_candidate'
        tracking[seed.track_id]=detail
        plans.append(SurfaceReplacement(track_id=seed.track_id,asset_path=str(asset),geometry_source=detail['initialization'],frames=geometry))
    save(work/'tracking.json',tracking)
    candidate=work/'candidate.mp4'
    rendering=render(source,candidate,timeline,natural_replacements=plans);save(work/'candidate-render.json',rendering)
    first=audit_export_text(candidate,values,work/'candidate-check',cache);save(work/'candidate-check.json',first)
    final=candidate;final_audit=first;rejected=[];final_render=rendering
    if first['status']=='residual_observed':
        rejected=sorted({owners[h['original_identifier_index']] for h in first['residual_findings']})
        remaining=[p for p in plans if p.track_id not in rejected]
        final=work/'fallback.mp4';final_render=render(source,final,timeline,natural_replacements=remaining)
        save(work/'fallback-render.json',final_render)
        final_audit=audit_export_text(final,values,work/'fallback-check',cache);save(work/'fallback-check.json',final_audit)
    report.update(candidate_audit=first,final_audit=final_audit,rejected_track_ids=rejected,
        render=final_render,tracking=tracking,repair_budget=1,
        original_identifier_scope='Only supplied values and contiguous four-character fragments, all decoded frames')
    if final_audit['status']!='no_original_identifier_observed_in_checked_frames':
        report['reason']='Final original-identifier audit incomplete or residual remains; export withheld'
        save(work/'report.json',report);return None,report
    inspection=decode_export(final);quality=quality_review(source,final,timeline)
    summaries=[]
    candidate_decisions=rendering.get('natural_replacement',{}).get('decisions',[])
    assets=rendering.get('natural_replacement',{}).get('assets',{})
    for seed in request.surfaces:
        track=tracks[seed.track_id];decisions=[d for d in candidate_decisions if d['track_id']==seed.track_id]
        fallback_frames=([r.frame for r in track.regions] if seed.track_id in rejected else
                         [d['frame'] for d in decisions if d['applied_strategy']=='opaque_redaction'])
        natural_count=len(track.regions)-len(fallback_frames)
        final_strategy='natural_replacement' if not fallback_frames else ('opaque_redaction' if not natural_count else 'mixed_natural_and_opaque')
        summaries.append({'track_id':seed.track_id,'category':track.category,
            'start_ms':round(min(r.frame for r in track.regions)/media['fps']*1000),
            'end_ms':round((max(r.frame for r in track.regions)+1)/media['fps']*1000),
            'proposed_strategy':'natural_replacement','final_strategy':final_strategy,
            'replacement_asset_sha256':assets.get(seed.track_id,{}).get('sha256'),
            'natural_frames':natural_count,'opaque_fallback_frames':fallback_frames,
            'post_audit_fallback':seed.track_id in rejected,
            'fallback_reasons':(['Original identifier residual observed in exported candidate'] if seed.track_id in rejected else
                sorted({d['fallback_reason'] for d in decisions if d['fallback_reason']})),
            'original_identifier_verification':final_audit['status']})
    report['track_decisions']=summaries
    report.update(export_sha256=final_audit['export_sha256'],media_inspection=inspection,visual_quality=quality,
        applied_strategies={s.track_id: ('opaque_redaction' if s.track_id in rejected else 'see_per_frame_render_decisions') for s in request.surfaces})
    if inspection['near_full_frame_black_frames']:
        report['reason']='Unexpected near-full-frame blackout; export withheld for review'
        save(work/'report.json',report);return None,report
    report['status']='original_identifier_check_completed_visual_review_required'
    save(work/'report.json',report)
    return final,report
