"""Bounded, executable heat-flow models fitted only to public observations.

The physical family is supplied by engineering; coefficients are estimated.
This does not discover arbitrary equations or prove mechanism identifiability.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.linalg import expm
from scipy.optimize import least_squares

from .contracts import DT


@dataclass(frozen=True)
class ThermalSpec:
    sensor_lag: bool

    def to_dict(self):
        return {"type": "two_node_thermal", "sensor_lag": self.sensor_lag}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {"type", "sensor_lag"}:
            raise ValueError("Only bounded thermal type and sensor_lag fields are supported")
        if value["type"] != "two_node_thermal" or type(value["sensor_lag"]) is not bool:
            raise ValueError("Unsupported thermal model specification")
        return cls(value["sensor_lag"])

    def bounds(self):
        lower = [.001, .001, .0001, .0001, .05, .05]
        upper = [.05, .05, .05, .05, 1., 1.]
        if self.sensor_lag:
            lower += [.5]
            upper += [35.]
        return np.asarray(lower), np.asarray(upper)

    def parameter_names(self):
        return ["loss_rate_1_per_s", "loss_rate_2_per_s", "coupling_rate_12_per_s",
                "coupling_rate_21_per_s", "heater_gain_1_c_per_s", "heater_gain_2_c_per_s"] + (
                    ["shared_sensor_time_constant_s"] if self.sensor_lag else [])


def discrete_dynamics(spec: ThermalSpec, rates: np.ndarray, sample_interval_s: float = DT):
    lower, upper = spec.bounds()
    rates = np.asarray(rates, dtype=float)
    if rates.shape != lower.shape or not np.isfinite(rates).all() or np.any(rates < lower) or np.any(rates > upper):
        raise ValueError("Thermal parameters outside the supported bounds")
    if not math.isfinite(sample_interval_s) or sample_interval_s <= 0:
        raise ValueError("Invalid measurement interval")
    loss1, loss2, coupling12, coupling21, gain1, gain2 = rates[:6]
    n = 4 if spec.sensor_lag else 2
    a, b = np.zeros((n, n)), np.zeros((n, 2))
    a[:2, :2] = [[-loss1-coupling12, coupling12], [coupling21, -loss2-coupling21]]
    b[0, 0], b[1, 1] = gain1, gain2
    if spec.sensor_lag:
        tau = rates[-1]
        a[2, 0], a[2, 2] = 1 / tau, -1 / tau
        a[3, 1], a[3, 3] = 1 / tau, -1 / tau
    augmented = np.zeros((n + 2, n + 2))
    augmented[:n, :n], augmented[:n, n:] = a, b
    transition = expm(augmented * sample_interval_s)
    return transition[:n, :n], transition[:n, n:]


def simulate(spec: ThermalSpec, rates: np.ndarray, commands, ambient_c=22., sample_interval_s=DT):
    u = np.asarray(commands, dtype=float)
    if u.ndim != 2 or u.shape[1] != 2 or not np.isfinite(u).all() or np.any(u < 0) or np.any(u > .65):
        raise ValueError("Expected bounded finite heater command pairs")
    if not math.isfinite(ambient_c):
        raise ValueError("Ambient temperature must be finite")
    a, b = discrete_dynamics(spec, rates, sample_interval_s)
    state = np.zeros(a.shape[0])
    rows = [state[-2:].copy() + ambient_c]
    for command in u:
        state = a @ state + b @ command
        rows.append(state[-2:].copy() + ambient_c)
    return np.asarray(rows)


@dataclass
class PhysicalFit:
    spec: ThermalSpec
    rates: np.ndarray
    training_rmse_c: float
    sensitivity_rank: int
    scaled_condition_number: float | None
    optimizer_evaluations: int
    validation_rmse_c: float | None = None

    def predict(self, commands, ambient_c=22.):
        return simulate(self.spec, self.rates, commands, ambient_c)

    def executable_model(self):
        return {"specification": self.spec.to_dict(),
                "estimated_parameters": dict(zip(self.spec.parameter_names(), self.rates.tolist()))}

    def to_dict(self):
        return {"specification": self.spec.to_dict(),
                "executable_model": self.executable_model(),
                "parameterization": "effective_rates_not_separate_capacities_and_conductances",
                "estimated_parameters": dict(zip(self.spec.parameter_names(), self.rates.tolist())),
                "training_rmse_c": self.training_rmse_c,
                "whole_trial_validation_rmse_c": self.validation_rmse_c,
                "local_scaled_sensitivity_rank": self.sensitivity_rank,
                "parameter_count": len(self.rates),
                "local_scaled_condition_number": self.scaled_condition_number,
                "rank_note": "numerical local sensitivity heuristic, not a formal identifiability proof",
                "optimizer_evaluations": self.optimizer_evaluations,
                "supplied_family": True,
                "equations": [
                    "d(delta_T1)/dt = gain1*Q1 - loss1*delta_T1 + coupling12*(delta_T2-delta_T1)",
                    "d(delta_T2)/dt = gain2*Q2 - loss2*delta_T2 + coupling21*(delta_T1-delta_T2)",
                ] + (["d(sensor_i)/dt = (delta_Ti-sensor_i)/tau"] if self.spec.sensor_lag else [])}


def fit_physical(observations: list[dict], spec: ThermalSpec, max_nfev=180) -> PhysicalFit:
    if not observations:
        raise ValueError("No observations available for physical fitting")
    # Explicitly copy only observed inputs/outputs. No hidden system label is accepted.
    trials = []
    for observation in observations:
        u = np.asarray(observation["commands_fraction"], dtype=float)
        y = np.asarray(observation["temperature_c"], dtype=float)
        ambient = observation["ambient_c"]
        dt = observation["sample_interval_s"]
        if y.shape != (len(u)+1, 2) or not np.isfinite(y).all():
            raise ValueError("Invalid thermal observation record")
        trials.append((u, y, ambient, dt))

    def residual(rates):
        return np.concatenate([(simulate(spec, rates, u, ambient, dt)[1:] - y[1:]).ravel()
                               for u, y, ambient, dt in trials])

    lower, upper = spec.bounds()
    starts = [[.012, .012, .008, .008, .3, .25], [.025, .008, .016, .005, .4, .2]]
    if spec.sensor_lag:
        starts = [starts[0]+[5.], starts[1]+[20.]]
    fitted = [least_squares(residual, x0, bounds=(lower, upper), x_scale='jac',
                            max_nfev=max_nfev, ftol=1e-7, xtol=1e-7, gtol=1e-7)
              for x0 in starts]
    valid = [f for f in fitted if f.success and np.isfinite(f.fun).all()]
    if not valid:
        raise ValueError("Physical-model optimizer did not converge within its budget")
    best = min(valid, key=lambda f: float(f.fun @ f.fun))
    singular = np.linalg.svd(best.jac * (upper-lower), compute_uv=False)
    rank = int(np.sum(singular > singular[0] * 1e-6)) if len(singular) and singular[0] else 0
    condition = float(singular[0]/singular[-1]) if singular[-1] > 0 else None
    return PhysicalFit(spec, best.x, float(np.sqrt(np.mean(best.fun**2))), rank, condition,
                       sum(f.nfev for f in fitted))


def physical_candidates(observations: list[dict]) -> list[PhysicalFit]:
    models = []
    for lag in (False, True):
        spec = ThermalSpec(lag)
        model = fit_physical(observations, spec)
        if len(observations) >= 2:
            errors = []
            for i, heldout in enumerate(observations):
                reduced = fit_physical(observations[:i]+observations[i+1:], spec)
                predicted = reduced.predict(heldout["commands_fraction"], heldout["ambient_c"])
                errors.append(float(np.sqrt(np.mean((predicted[1:]-np.asarray(heldout["temperature_c"])[1:])**2))))
            model.validation_rmse_c = float(np.mean(errors))
        models.append(model)
    return models


def execute_model(value: dict, commands, ambient_c=22.):
    """Compile a minimal declarative model; unknown structure and code are rejected."""
    if not isinstance(value, dict) or set(value) != {"specification", "estimated_parameters"}:
        raise ValueError("Executable thermal model has unexpected fields")
    spec = ThermalSpec.from_dict(value["specification"])
    named = value["estimated_parameters"]
    if not isinstance(named, dict) or set(named) != set(spec.parameter_names()):
        raise ValueError("Executable thermal parameter names do not match its structure")
    if any(type(named[n]) not in (int, float) for n in spec.parameter_names()):
        raise ValueError("Thermal parameter values must be numerical")
    rates = np.asarray([named[n] for n in spec.parameter_names()], dtype=float)
    return simulate(spec, rates, commands, ambient_c)
