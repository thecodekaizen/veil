"""Explicit bounded live investigator over a separate simulated lab process."""
import argparse
import hashlib
import json
from pathlib import Path
from .contracts import initial_schedule,experiment_library,schedule
from .physical import fit_physical,ThermalSpec
from .investigation import Investigation
from .investigator_tools import InvestigationTools,decide_with_tools
from .meta import MetaDecider,load_api_key
from .run import LabClient,write_json


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--env-file',type=Path)
    parser.add_argument('--evaluator-seed',type=int,default=991)
    args=parser.parse_args()
    protocol={'version':'live-controller-integration-v2','max_provider_calls':8,'local_cost_guard_usd':1.,
              'max_experiment_actions':7,'max_fit_actions':4,'policy':'meta_investigator',
              'initial_model':'supplied no-lag family, deliberately restricted for integration test',
              'initial_trials':['initial-common','left-pulse','right-pulse'],
              'prospective_probe':'sustained-both at 60 percent','automatic_retries':False,
              'purpose':'end-to-end live integration; not fair superiority comparison',
              'source':'generated simulation only','no_hardware':True}
    if not args.live:print(json.dumps(protocol,indent=2));return
    args.output.mkdir(parents=True,exist_ok=False)
    protocol['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    write_json(args.output/'protocol.json',protocol)
    write_json(args.output/'evaluator-config.json',{'seed':args.evaluator_seed,'delayed':True,'exclude_from_model_context':True})
    # Seed and world option are evaluator-only; never part of public tool context.
    lab=LabClient(args.evaluator_seed,True,7)
    store=Investigation(args.output/'session.sqlite');session='live-investigation'
    steps=[]
    try:
        observations=[lab.request({'operation':'experiment','schedule':p.to_dict()}) for p in [initial_schedule()]+experiment_library()[:2]]
        original=fit_physical(observations,ThermalSpec(False))
        store.create(session,7,observations)
        store.add_model(session,'v1',original.executable_model(),['initial-0','initial-1','initial-2'])
        probe=schedule('sustained-both',[(60,60)])
        store.prepare(session,'probe','v1',probe.to_dict())
        observed=store.execute(session,'probe',lambda action,plan:lab.request({'operation':'experiment','schedule':plan}))
        write_json(args.output/'initial-assessment.json',observed)
        tools=InvestigationTools(store,session,max_fits=4)
        provider=MetaDecider(load_api_key(args.env_file),args.output/'provider',max_calls=8,budget_usd=1.)
        for index in range(8):
            write_json(args.output/f'context-{index+1}.json',tools.context())
            decision,usage=decide_with_tools(provider,tools,'meta_investigator')
            result=tools.apply(f'controller-{index+1}',decision)
            if decision['operation']=='propose_experiment':
                action=f'experiment-{index+1}'
                store.prepare(session,action,result['model_id'],result['schedule'],result['kind'])
                measured=store.execute(session,action,lambda ident,plan:lab.request({'operation':'experiment','schedule':plan}))
                result={**result,'execution':measured}
            row={'step':index+1,'decision':decision,'usage':usage,'result':result}
            steps.append(row);write_json(args.output/f'step-{index+1}.json',row)
            print(json.dumps({'step':index+1,'operation':decision['operation'],'family':decision['family'],
                              'outcome':result.get('execution',{}).get('verdict',result.get('status','fit_completed')),
                              'estimated_usd':usage['estimated_usd']}),flush=True)
            if decision['operation']=='stop':break
        write_json(args.output/'result.json',{'status':'completed','steps':steps,
            'limitation':'Live integration only; supplied model grammar and deliberately restricted initial family'})
    except Exception as exc:
        write_json(args.output/'result.json',{'status':'failed_no_retry','error_type':type(exc).__name__,
                  'message':str(exc) if isinstance(exc,ValueError) else 'Local controller failure','steps':steps})
        raise
    finally:
        try:write_json(args.output/'investigation-export.json',store.export(session))
        finally:store.close();lab.close()
if __name__=='__main__':main()
