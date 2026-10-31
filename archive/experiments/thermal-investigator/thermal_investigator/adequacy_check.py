"""Separate diagnostic trial before sealed challenge scoring; no model API."""
import argparse
import hashlib
from pathlib import Path
import numpy as np
from .adequacy import choose_probe, assess
from .contracts import DT, initial_schedule, experiment_library
from .lab import parameters
from .physical import physical_candidates
from .predictor import fit_candidates, select_model
from .run import write_json
from .validation import challenges, hidden_trace

SEEDS=(307,331,353,379,401,431,457,479,503,541)
STRATEGIES=('fixed-release','fixed-sustained','model-disagreement')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output; output.mkdir(parents=True,exist_ok=False)
    write_json(output/'protocol.json',{'version':'prospective-adequacy-v1','seeds':SEEDS,
        'strategies':STRATEGIES,'training_trials':3,'diagnostic_trials_per_strategy':1,
        'threshold_c':.3,'meta_calls':0,'no_refitting_after_probe':True,
        'worlds':['coupled','sensor-delay','nonlinear-loss-stress'],
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        'limitations':['simulation only','same-process evaluator','supplied structures',
                       'probe adds 120 experiment seconds and 300 reset seconds',
                       'challenge schedules previously used; fresh system seeds only']})
    rows=[]
    for seed in SEEDS:
        for world in ('coupled','sensor-delay','nonlinear-loss-stress'):
            p=parameters(seed,world=='sensor-delay'); nonlinear=world=='nonlinear-loss-stress'
            def observation(plan,index):
                clean=hidden_trace(plan.commands(),p,nonlinear)
                measured=clean+np.random.default_rng(np.random.SeedSequence([seed,index])).normal(0,.08,clean.shape)
                measured[0]=22.
                return {'commands_fraction':plan.commands(),'temperature_c':measured.tolist(),
                        'ambient_c':22.,'sample_interval_s':DT,'noise_std_c':.08,'source':'simulation'}
            obs=[observation(plan,i) for i,plan in enumerate([initial_schedule()]+experiment_library()[:2])]
            physical=min(physical_candidates(obs),key=lambda m:m.validation_rmse_c)
            arx=select_model(fit_candidates(obs)); models=[physical,arx]
            for strategy in STRATEGIES:
                folder=output/f'{seed}-{world}-{strategy}'; folder.mkdir()
                probe=choose_probe(models,strategy)
                predictions={s.id:physical.predict(s.commands(),22.).tolist() for s in challenges()}
                write_json(folder/'prediction-commit.json',{'observations':obs,
                    'models':[m.to_dict() for m in models], 'probe':probe.to_dict(),
                    'probe_prediction':physical.predict(probe.commands(),22.).tolist(),'challenges':predictions})
                path=folder/'prediction-commit.json'; digest=hashlib.sha256(path.read_bytes()).hexdigest()
                measured=observation(probe,9)
                diagnostic=assess(physical.predict(probe.commands(),22.),measured['temperature_c'])
                # Freeze decision before generating any challenge output.
                write_json(folder/'diagnostic-commit.json', {'probe_observation':measured,'assessment':diagnostic})
                diagnostic_path=folder/'diagnostic-commit.json'
                diagnostic_digest=hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()
                actual={s.id:hidden_trace(s.commands(),p,nonlinear).tolist() for s in challenges()}
                errors=[float(np.sqrt(np.mean((np.asarray(predictions[k])-v)**2,axis=0)).mean()) for k,v in actual.items()]
                row={'seed':seed,'world':world,'strategy':strategy,'probe':probe.id,
                     'flagged':diagnostic['status']=='model_mismatch_observed',
                     'any_challenge_failure':max(errors)>.3,'challenge_rmse_c':errors,
                     'probe_rmse_c':diagnostic['probe_rmse_c']}
                if hashlib.sha256(path.read_bytes()).hexdigest()!=digest or hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()!=diagnostic_digest:
                    raise RuntimeError('Committed evidence changed')
                write_json(folder/'scores.json',{'prediction_sha256':digest,'diagnostic_sha256':diagnostic_digest,
                                               'result':row,'actual_traces':actual})
                rows.append(row)
            print(f'{seed} {world} complete',flush=True)
    write_json(output/'results.json',{'rows':rows,'meta_calls':0})
    lines=['# Prospective model-adequacy check','',
           'Thirty fresh simulated systems. Each strategy gets three fitting trials and one diagnostic trial.',
           'Models are not refitted with diagnostic observations. Decisions precede challenge disclosure.','',
           '| Strategy | Failure systems flagged | Failure systems missed | Nonfailure systems flagged |',
           '|---|---:|---:|---:|']
    for strategy in STRATEGIES:
        r=[x for x in rows if x['strategy']==strategy]
        lines.append(f"| {strategy} | {sum(x['flagged'] and x['any_challenge_failure'] for x in r)} | {sum(not x['flagged'] and x['any_challenge_failure'] for x in r)} | {sum(x['flagged'] and not x['any_challenge_failure'] for x in r)} |")
    lines+=['','Failures mean at least one of three challenge RMSEs exceeds the fixed diagnostic 0.3°C threshold.',
            'Flags only report mismatch on the diagnostic trial. A passed probe does not certify reliability.',
            'Challenge schedules were previously used; only system seeds are fresh. No Meta contribution or hardware claim.',
            'Each probe costs an additional 120 simulated experiment seconds plus a 300-second reset charge.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__': main()
