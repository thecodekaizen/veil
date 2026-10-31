"""Public-data-only prospective checks of fitted-model adequacy."""
from __future__ import annotations
import numpy as np
from .contracts import experiment_library, schedule

DIAGNOSTIC_THRESHOLD_C = .3

def probe_library():
    return experiment_library() + [schedule('sustained-both', [(60,60)])]

def choose_probe(models, strategy):
    plans=probe_library()
    if strategy=='fixed-release':
        return next(p for p in plans if p.id=='both-release')
    if strategy=='fixed-sustained':
        return next(p for p in plans if p.id=='sustained-both')
    if strategy!='model-disagreement':
        raise ValueError('Unknown diagnostic strategy')
    if len(models)<2:
        raise ValueError('Disagreement requires two fitted models')
    return max(plans, key=lambda p:float(np.mean(np.var(
        [m.predict(p.commands(),22.) for m in models],axis=0))))

def assess(predicted, measured):
    predicted=np.asarray(predicted,dtype=float); measured=np.asarray(measured,dtype=float)
    if predicted.shape!=measured.shape or predicted.ndim!=2 or predicted.shape[1]!=2:
        raise ValueError('Expected matching temperature-pair trajectories')
    if len(predicted)<2 or not np.isfinite(predicted).all() or not np.isfinite(measured).all():
        raise ValueError('Expected finite trajectories with at least two samples')
    error=float(np.sqrt(np.mean((predicted[1:]-measured[1:])**2,axis=0)).mean())
    return {'probe_rmse_c':error,'threshold_c':DIAGNOSTIC_THRESHOLD_C,
            'status':'model_mismatch_observed' if error>DIAGNOSTIC_THRESHOLD_C else 'no_mismatch_observed',
            'scope':'This probe only; passing does not certify unseen schedules.'}
