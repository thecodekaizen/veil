"""Frozen paired comparison with unrestricted common candidate families."""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path
import numpy as np
from .contracts import initial_schedule,experiment_library,Schedule
from .adequacy import probe_library
from .investigation import Investigation
from .investigator_tools import InvestigationTools,decide_with_tools
from .model_registry import execute_candidate
from .meta import MetaDecider,load_api_key
from .run import LabClient,write_json

SEEDS=(1301,1327,1361,1399,1423)
METHODS=('fixed_bic','disagreement_bic','meta_direct','meta_investigator')

def bic(candidate,observations):
    model=candidate['model'];errors=[]
    for obs in observations:
        pred=execute_candidate(model,obs['commands_fraction'])
        errors.extend((pred[1:]-np.asarray(obs['temperature_c'])[1:]).ravel())
    n=len(errors);sse=float(np.dot(errors,errors));k=len(model['estimated_parameters'])
    return n*math.log(max(sse/n,1e-15))+k*math.log(n)

def select(candidates,observations):return min(candidates,key=lambda c:bic(c,observations))

def protocol():
    return {'version':'unrestricted-paired-v2','seeds':SEEDS,'worlds':['coupled','sensor-delay'],
            'methods':METHODS,'primary':'system-mean sealed RMSE C at equal seven-action budget ceiling',
            'practical_gate':'investigator median error at least 20% below both conventional baselines; report paired differences and failures',
            'initial_trials':3,'maximum_total_experiment_actions':7,'reset_seconds_per_trial':300,
            'maximum_fits':9,'shared_initial_fits':3,'max_calls_per_Meta_case':8,
            'max_Meta_calls_total':160,'bootstrap':'paired median difference, 10000 resamples, seed 148, descriptive 95% interval','guard_per_Meta_case_usd':.45,'aggregate_local_guard_usd':9,
            'no_automatic_retries':True,'initial_selection':'BIC across all three supplied families; same fitted candidates for each method',
            'fixed_schedule':['sustained-both','left-stair','staggered','right-stair'],
            'active_baseline':'maximum supplied-family prediction variance; refit all families after two and four new trials',
            'numerical_model_selection':'BIC on all available observations; tools equally accessible',
            'Meta_submission':'latest independently supported revision, otherwise unrestricted initial model; no post-hoc best-model oracle',
            'failures':'report execution error and score last supported model when possible; failures never omitted',
            'early_stop':'charged actual actions plus common ceiling; no experiment-saving claim from accuracy alone',
            'challenge':'same pre-existing lab schedule; fresh instances only, not fresh challenge family',
            'limitations':['simulation only','bounded supplied grammar','ten cases feasibility not broad proof',
                           'direct and investigator differ only in instruction policy; same persistence and tools',
                           'no hardware or industrial savings claim']}


def run_case(folder,seed,delayed,method,key):
    folder.mkdir();lab=LabClient(seed,delayed,7);store=Investigation(folder/'session.sqlite')
    session='comparison';start=time.monotonic();final_model=None;failure=None;steps=[];provider=None
    try:
        observations=[lab.request({'operation':'experiment','schedule':p.to_dict()}) for p in [initial_schedule()]+experiment_library()[:2]]
        store.create(session,7,observations);tools=InvestigationTools(store,session,max_fits=9)
        ids=['initial-0','initial-1','initial-2']
        candidates=[tools.fit(f,ids) for f in ('linear','sensor_lag','quadratic_loss')]
        chosen=select(candidates,observations);final_model=chosen['model']
        store.add_model(session,'initial',final_model,ids)
        write_json(folder/'initial-models.json',{'candidates':candidates,'bic_scores':{c['family']:bic(c,observations) for c in candidates},'selected':chosen['family']})
        if method.startswith('meta_'):
            provider=MetaDecider(key,folder/'provider',max_calls=8,budget_usd=.45)
            for i in range(8):
                write_json(folder/f'context-{i+1}.json',tools.context())
                decision,usage=decide_with_tools(provider,tools,method)
                result=tools.apply(f'decision-{i+1}',decision)
                if decision['operation']=='propose_experiment':
                    action=f'action-{i+1}'
                    store.prepare(session,action,result['model_id'],result['schedule'],result['kind'])
                    result['execution']=store.execute(session,action,lambda ident,plan:lab.request({'operation':'experiment','schedule':plan}))
                    if result['execution']['verdict']=='revision_supported_on_confirmation':
                        final_model=json.loads(next(m for m in store.export(session)['models'] if m['id']==result['model_id'])['body'])
                row={'decision':decision,'usage':usage,'result':result};steps.append(row);write_json(folder/f'step-{i+1}.json',row)
                if decision['operation']=='stop':break
        else:
            used=[]
            for i in range(4):
                if method=='fixed_bic':
                    ident=('sustained-both','left-stair','staggered','right-stair')[i]
                    plan=next(p for p in probe_library() if p.id==ident)
                else:
                    legal=[p for p in probe_library() if p.id not in used]
                    plan=max(legal,key=lambda p:float(np.mean(np.var([execute_candidate(c['model'],p.commands()) for c in candidates],axis=0))))
                used.append(plan.id)
                store.prepare(session,f'collected-{i+1}','initial',plan.to_dict())
                store.execute(session,f'collected-{i+1}',lambda ident,body:lab.request({'operation':'experiment','schedule':body}))
                observation=json.loads(next(o for o in store.export(session)['observations'] if o['id']==f'collected-{i+1}')['body'])
                observations.append(observation)
                # Conventional data collection is recorded separately; no claim of
                # tested model revisions or confirmation without a frozen forecast.
                write_json(folder/f'collected-{i+1}.json',{'schedule':plan.to_dict(),'observation':observation})
                if method=='disagreement_bic' and i in (1,3) or method=='fixed_bic' and i==3:
                    current_ids=[o['observation_id'] for o in tools.evidence()]
                    candidates=[tools.fit(f,current_ids) for f in ('linear','sensor_lag','quadratic_loss')]
            final_model=select(candidates,observations)['model']
        status='completed'
    except Exception as exc:
        failure={'type':type(exc).__name__,'message':str(exc) if isinstance(exc,ValueError) else 'Controller execution failure'}
        status='failed_no_retry'
    result={'status':status,'failure':failure,'method':method,'steps_completed':len(steps),'source':'simulation'}
    try:
        if final_model is not None:
            inputs=lab.request({'operation':'challenge_inputs'})
            prediction=execute_candidate(final_model,inputs['commands_fraction']).tolist()
            write_json(folder/'prediction-commit.json',{'model':final_model,'inputs':inputs,'prediction':prediction})
            digest=hashlib.sha256((folder/'prediction-commit.json').read_bytes()).hexdigest()
            score=lab.request({'operation':'challenge','prediction':{'temperature_c':prediction}})
            assert hashlib.sha256((folder/'prediction-commit.json').read_bytes()).hexdigest()==digest
            write_json(folder/'challenge-score.json',score)
            result.update({'mean_rmse_c':score['mean_rmse_c'],'prediction_sha256':digest})
        exported=store.export(session)
        write_json(folder/'investigation-export.json',exported)
        result['experiment_actions_used']=exported['session']['used']
        result['fits_used']=9-tools.fit_remaining()
        result['wall_seconds']=time.monotonic()-start
        result['usage']=provider._state() if provider is not None else {'attempts':0,'charged_or_reserved_usd':0.}
        write_json(folder/'result.json',result)
        return result
    finally:store.close();lab.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--live',action='store_true');parser.add_argument('--env-file',type=Path)
    args=parser.parse_args();frozen=protocol()
    if not args.live:print(json.dumps(frozen,indent=2));return
    args.output.mkdir(parents=True,exist_ok=False)
    frozen['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    write_json(args.output/'protocol.json',frozen)
    key=load_api_key(args.env_file);rows=[]
    for index,seed in enumerate(SEEDS):
        for delayed in (False,True):
            # Rotate method order by paired system to reduce simple order effects.
            methods=METHODS[index%4:]+METHODS[:index%4]
            for method in methods:
                result=run_case(args.output/f'case-{index}-{int(delayed)}-{method}',seed,delayed,method,key)
                result.update({'pair_id':f'{index}-{int(delayed)}','world':'sensor-delay' if delayed else 'coupled'})
                rows.append(result);write_json(args.output/'results.json',{'rows':rows})
                print(json.dumps({'pair':result['pair_id'],'method':method,'status':result['status'],
                                  'rmse_c':result.get('mean_rmse_c'),'calls':result['usage']['attempts']}),flush=True)
    summarize(args.output,rows)


def summarize(folder,rows):
    lines=['# Unrestricted paired comparison','',
           'Ten fresh simulated systems; identical seven-action ceilings and three supplied model families.',
           'Shared initial selection uses BIC; no deliberately wrong initial model. All failures retained.','',
           '| Method | Median RMSE °C | Failed executions | Median actions used | Meta calls |',
           '|---|---:|---:|---:|---:|']
    for method in METHODS:
        r=[x for x in rows if x['method']==method];errors=[x['mean_rmse_c'] for x in r if 'mean_rmse_c' in x]
        lines.append(f"| {method} | {np.median(errors):.6f} | {sum(x['status']!='completed' for x in r)}/10 | {np.median([x['experiment_actions_used'] for x in r]):.1f} | {sum(x['usage']['attempts'] for x in r)} |")
    lines+=['','## Paired investigator minus baseline RMSE (negative favors investigator)','',
            '| Baseline | Median paired difference °C | Investigator wins / ties / losses |','|---|---:|---|']
    investigator={x['pair_id']:x for x in rows if x['method']=='meta_investigator'}
    for method in ('fixed_bic','disagreement_bic','meta_direct'):
        baseline={x['pair_id']:x for x in rows if x['method']==method}
        diffs=[investigator[p]['mean_rmse_c']-baseline[p]['mean_rmse_c'] for p in investigator if 'mean_rmse_c' in investigator[p] and 'mean_rmse_c' in baseline[p]]
        rng=np.random.default_rng(148)
        samples=np.median(rng.choice(diffs,size=(10000,len(diffs)),replace=True),axis=1)
        low,high=np.quantile(samples,[.025,.975])
        lines.append(f'| {method} | {np.median(diffs):.6f} (95% bootstrap [{low:.6f}, {high:.6f}]) | {sum(x < -1e-9 for x in diffs)} / {sum(abs(x)<=1e-9 for x in diffs)} / {sum(x>1e-9 for x in diffs)} |')
    medians={m:float(np.median([r['mean_rmse_c'] for r in rows if r['method']==m and 'mean_rmse_c' in r])) for m in METHODS}
    superiority=all(medians['meta_investigator']<=.8*medians[m] for m in ('fixed_bic','disagreement_bic'))
    lines+=['',f'Predeclared 20% median-error improvement gate versus both numerical baselines: {"PASS" if superiority else "FAIL"}.',
            'Bootstrap intervals are descriptive with ten paired instances, not broad scientific proof.']
    cost=sum(x['usage']['charged_or_reserved_usd'] for x in rows)
    lines+=['',f'Estimated total API cost: ${cost:.6f}. Not confirmed billing balance.',
            'Early stopping uses fewer actual experiments; allowed ceilings are matched, realized actions need not be.',
            'A lower-budget result is not an experiment-saving claim unless its accuracy target is met.',
            'Ten instances and one pre-existing sealed schedule support feasibility only; no hardware or industrial claim.']
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
