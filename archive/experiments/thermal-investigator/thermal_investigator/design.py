"""Conventional experiment-design criteria using public data and fitted models."""
from __future__ import annotations

import numpy as np

from .predictor import Predictor, features

TEMPERATURE_SCALE_C = 10.0
INFORMATION_REGULARIZATION = 1e-6


def regressors(observation: dict, order: int) -> np.ndarray:
    u = np.asarray(observation["commands_fraction"], dtype=float)
    y = np.asarray(observation["temperature_c"], dtype=float) - observation["ambient_c"]
    return np.asarray([features(y, u, t, order) for t in range(len(u))])


def design_scores(candidates: list[Predictor], observations: list[dict], schedules: list) -> list[dict]:
    if not candidates or not observations or not schedules:
        raise ValueError("Design scoring needs models, observations and legal schedules")
    rows = []
    for plan in schedules:
        predictions, gains = [], []
        for model in candidates:
            p = model.order
            scale = np.asarray([TEMPERATURE_SCALE_C] * (2 * p) + [1.] * (2 * p))
            x = np.vstack([regressors(o, p) for o in observations]) / scale
            base = x.T @ x + INFORMATION_REGULARIZATION * np.eye(4 * p)
            predicted = model.predict(plan.commands())
            future = regressors({"temperature_c": predicted, "ambient_c": 22.,
                                 "commands_fraction": plan.commands()}, p) / scale
            before_sign, before = np.linalg.slogdet(base)
            after_sign, after = np.linalg.slogdet(base + future.T @ future)
            if before_sign <= 0 or after_sign <= 0:
                raise ValueError("Information matrix must be positive definite")
            gains.append(float((after - before) / (4 * p)))
            predictions.append(predicted)
        rows.append({"schedule_id": plan.id, "schedule": plan.to_dict(),
                     "d_optimal_gain_per_parameter": float(np.mean(gains)),
                     "disagreement_c_squared": float(np.var(np.asarray(predictions)[:, 1:], axis=0).mean())})
    return rows


def choose_d_optimal(candidates: list[Predictor], observations: list[dict], schedules: list):
    rows = design_scores(candidates, observations, schedules)
    best = max(rows, key=lambda r: (r["d_optimal_gain_per_parameter"], r["schedule_id"]))
    return next(p for p in schedules if p.id == best["schedule_id"]), {
        "selector": "regularized_d_optimal_regressor_design",
        "gain_per_parameter": best["d_optimal_gain_per_parameter"],
        "assumptions": "linear ARX regressor information approximation; input-output noise is not whitened",
        "scores": rows,
    }
