"""Supplied quadratic-loss model, numerically fitted to public traces only.

No sensor-lag term is supported in this candidate. The family is explicit prior
engineering knowledge, not a discovered physical law or a Meta contribution.
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import least_squares
from .contracts import DT
from .physical import ThermalSpec

NAMES=ThermalSpec(False).parameter_names()+['quadratic_loss_1_per_c_s','quadratic_loss_2_per_c_s']
LOWER=np.r_[ThermalSpec(False).bounds()[0],[0.,0.]]
UPPER=np.r_[ThermalSpec(False).bounds()[1],[.01,.01]]


def simulate_quadratic(rates,commands,ambient_c=22.,step_s=.5):
    rates=np.asarray(rates,dtype=float);u=np.asarray(commands,dtype=float)
    if rates.shape!=(8,) or not np.isfinite(rates).all() or np.any(rates<LOWER) or np.any(rates>UPPER):
        raise ValueError('Quadratic thermal rates outside bounds')
    if u.ndim!=2 or u.shape[1]!=2 or not np.isfinite(u).all() or np.any(u<0) or np.any(u>.65):
        raise ValueError('Expected finite bounded commands')
    if not np.isfinite(ambient_c) or step_s not in (.25,.5,1.):
        raise ValueError('Unsupported ambient or integration step')
    loss1,loss2,c12,c21,g1,g2,q1,q2=map(float,rates)
    def derivative(a,b,v1,v2):
        return g1*v1-loss1*a+c12*(b-a)-q1*a*abs(a), g2*v2-loss2*b+c21*(a-b)-q2*b*abs(b)
    a=b=0.; rows=[[ambient_c,ambient_c]]
    for v1,v2 in u:
        for _ in range(round(DT/step_s)):
            k1a,k1b=derivative(a,b,v1,v2)
            k2a,k2b=derivative(a+step_s*k1a/2,b+step_s*k1b/2,v1,v2)
            k3a,k3b=derivative(a+step_s*k2a/2,b+step_s*k2b/2,v1,v2)
            k4a,k4b=derivative(a+step_s*k3a,b+step_s*k3b,v1,v2)
            a+=step_s*(k1a+2*k2a+2*k3a+k4a)/6
            b+=step_s*(k1b+2*k2b+2*k3b+k4b)/6
        rows.append([a+ambient_c,b+ambient_c])
    result=np.asarray(rows)
    if not np.isfinite(result).all(): raise ValueError('Nonfinite prediction')
    return result


@dataclass
class QuadraticFit:
    rates:np.ndarray
    training_rmse_c:float
    optimizer_evaluations:int
    validation_rmse_c:float|None=None
    def predict(self,commands,ambient_c=22.):return simulate_quadratic(self.rates,commands,ambient_c)
    def executable_model(self):
        return {'specification':{'type':'two_node_quadratic_loss','sensor_lag':False},
                'estimated_parameters':dict(zip(NAMES,self.rates.tolist()))}
    def to_dict(self):
        return {'executable_model':self.executable_model(),'supplied_family':True,
                'training_rmse_c':self.training_rmse_c,'whole_trial_validation_rmse_c':self.validation_rmse_c,
                'optimizer_evaluations':self.optimizer_evaluations,
                'mechanism_note':'Fitted effective coefficients; no causal or identifiability certificate'}


def execute_quadratic(value,commands,ambient_c=22.):
    if not isinstance(value,dict) or set(value)!={'specification','estimated_parameters'}:
        raise ValueError('Unexpected executable model fields')
    spec=value['specification']; named=value['estimated_parameters']
    if not isinstance(spec,dict) or set(spec)!={'type','sensor_lag'} or spec['type']!='two_node_quadratic_loss' or spec['sensor_lag'] is not False:
        raise ValueError('Unsupported quadratic structure')
    if not isinstance(named,dict) or set(named)!=set(NAMES) or any(type(named[n]) not in (int,float) for n in NAMES):
        raise ValueError('Invalid quadratic parameter names or values')
    return simulate_quadratic([named[n] for n in NAMES],commands,ambient_c)


def fit_quadratic(observations,max_nfev=180):
    if not observations:raise ValueError('No observations')
    trials=[]
    for obs in observations:
        commands=np.asarray(obs['commands_fraction'],dtype=float)
        measured=np.asarray(obs['temperature_c'],dtype=float)
        if obs['sample_interval_s']!=DT or measured.shape!=(len(commands)+1,2) or not np.isfinite(measured).all():
            raise ValueError('Invalid observation interval or temperatures')
        trials.append((commands,measured,obs['ambient_c']))
    def residual(rates):
        return np.concatenate([(simulate_quadratic(rates,u,ambient)[1:]-y[1:]).ravel() for u,y,ambient in trials])
    starts=([.012,.012,.008,.008,.3,.25,.0005,.0005],
            [.025,.008,.016,.005,.4,.2,.001,.001])
    fits=[least_squares(residual,start,bounds=(LOWER,UPPER),x_scale='jac',max_nfev=max_nfev,
                        ftol=1e-7,xtol=1e-7,gtol=1e-7) for start in starts]
    valid=[f for f in fits if f.success and np.isfinite(f.fun).all()]
    if not valid:raise ValueError('Quadratic fit did not converge within budget')
    best=min(valid,key=lambda f:float(f.fun@f.fun))
    return QuadraticFit(best.x,float(np.sqrt(np.mean(best.fun**2))),sum(f.nfev for f in fits))
