"""Check supplied structural extension on independently scored excitation."""
import argparse
import hashlib
from pathlib import Path
import numpy as np
from .contracts import initial_schedule,experiment_library,schedule,DT
from .physical import physical_candidates
from .nonlinear import fit_quadratic
from .lab import parameters
from .validation import hidden_trace
from .run import write_json

SEEDS=(941,977)

def quadratic_candidate(observations):
    fitted=fit_quadratic(observations)
    errors=[]
    for i,obs in enumerate(observations):
        reduced=fit_quadratic(observations[:i]+observations[i+1:])
        pred=reduced.predict(obs['commands_fraction'])
        errors.append(float(np.sqrt(np.mean((pred[1:]-np.asarray(obs['temperature_c'])[1:])**2))))
    fitted.validation_rmse_c=float(np.mean(errors))
    return fitted

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    folder=parser.parse_args().output;folder.mkdir(parents=True,exist_ok=False)
    challenges=[schedule('sustained-high',[(65,65)]),schedule('held-high-release',[(65,45),(65,45),(0,0),(0,0)])]
    write_json(folder/'protocol.json',{'version':'bounded-structure-v1','seeds':SEEDS,
        'worlds':['coupled','sensor-delay','nonlinear-loss-stress'],'training_trials':4,
        'family_knowledge':'All three structures supplied; conventional whole-trial CV selects family',
        'selection_before_challenge':True,'challenges':[p.to_dict() for p in challenges],
        'meta_calls':0,'threshold_c':.3,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}})
    rows=[]
    for seed in SEEDS:
        for world in ('coupled','sensor-delay','nonlinear-loss-stress'):
            case=folder/f'{seed}-{world}';case.mkdir()
            p=parameters(seed,world=='sensor-delay');nonlinear=world=='nonlinear-loss-stress'
            obs=[]
            for i,plan in enumerate([initial_schedule()]+experiment_library()[:2]+[schedule('training-sustained',[(60,60)])]):
                clean=hidden_trace(plan.commands(),p,nonlinear)
                noisy=clean+np.random.default_rng(np.random.SeedSequence([seed,i])).normal(0,.08,clean.shape);noisy[0]=22.
                obs.append({'commands_fraction':plan.commands(),'temperature_c':noisy.tolist(),
                            'sample_interval_s':DT,'ambient_c':22.,'noise_std_c':.08,'source':'simulation'})
            candidates=physical_candidates(obs)+[quadratic_candidate(obs)]
            selected=min(candidates,key=lambda m:m.validation_rmse_c)
            baseline=min(candidates[:2],key=lambda m:m.validation_rmse_c)
            models={'original_grammar':baseline,'expanded_grammar':selected}
            predictions={name:{s.id:m.predict(s.commands()).tolist() for s in challenges} for name,m in models.items()}
            write_json(case/'prediction-commit.json',{'observations':obs,'candidates':[m.to_dict() for m in candidates],
                'selected':selected.executable_model()['specification'],'predictions':predictions})
            path=case/'prediction-commit.json';digest=hashlib.sha256(path.read_bytes()).hexdigest()
            actual={s.id:hidden_trace(s.commands(),p,nonlinear).tolist() for s in challenges}
            for name in models:
                for key,trace in actual.items():
                    error=float(np.sqrt(np.mean((np.asarray(predictions[name][key])-trace)**2,axis=0)).mean())
                    rows.append({'seed':seed,'world':world,'method':name,'schedule':key,'rmse_c':error,
                                 'selected':models[name].executable_model()['specification']})
            assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
            write_json(case/'scores.json',{'prediction_sha256':digest,'actual_traces':actual,
                'scores':[r for r in rows if r['seed']==seed and r['world']==world]})
            print(f'{seed} {world} complete',flush=True)
    write_json(folder/'results.json',{'rows':rows,'meta_calls':0})
    lines=['# Bounded structural-extension check','',
           'Six fresh simulated systems; four noisy training trials; two independently scored challenges.',
           'Every structure is supplied and selected by conventional whole-trial validation. No Meta calls.','',
           '| World | Original grammar median RMSE °C | Expanded grammar median RMSE °C |','|---|---:|---:|']
    for world in ('coupled','sensor-delay','nonlinear-loss-stress'):
        values=[np.median([r['rmse_c'] for r in rows if r['world']==world and r['method']==m]) for m in models]
        lines.append(f'| {world} | {values[0]:.5f} | {values[1]:.5f} |')
    lines+=['','Two instances per world are insufficient for broad claims. The stress mechanism is now inside the expanded family.',
            'This measures supplied-family coverage and numerical fitting, not Meta discovery or an investigator advantage.',
            'No hardware, calibrated reliability or newly discovered physical law is established.']
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
