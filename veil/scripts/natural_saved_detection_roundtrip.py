"""Reuse saved real Meta geometry; no fresh inference and no benchmark labels."""
from pathlib import Path
import argparse,json,hashlib,time,shutil
from veil import VeilClient
from veil.providers.common import save
from veil.media.inspect import decode_export

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--base-url',default='http://127.0.0.1:8020');p.add_argument('--face-blur',action='store_true');a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
evidence=Path('artifacts/live-pipeline-003/provider-evidence')
timeline=json.loads((evidence/'timeline.json').read_text())
repair=json.loads((evidence/'repair-timeline.json').read_text())
timeline['visual_tracks'].extend(repair['visual_tracks'])
if a.face_blur:
    for track in timeline['visual_tracks']:
        if track['category']=='face':track['action']='blur'
source=Path('artifacts/smoke-001/input.mp4')
seed={'track_id':'plate-7','kind':'plate','start_frame':0,'original_identifiers':['TEST0146']}
save(a.output/'request.json',{'timeline':timeline,'surfaces':[seed]})
start=time.monotonic()
with VeilClient(a.base_url) as client:
    result=client.protect_natural(source,a.output/'downloaded.mp4',[seed],media_is_synthetic_or_consented=True,timeline=timeline)
save(a.output/'roundtrip.json',result)
job=Path('artifacts/private/natural-jobs')/result['job']['id'];archive=a.output/'server-evidence';archive.mkdir()
for f in job.rglob('*.json'):
    dest=archive/f.relative_to(job);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
for name in ('candidate.mp4','fallback.mp4'):
    f=job/'natural'/name
    if f.exists():shutil.copy2(f,a.output/name)
review=result['natural_review']
summary={'job_id':result['job']['id'],'status':result['job']['status'],'downloaded':result['downloaded'],'elapsed_s':time.monotonic()-start,
    'additional_model_calls':0,'additional_api_cost_usd':0,'face_treatment':'blur' if a.face_blur else 'cover','no_face_anonymity_guarantee':True,
    'scope':'Existing synthetic development scene; saved real SAM/Spark detection and real Voice mute intervals plus saved output-audit phone repair geometry. Reused, not fresh inference or held-out validation.',
    'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'natural_status':review['status'],'track_decisions':review.get('track_decisions'),
    'original_identifier_check':review.get('final_audit'),'visual_preference':'not_run','self_recorded_screen_case':'missing by user instruction'}
if result['downloaded']:
    summary['media']=decode_export(a.output/'downloaded.mp4')
    summary['hash_matches_audit']=hashlib.sha256((a.output/'downloaded.mp4').read_bytes()).hexdigest()==review['export_sha256']
save(a.output/'summary.json',summary)
print({k:summary[k] for k in ('status','downloaded','natural_status','elapsed_s')})
