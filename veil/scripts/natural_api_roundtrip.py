"""Real SDK -> loopback HTTP -> native renderer/OCR -> MP4 download.

Uses the existing synthetic development clip, not six independent benchmark cases.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import cv2
from veil import VeilClient
from veil.providers.common import save
from veil.media.inspect import decode_export


def occlude(source, target):
    cap=cv2.VideoCapture(str(source));fps=cap.get(cv2.CAP_PROP_FPS)
    w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    silent=target.with_name('occlusion-silent.mp4');writer=cv2.VideoWriter(str(silent),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
    if not writer.isOpened():raise ValueError('Cannot create occlusion diagnostic')
    i=0
    try:
        while True:
            ok,frame=cap.read()
            if not ok:break
            if 24<=i<36:cv2.rectangle(frame,(120,165),(500,310),(110,110,110),-1)
            writer.write(frame);i+=1
    finally:cap.release();writer.release()
    subprocess.run(['ffmpeg','-y','-i',str(silent),'-i',str(source),'-map','0:v','-map','1:a','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(target)],check=True,capture_output=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--base-url',default='http://127.0.0.1:8020');p.add_argument('--mode',choices=['manual','auto','wrong-geometry','occlusion'],required=True)
    p.add_argument('--jobs-dir',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    timeline=json.loads((a.fixture/'timeline.json').read_text());quad=json.loads((a.fixture/'surface-plan.json').read_text())['frames'][0]['corners']
    source=a.fixture/'original.mp4'
    if a.mode=='occlusion':
        source=a.output/'occlusion-source.mp4';occlude(a.fixture/'original.mp4',source)
    if a.mode=='wrong-geometry':
        quad=[[x+110,y] for x,y in quad]
        for row in timeline['visual_tracks'][0]['regions']:row['box'][2]+=115
    seed={'track_id':'plate-001','kind':'plate','start_frame':0,'original_identifiers':['2025550146']}
    if a.mode!='auto':seed['corners']=quad
    save(a.output/'request.json',{'timeline':timeline,'surfaces':[seed]});started=time.monotonic()
    with VeilClient(a.base_url) as client:
        result=client.protect_natural(source,a.output/'downloaded.mp4',[seed],media_is_synthetic_or_consented=True,timeline=timeline)
    save(a.output/'roundtrip.json',result)
    review=result['natural_review']
    summary={'mode':a.mode,'job_id':result['job']['id'],'status':result['job']['status'],'downloaded':result['downloaded'],
        'natural_status':review['status'],'elapsed_s':time.monotonic()-started,'api_calls':0,'additional_api_cost_usd':0,
        'scope':'Existing synthetic development fixture or disclosed derived occlusion diagnostic. Protective boxes fixture-authored, not inferred.',
        'human_visual_preference':'not_run','six_case_benchmark':'not_run'}
    if result['downloaded']:
        summary['media']=decode_export(a.output/'downloaded.mp4')
        summary['download_sha256']=hashlib.sha256((a.output/'downloaded.mp4').read_bytes()).hexdigest()
        summary['hash_matches_audit']=summary['download_sha256']==review['export_sha256']
        summary['rejected_tracks']=review['rejected_track_ids']
        summary['natural_rendering']=review['render'].get('natural_replacement',{})
    if a.jobs_dir:
        job=a.jobs_dir/result['job']['id'];archive=a.output/'server-evidence';archive.mkdir()
        # Synthetic fixture job only: preserve JSON and explicit rejected/fallback videos.
        for file in job.rglob('*.json'):
            rel=file.relative_to(job);dest=archive/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dest)
        for name in ('candidate.mp4','fallback.mp4'):
            if (job/'natural'/name).exists():shutil.copy2(job/'natural'/name,a.output/name)
    save(a.output/'summary.json',summary)
    print({k:summary[k] for k in ('mode','status','downloaded','natural_status','elapsed_s')})

if __name__=='__main__':main()
