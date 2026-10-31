"""Matched-budget local revision comparison. No Meta calls or hardware claims."""
import argparse
import hashlib
from pathlib import Path
import numpy as np
from .contracts import DT, Schedule, initial_schedule, experiment_library, schedule
from .physical import physical_candidates
from .adequacy import assess
from .investigation import Investigation
from .lab import parameters
from .validation import hidden_trace
from .run import write_json

SEEDS=(701,733,769,809,853,887)

def confirmation_schedule():
    return schedule('revision-confirmation',[(40,5),(5,60),(55,25),(0,0),(25,45),(10,10)])

def final_schedules():
    return [schedule('sealed-ramp',[(5,15),(15,25),(25,35),(35,45),(45,55),(55,65)]),
            schedule('sealed-asymmetric',[(65,10),(0,30),(40,0),(10,60),(0,0),(30,15)]),
            schedule('sealed-bursts',[(65,65),(0,0),(65,65),(0,0),(20,50),(0,0)])]

def choose(observations):
    return min(physical_candidates(observations),key=lambda m:m.validation_rmse_c)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output; output.mkdir(parents=True,exist_ok=False)
    write_json(output/'protocol.json',{'version':'matched-revision-v1','seeds':SEEDS,
        'worlds':['coupled','sensor-delay','nonlinear-loss-stress'],'action_budget':5,
        'experiment_seconds':600,'reset_charge_seconds':1500,'meta_calls':0,
        'methods':['frozen_initial','batch_all_families_five_trials','mismatch_revision_four_then_confirm'],
        'primary_endpoint':'raw held-out mean per-sensor RMSE at matched five-action budget',
        'secondary':'confirmation support/rejection versus sealed failure; no discarded scores',
        'target_c':.3,'initial_family_selection':'whole-trial CV across both supplied families for every method',
        'probe':schedule('sustained',[(60,60)]).to_dict(),
        'confirmation':confirmation_schedule().to_dict(),'sealed_inputs':[s.to_dict() for s in final_schedules()],
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        'limitations':['simulation only','same-process numerical evaluator','six instances per world',
                       'fixed shared collection policy','human-authored revision policy','not Meta comparison']})
    rows=[]
    for seed in SEEDS:
        for world in ('coupled','sensor-delay','nonlinear-loss-stress'):
            folder=output/f'{seed}-{world}';folder.mkdir()
            params=parameters(seed,world=='sensor-delay'); nonlinear=world=='nonlinear-loss-stress'
            def observed(plan,index):
                clean=hidden_trace(plan.commands(),params,nonlinear)
                noisy=clean+np.random.default_rng(np.random.SeedSequence([seed,index])).normal(0,.08,clean.shape)
                noisy[0]=22.
                return {'commands_fraction':plan.commands(),'temperature_c':noisy.tolist(),
                        'ambient_c':22.,'sample_interval_s':DT,'source':'simulation','noise_std_c':.08}
            initial=[observed(plan,i) for i,plan in enumerate([initial_schedule()]+experiment_library()[:2])]
            original=choose(initial); policy=original
            store=Investigation(folder/'session.sqlite')
            try:
                store.create('comparison',5,initial)
                store.add_model('comparison','v1',original.executable_model(),['initial-0','initial-1','initial-2'])
                probe=schedule('sustained',[(60,60)])
                probe_obs=observed(probe,3)
                store.prepare('comparison','probe','v1',probe.to_dict())
                diagnostic=store.execute('comparison','probe',lambda *args:probe_obs)
                mismatch=diagnostic['assessment']['status']=='model_mismatch_observed'
                active='v1'
                if mismatch:
                    policy=choose(initial+[probe_obs]);active='v2'
                    store.add_model('comparison','v2',policy.executable_model(),['initial-0','initial-1','initial-2','probe'],parent='v1')
                confirm=confirmation_schedule()
                store.prepare('comparison','confirm',active,confirm.to_dict(),'confirmation' if mismatch else 'diagnostic')
                # Restart before the independent confirmation measurement.
                store.close();store=Investigation(folder/'session.sqlite')
                confirm_obs=observed(confirm,4)
                verdict=store.execute('comparison','confirm',lambda *args:confirm_obs)
                batch=choose(initial+[probe_obs,confirm_obs])
                models={'frozen_initial':original,'batch_all_families_five_trials':batch,
                        'mismatch_revision_four_then_confirm':policy}
                predictions={name:{p.id:model.predict(p.commands()).tolist() for p in final_schedules()} for name,model in models.items()}
                write_json(folder/'prediction-commit.json',{'models':{name:m.to_dict() for name,m in models.items()},
                    'predictions':predictions,'diagnostic':diagnostic,'confirmation':verdict,
                    'policy_abstains':verdict['assessment']['status']=='model_mismatch_observed'})
                committed=folder/'prediction-commit.json'; digest=hashlib.sha256(committed.read_bytes()).hexdigest()
                # Sealed outputs are first generated after all methods commit.
                actual={p.id:hidden_trace(p.commands(),params,nonlinear).tolist() for p in final_schedules()}
                case=[]
                for name in models:
                    errors=[float(np.sqrt(np.mean((np.asarray(predictions[name][key])-trace)**2,axis=0)).mean()) for key,trace in actual.items()]
                    row={'seed':seed,'world':world,'method':name,'mean_rmse_c':float(np.mean(errors)),
                         'any_failure':max(errors)>.3,'per_schedule_rmse_c':errors,'actions_charged':5,
                         'policy_abstains':verdict['assessment']['status']=='model_mismatch_observed' if name=='mismatch_revision_four_then_confirm' else None,
                         'revision_triggered':mismatch if name=='mismatch_revision_four_then_confirm' else None}
                    rows.append(row);case.append(row)
                assert hashlib.sha256(committed.read_bytes()).hexdigest()==digest
                write_json(folder/'scores.json',{'prediction_sha256':digest,'scores':case,'actual_traces':actual})
                write_json(folder/'investigation-export.json',store.export('comparison'))
            finally:store.close()
            print(f'{seed} {world} complete',flush=True)
    write_json(output/'results.json',{'rows':rows,'meta_calls':0})
    lines=['# Matched five-action revision comparison','',
           'Eighteen fresh simulated systems; three new sealed schedules each. No Meta calls. All scores retained.','',
           '| Method | Median system mean RMSE °C | Systems with a failed schedule |',
           '|---|---:|---:|']
    for name in ('frozen_initial','batch_all_families_five_trials','mismatch_revision_four_then_confirm'):
        subset=[r for r in rows if r['method']==name]
        lines.append(f"| {name} | {np.median([r['mean_rmse_c'] for r in subset]):.4f} | {sum(r['any_failure'] for r in subset)}/18 |")
    policy=[r for r in rows if r['method']=='mismatch_revision_four_then_confirm']
    lines+=['',f"Revisions triggered: {sum(r['revision_triggered'] for r in policy)}/18.",
            f"Confirmation rejection/abstention: {sum(r['policy_abstains'] for r in policy)}/18.",
            f"Sealed failing systems without a confirmation warning: {sum(r['any_failure'] and not r['policy_abstains'] for r in policy)}.",
            '', 'Five trials charge 600 simulated experiment seconds and 1500 reset seconds per method.',
            'The batch baseline fits all five trials; the revision policy reserves trial five for independent confirmation.',
            'The frozen reference observes the same trials but does not refit. All use both supplied families initially.',
            'No advantage from Meta, hardware validation or calibrated uncertainty is established.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
