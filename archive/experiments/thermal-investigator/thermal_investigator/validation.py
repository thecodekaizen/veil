"""Frozen local evaluator. Hidden simulator state stays outside fitting inputs.

This evaluator shares a Python process with numerical fits; it is not a security
sandbox. Model implementations receive only the saved public observations.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import numpy as np
from .contracts import DT, experiment_library, initial_schedule, schedule
from .lab import parameters, derivative
from .physical import physical_candidates
from .predictor import fit_candidates, select_model
from .run import write_json

SEEDS = (101, 113, 127, 139, 151, 163, 179, 191, 211, 227)
THRESHOLD_C = .3  # Diagnostic prediction threshold, not a hardware tolerance.

def challenges():
    return [schedule('held-alternate', [(10,50),(50,20),(20,60),(0,15)]),
            schedule('held-sustained', [(55,45)]),
            schedule('held-fast-switch', [(60,0),(0,60)]*6)]

def hidden_trace(commands, p, nonlinear=False):
    state = np.zeros(4)
    result = [np.array([22.,22.])]
    def rhs(x, u):
        dx = derivative(x,u,p)
        if nonlinear:
            extra = .004*x[:2]*np.abs(x[:2])/np.array([p.c1,p.c2])
            dx[:2] -= extra
            if not p.sensor_tau:
                dx[2:] -= extra
        return dx
    for u in np.asarray(commands):
        for _ in range(8):
            k1=rhs(state,u); k2=rhs(state+.125*k1,u)
            k3=rhs(state+.125*k2,u); k4=rhs(state+.25*k3,u)
            state += .25*(k1+2*k2+2*k3+k4)/6
        result.append(state[2:].copy()+22.)
    return np.asarray(result)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=False)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    write_json(args.output/'protocol.json', {'version':'fresh-validation-v1', 'seeds':SEEDS,
        'worlds':['coupled','sensor-delay','nonlinear-loss-stress'], 'meta_calls':0,
        'training':['initial-common','left-pulse','right-pulse'],
        'challenges':[s.to_dict() for s in challenges()], 'diagnostic_threshold_c':THRESHOLD_C,
        'source_sha256':hashes, 'selection':'whole-trial validation before challenge outputs',
        'stress':'same nonlinear heat loss in training and challenge; unsupported supplied family',
        'limitations':['simulation only','shared-process evaluator','supplied model structures',
                       'no Meta contribution','diagnostic threshold is not a safety certification']})
    rows=[]
    for seed in SEEDS:
        for world in ('coupled','sensor-delay','nonlinear-loss-stress'):
            directory=args.output/f'{seed}-{world}'; directory.mkdir()
            p=parameters(seed, world=='sensor-delay'); nonlinear=world=='nonlinear-loss-stress'
            observations=[]
            for index,plan in enumerate([initial_schedule()]+experiment_library()[:2]):
                commands=plan.commands(); clean=hidden_trace(commands,p,nonlinear)
                noisy=clean+np.random.default_rng(np.random.SeedSequence([seed,index])).normal(0,.08,clean.shape)
                noisy[0]=22.
                observations.append({'commands_fraction':commands,'temperature_c':noisy.tolist(),
                    'ambient_c':22., 'sample_interval_s':DT, 'noise_std_c':.08, 'source':'simulation'})
            write_json(directory/'observations.json', {'observations':observations})
            physical=min(physical_candidates(observations),key=lambda m:m.validation_rmse_c)
            arx=select_model(fit_candidates(observations))
            models={'physical':physical,'arx':arx}
            predictions={name:{s.id:model.predict(s.commands(),22.).tolist() for s in challenges()}
                         for name,model in models.items()}
            write_json(directory/'prediction-commit.json', {'models':{n:m.to_dict() for n,m in models.items()},
                'predictions':predictions})
            commit=directory/'prediction-commit.json'; digest=hashlib.sha256(commit.read_bytes()).hexdigest()
            case=[]
            for plan in challenges():
                actual=hidden_trace(plan.commands(),p,nonlinear)
                for name,model in models.items():
                    error=float(np.sqrt(np.mean((np.asarray(predictions[name][plan.id])-actual)**2,axis=0)).mean())
                    row={'seed':seed,'world':world,'challenge':plan.id,'method':name,'rmse_c':error,
                         'validation_rmse_c':model.validation_rmse_c,
                         'validation_flag':model.validation_rmse_c>THRESHOLD_C,
                         'challenge_above_threshold':error>THRESHOLD_C}
                    case.append(row); rows.append(row)
            if hashlib.sha256(commit.read_bytes()).hexdigest()!=digest:
                raise RuntimeError('Prediction changed after scoring')
            write_json(directory/'scores.json', {'prediction_sha256':digest,'scores':case,
                'actual_traces':{s.id:hidden_trace(s.commands(),p,nonlinear).tolist() for s in challenges()}})
            print(f'{seed} {world} complete',flush=True)
    write_json(args.output/'results.json', {'rows':rows,'meta_calls':0})
    lines=['# Fresh simulated-system validation','',
           'Ten new seeds per world; three unseen schedules; three shared training trials. Zero Meta calls.','',
           '| World | Method | Median RMSE °C | Maximum RMSE °C | Challenges above 0.3°C |',
           '|---|---|---:|---:|---:|']
    for world in ('coupled','sensor-delay','nonlinear-loss-stress'):
        for method in ('physical','arx'):
            r=[x for x in rows if x['world']==world and x['method']==method]
            lines.append(f"| {world} | {method} | {np.median([x['rmse_c'] for x in r]):.4f} | {max(x['rmse_c'] for x in r):.4f} | {sum(x['challenge_above_threshold'] for x in r)}/{len(r)} |")
    lines+=['','Each system contributes three correlated challenge scores; these are not 90 independent systems.',
            'The nonlinear stress case uses unsupported quadratic heat loss during both training and challenge.',
            'A validation flag measures held-trial prediction error, not diagnosis of the hidden mechanism.',
            'Source and protocol were saved before execution. No retuning within this run.',
            'This establishes neither hardware performance nor an advantage from Meta.']
    (args.output/'REPORT.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__': main()
