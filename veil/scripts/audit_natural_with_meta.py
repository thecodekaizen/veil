"""One explicit two-call broad output audit on an existing synthetic natural job."""
import argparse,json,time,shutil
from pathlib import Path
from veil import VeilClient
from veil.providers.common import save
p=argparse.ArgumentParser();p.add_argument('--job-id',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--base-url',default='http://127.0.0.1:8020');a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
with VeilClient(a.base_url) as client:
    result=client.cloud_action(a.job_id,'verify')
    audit=client.verification(a.job_id);receipt=client.receipt(a.job_id)
save(a.output/'job.json',result);save(a.output/'verification.json',audit);save(a.output/'receipt.json',receipt)
job=Path('artifacts/private/natural-jobs')/a.job_id
for name in ('calls.json','audit-0.json','audit-0-raw.json','audit-0-voice.json','audit-0-ocr.json'):
    if (job/name).exists():shutil.copy2(job/name,a.output/name)
save(a.output/'transfer.json',{'media':'three decoded actual exported frames and exported audio, synthetic development footage only',
    'provider':'Meta','expected_calls':2,'retry_policy':'none','elapsed_s':time.monotonic()-started})
print({'job_status':result['status'],'general_verification':audit['status'],'calls':len(receipt.get('cloud_calls',[])),'estimated_usd':receipt.get('estimated_api_cost_usd')})
