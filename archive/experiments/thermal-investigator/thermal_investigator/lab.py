"""Hidden simulation/evaluation process. Agent-facing tools must not import this module.

Original lumped linear heat-balance implementation inspired by standard thermal
models, not copied from TCLab and not validated against its hardware.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import sys
import uuid

import numpy as np

from .contracts import DT, MAX_TEMPERATURE_C, RESET_SECONDS, Schedule


@dataclass(frozen=True)
class ThermalParameters:
    c1: float
    c2: float
    loss1: float
    loss2: float
    coupling: float
    heater1_w: float
    heater2_w: float
    sensor_tau: float


def parameters(seed: int, delayed: bool) -> ThermalParameters:
    rng = np.random.default_rng(seed)
    return ThermalParameters(
        float(rng.uniform(4, 8)), float(rng.uniform(5, 10)),
        float(rng.uniform(.035, .075)), float(rng.uniform(.035, .075)),
        float(rng.uniform(.025, .065)), float(rng.uniform(1.7, 2.3)),
        float(rng.uniform(1.5, 2.1)), float(rng.uniform(5, 14)) if delayed else 0.0,
    )


def derivative(state: np.ndarray, command: np.ndarray, p: ThermalParameters) -> np.ndarray:
    a, b, sensed_a, sensed_b = state
    da = (p.heater1_w * command[0] - p.loss1 * a - p.coupling * (a - b)) / p.c1
    db = (p.heater2_w * command[1] - p.loss2 * b - p.coupling * (b - a)) / p.c2
    if p.sensor_tau:
        return np.array([da, db, (a - sensed_a) / p.sensor_tau, (b - sensed_b) / p.sensor_tau])
    return np.array([da, db, da, db])


def trajectory(commands: np.ndarray, p: ThermalParameters, ambient: float = 22.0,
               step: float = .25) -> np.ndarray:
    state = np.zeros(4)
    outputs = [state[2:].copy() + ambient]
    for command in commands:
        for _ in range(round(DT / step)):
            k1 = derivative(state, command, p)
            k2 = derivative(state + step * k1 / 2, command, p)
            k3 = derivative(state + step * k2 / 2, command, p)
            k4 = derivative(state + step * k3, command, p)
            state += step * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            if not np.isfinite(state).all() or max(state[:2] + ambient) > MAX_TEMPERATURE_C:
                raise ValueError("Temperature envelope exceeded")
        outputs.append(state[2:].copy() + ambient)
    return np.asarray(outputs)


class Lab:
    def __init__(self, seed: int, delayed: bool, max_actions: int = 4):
        self._params = parameters(seed, delayed)
        self._noise_seed = seed
        self._actions = 0
        self._max_actions = max_actions
        self._challenge_used = False
        self._session_id = str(uuid.uuid4())

    def run(self, value: dict) -> dict:
        if self._challenge_used:
            raise ValueError("Investigation closed after challenge disclosure")
        if self._actions >= self._max_actions:
            raise ValueError("Experiment action budget exhausted")
        self._actions += 1  # malformed attempts also consume a slot
        plan = Schedule.from_dict(value)
        commands = np.asarray(plan.commands())
        clean = trajectory(commands, self._params)
        # Same noise for the same physical input across strategies, independent of call order.
        digest = hashlib.sha256(commands.tobytes()).digest()
        entropy = [self._noise_seed, int.from_bytes(digest[:4], "big")]
        rng = np.random.default_rng(np.random.SeedSequence(entropy))
        measured = clean + rng.normal(0, .08, clean.shape)
        measured[0] = 22.0  # idealized reset fixture, disclosed in experiment metadata
        return {
            "session_id": self._session_id, "observation_id": str(uuid.uuid4()),
            "source": "simulation", "ambient_c": 22.0, "sample_interval_s": DT,
            "noise_std_c": .08, "reset_policy": "idealized_exact_ambient",
            "reset_charge_s": RESET_SECONDS, "experiment_s": len(commands) * DT,
            "actions_remaining": self._max_actions - self._actions,
            "commands_fraction": commands.tolist(), "temperature_c": measured.tolist(),
            "command_energy_proxy_fraction_seconds": float(commands.sum() * DT),
        }

    def challenge(self, prediction: dict) -> dict:
        if self._challenge_used:
            raise ValueError("Challenge already revealed")
        candidate = np.asarray(prediction["temperature_c"], dtype=float)
        if candidate.shape != (61, 2) or not np.isfinite(candidate).all():
            raise ValueError("Prediction must contain 61 finite temperature pairs")
        self._challenge_used = True
        commands = challenge_commands()
        clean = trajectory(commands, self._params)
        rmse = np.sqrt(np.mean((candidate - clean) ** 2, axis=0))
        return {
            "source": "simulation", "score_target": "noise_free_latent_sensor_trace",
            "rmse_c_by_sensor": rmse.tolist(), "mean_rmse_c": float(rmse.mean()),
            "fixed_normalization_c": 10.0, "normalized_rmse": float(rmse.mean() / 10),
            "temperature_c": clean.tolist(),
        }


def challenge_commands() -> np.ndarray:
    # Input is public before prediction; future outputs and hidden parameters remain sealed.
    return np.asarray([[a, b] for a, b in [(.1, .5), (.5, .2), (.2, .6), (0., .15)] for _ in range(15)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--delayed", action="store_true")
    parser.add_argument("--max-actions", type=int, default=4)
    args = parser.parse_args()
    lab = Lab(args.seed, args.delayed, args.max_actions)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request["operation"] == "experiment":
                result = lab.run(request["schedule"])
            elif request["operation"] == "challenge_inputs":
                result = {"commands_fraction": challenge_commands().tolist(), "ambient_c": 22.0}
            elif request["operation"] == "challenge":
                result = lab.challenge(request["prediction"])
            else:
                raise ValueError("Unknown operation")
            response = {"ok": True, "result": result}
        except (ValueError, TypeError, KeyError) as exc:
            response = {"ok": False, "error": str(exc)}
        print(json.dumps(response, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
