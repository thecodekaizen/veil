"""Offline audit of saved paired results; does not call a model or lab."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from .model_registry import execute_candidate


def audit(folder):
    rows=json.loads((folder/'results.json').read_text())['rows']
    initial_by_pair={};case_checks=[]
    for case in sorted(folder.glob('case-*')):
        if not case.is_dir() or not (case/'result.json').exists():continue
        result=json.loads((case/'result.json').read_text())
        prediction_path=case/'prediction-commit.json'
        if hashlib.sha256(prediction_path.read_bytes()).hexdigest()!=result['prediction_sha256']:
            raise ValueError('Prediction commitment hash mismatch')
        committed=json.loads(prediction_path.read_text());score=json.loads((case/'challenge-score.json').read_text())
        predicted=np.asarray(committed['prediction']);actual=np.asarray(score['temperature_c'])
        if predicted.shape!=(61,2) or actual.shape!=(61,2) or not np.isfinite(predicted).all() or not np.isfinite(actual).all():raise ValueError('Invalid score trajectories')
        executable=execute_candidate(committed['model'],committed['inputs']['commands_fraction'])
        if not np.allclose(predicted,executable,rtol=0,atol=1e-9):raise ValueError('Prediction differs from frozen executable model')
        recomputed=float(np.sqrt(np.mean((predicted-actual)**2,axis=0)).mean())
        if not np.isclose(recomputed,result['mean_rmse_c'],rtol=0,atol=1e-10):raise ValueError('Result score mismatch')
        if not np.isclose(recomputed,score['mean_rmse_c'],rtol=0,atol=1e-10):raise ValueError('Lab score mismatch')
        exported=json.loads((case/'investigation-export.json').read_text())
        initial={r['id']:json.loads(r['body']) for r in exported['observations'] if r['id'].startswith('initial-')}
        if len(initial)!=3:raise ValueError('Expected three shared initial trials')
        if result['fits_used']>9:raise ValueError('Fitting budget exceeded')
        public=[{k:initial[i][k] for k in ('commands_fraction','temperature_c','sample_interval_s','ambient_c')} for i in sorted(initial)]
        pair='-'.join(case.name.split('-')[1:3])
        if pair in initial_by_pair and public!=initial_by_pair[pair]:raise ValueError('Paired initial measurements differ')
        initial_by_pair[pair]=public
        if exported['session']['used']!=result['experiment_actions_used'] or result['experiment_actions_used']>7:
            raise ValueError('Experiment budget mismatch')
        steps=[json.loads(p.read_text()) for p in sorted(case.glob('step-*.json'))]
        stopped=bool(steps and steps[-1]['decision']['operation']=='stop')
        case_checks.append({'case':case.name,'status':result['status'],'score_recomputed':True,
                            'actions':result['experiment_actions_used'],'fits':result['fits_used'],
                            'explicit_stop':stopped,'decision_cap_reached':len(steps)==8 and not stopped})
    return {'status':'consistent','completed_case_records':len(case_checks),'expected_case_records':40,
            'complete':len(case_checks)==40,'checks':case_checks,
            'limitations':['internal consistency, not authenticity','shared seed parameter draws couple the two worlds',
                           'fallback forecasts from failed controllers are not successful Meta forecasts',
                           'common initial numerical model is itself a three-trial conventional reference']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    args=parser.parse_args();print(json.dumps(audit(args.folder),indent=2))
if __name__=='__main__':main()
