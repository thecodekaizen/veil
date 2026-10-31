"""Offline consistency checks for saved controller evidence; no API or lab calls.

These checks detect inconsistent records, not forgery or trusted timestamps.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from .contracts import Schedule
from .model_registry import execute_candidate
from .adequacy import assess


def review_export(exported):
    models={m['id']:m for m in exported['models']}
    observations={o['id']:json.loads(o['body']) for o in exported['observations']}
    events=exported['events'];supports=rejections=0;checks=[]
    initial=sum(k.startswith('initial-') for k in observations)
    if exported['session']['used']!=initial+len(exported['actions']) or exported['session']['used']>exported['session']['budget']:
        raise ValueError('Action budget inconsistent')
    for action in exported['actions']:
        if action['status']!='completed':raise ValueError('Unresolved execution')
        request=json.loads(action['request']);plan=Schedule.from_dict(request['schedule'])
        model=models[action['model']];frozen=np.asarray(json.loads(action['prediction']))
        calculated=execute_candidate(json.loads(model['body']),plan.commands())
        if not np.allclose(frozen,calculated,rtol=0,atol=1e-9):raise ValueError('Frozen prediction differs from executable model')
        obs=observations[action['id']]
        if not np.array_equal(plan.commands(),obs['commands_fraction']):raise ValueError('Measured input differs from frozen input')
        recorded=json.loads(action['result']);assessment=assess(frozen,obs['temperature_c'])
        if not np.isclose(assessment['probe_rmse_c'],recorded['assessment']['probe_rmse_c'],atol=1e-10):raise ValueError('Incorrect error score')
        if assessment['status']!=recorded['assessment']['status']:raise ValueError('Incorrect mismatch status')
        def event_number(kind,key,value):
            matches=[e['sequence'] for e in events if e['kind']==kind and json.loads(e['body']).get(key)==value]
            if len(matches)!=1:raise ValueError('Expected exactly one lifecycle event')
            return matches[0]
        registered=event_number('model_registered','id',action['model'])
        frozen_event=event_number('prediction_frozen','action',action['id'])
        dispatched=event_number('dispatched','action',action['id'])
        measured=event_number('measurement_recorded','action_id',action['id'])
        if not registered<frozen_event<dispatched<measured:raise ValueError('Prediction lifecycle order invalid')
        if action['kind']=='confirmation':
            if model['parent'] is None:raise ValueError('Confirmation of unrevised model')
            evidence=json.loads(model['evidence'])
            if any(np.array_equal(plan.commands(),observations[e]['commands_fraction']) for e in evidence):
                raise ValueError('Confirmation input was already used in fitted evidence')
            failed=assessment['status']=='model_mismatch_observed'
            expected='revision_rejected' if failed else 'revision_supported_on_confirmation'
            if recorded['verdict']!=expected:raise ValueError('Confirmation verdict inconsistent')
            rejections+=int(failed);supports+=int(not failed)
        checks.append({'action_id':action['id'],'rmse_c':assessment['probe_rmse_c'],'verdict':recorded['verdict']})
    return {'status':'consistent','actions_used':exported['session']['used'],'action_budget':exported['session']['budget'],
            'confirmation_supports':supports,'confirmation_rejections':rejections,'checks':checks,
            'limitations':'Internal consistency only; no authenticity, superiority or global reliability certificate'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('export',type=Path)
    args=parser.parse_args();print(json.dumps(review_export(json.loads(args.export.read_text())),indent=2))
if __name__=='__main__':main()
