"""Explicit two-call live integration using previously saved public simulation data."""
import argparse
import hashlib
import json
from pathlib import Path
from .investigation import Investigation
from .investigator_tools import InvestigationTools,decide_with_tools
from .meta import MetaDecider,load_api_key
from .run import write_json


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true')
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--env-file',type=Path)
    args=parser.parse_args()
    protocol={'version':'live-tools-integration-v1','max_calls':2,'local_cost_guard_usd':.25,
              'policy':'meta_investigator','automatic_retries':False,
              'source':'previously recorded public noiseless simulation; not held-out evaluation',
              'purpose':'validate real structured decisions and numerical tool dispatch; not superiority',
              'no_physical_experiment_dispatched':True}
    if not args.live:
        print(json.dumps(protocol,indent=2));return
    args.output.mkdir(parents=True,exist_ok=False)
    protocol['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    protocol['input_export_sha256']=hashlib.sha256(args.source.read_bytes()).hexdigest()
    write_json(args.output/'protocol.json',protocol)
    recorded=json.loads(args.source.read_text())
    observations={r['id']:json.loads(r['body']) for r in recorded['observations']}
    original=next(r for r in recorded['models'] if r['id']=='v1')
    probe=next(r for r in recorded['actions'] if r['id']=='probe')
    store=Investigation(args.output/'investigation.sqlite')
    decisions=[]
    try:
        store.create('live-integration',5,[observations[f'initial-{i}'] for i in range(3)])
        store.add_model('live-integration','v1',json.loads(original['body']),['initial-0','initial-1','initial-2'])
        request=json.loads(probe['request'])
        store.prepare('live-integration','probe','v1',request['schedule'])
        store.execute('live-integration','probe',lambda *args:observations['probe'])
        tools=InvestigationTools(store,'live-integration',max_fits=2)
        provider=MetaDecider(load_api_key(args.env_file),args.output/'provider',max_calls=2,budget_usd=.25)
        for step in range(2):
            write_json(args.output/f'context-{step+1}.json',tools.context())
            decision,usage=decide_with_tools(provider,tools,'meta_investigator')
            result=tools.apply(f'live-decision-{step+1}',decision)
            row={'step':step+1,'decision':decision,'usage':usage,'tool_result':result}
            decisions.append(row);write_json(args.output/f'decision-{step+1}.json',row)
            print(json.dumps({'step':step+1,'operation':decision['operation'],'family':decision['family'],
                              'estimated_usd':usage['estimated_usd'],'status':result.get('status','fit_completed')}),flush=True)
            if decision['operation']=='stop':break
        write_json(args.output/'result.json',{'status':'completed','decisions':decisions,'limitations':protocol['purpose']})
    except Exception as exc:
        write_json(args.output/'result.json',{'status':'failed_no_retry','error_type':type(exc).__name__,
                   'message':str(exc) if isinstance(exc,ValueError) else 'Local integration failure', 'decisions':decisions})
        raise
    finally:
        write_json(args.output/'investigation-export.json',store.export('live-integration'))
        store.close()
if __name__=='__main__':main()
