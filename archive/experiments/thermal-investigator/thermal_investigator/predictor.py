"""Numerical prediction baseline; contains no simulator imports or hidden labels."""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


@dataclass
class Predictor:
    order: int
    ridge: float
    coefficients: np.ndarray
    training_rmse_c: float
    validation_rmse_c: float | None
    spectral_radius: float
    validation_status: str = "not_available_single_trial"

    def predict(self, commands: list | np.ndarray, ambient: float = 22.0) -> np.ndarray:
        u = np.asarray(commands, dtype=float)
        if u.ndim != 2 or u.shape[1] != 2 or not np.isfinite(u).all():
            raise ValueError("Expected finite pairs of heater commands")
        y = [np.zeros(2)]
        for t in range(len(u)):
            x = features(y, u, t, self.order)
            following = x @ self.coefficients
            if not np.isfinite(following).all() or np.abs(following).max() > 1e4:
                raise ValueError("Numerical prediction diverged")
            y.append(following)
        return np.asarray(y) + ambient

    def to_dict(self) -> dict:
        return {
            "family": f"autoregressive_order_{self.order}", "order": self.order,
            "ridge": self.ridge, "coefficients": self.coefficients.tolist(),
            "training_rmse_c": self.training_rmse_c,
            "whole_trial_validation_rmse_c": self.validation_rmse_c,
            "spectral_radius": self.spectral_radius, "validation_status": self.validation_status,
            "mechanistic_interpretation": "not established by this predictor",
        }


def features(y, u, t: int, order: int) -> np.ndarray:
    outputs = [y[t - i] if t >= i else np.zeros(2) for i in range(order)]
    inputs = [u[t - i] if t >= i else np.zeros(2) for i in range(order)]
    return np.concatenate(outputs + inputs)


def fit_one(observations: list[dict], order: int, ridge: float) -> Predictor:
    if type(order) is not int or order not in (1, 2):
        raise ValueError("Unsupported predictor order")
    if not math.isfinite(ridge) or ridge <= 0:
        raise ValueError("Regularization must be finite and positive")
    xs, targets = [], []
    for obs in observations:
        u = np.asarray(obs["commands_fraction"], dtype=float)
        y = np.asarray(obs["temperature_c"], dtype=float) - obs["ambient_c"]
        if y.shape != (len(u) + 1, 2) or not np.isfinite(y).all():
            raise ValueError("Invalid observation shape or nonfinite temperature")
        for t in range(len(u)):
            xs.append(features(y, u, t, order))
            targets.append(y[t + 1])
    x, target = np.asarray(xs), np.asarray(targets)
    if len(x) == 0:
        raise ValueError("No fitting observations")
    # Use an augmented least-squares solve rather than squaring the condition number.
    penalty = np.sqrt(ridge) * np.eye(4 * order)
    beta = np.linalg.lstsq(np.vstack([x, penalty]),
                           np.vstack([target, np.zeros((4 * order, 2))]), rcond=None)[0]
    companion = np.zeros((2 * order, 2 * order))
    companion[:2] = beta[:2 * order].T
    if order > 1:
        companion[2:, :-2] = np.eye(2 * (order - 1))
    radius = float(np.max(np.abs(np.linalg.eigvals(companion))))
    if not math.isfinite(radius) or radius >= 1.0:
        raise ValueError("Fitted free-response dynamics are unstable")
    return Predictor(order, ridge, beta, float(np.sqrt(np.mean((x @ beta - target) ** 2))), None, radius)


def trial_error(model: Predictor, observation: dict) -> float:
    predicted = model.predict(observation["commands_fraction"], observation["ambient_c"])
    measured = np.asarray(observation["temperature_c"])
    return float(np.sqrt(np.mean((predicted[1:] - measured[1:]) ** 2)))


def fit_candidates(observations: list[dict]) -> list[Predictor]:
    candidates = []
    for order in (1, 2):
        choices = []
        for ridge in (.001, .01, .1, 1.0):
            try:
                full = fit_one(observations, order, ridge)
                if len(observations) >= 2:
                    errors = []
                    invalid_folds = 0
                    for i, heldout in enumerate(observations):
                        try:
                            reduced = fit_one(observations[:i] + observations[i + 1:], order, ridge)
                            errors.append(trial_error(reduced, heldout))
                        except (ValueError, np.linalg.LinAlgError):
                            invalid_folds += 1
                    if invalid_folds:
                        # A stable full fit may exist even when a reduced-data fold
                        # is underdetermined. Keep it provisional, with no CV claim.
                        full.validation_status = "incomplete_unstable_reduced_fit"
                        score = 1e6 + invalid_folds + abs(math.log10(ridge) + 1)
                    else:
                        full.validation_status = "whole_trial_leave_one_out"
                        full.validation_rmse_c = float(np.mean(errors))
                        score = full.validation_rmse_c
                else:
                    # No independent trial exists yet; use a disclosed fixed regularization prior.
                    score = abs(math.log10(ridge) + 1)
                choices.append((score, ridge, full))
            except (ValueError, np.linalg.LinAlgError):
                continue
        if choices:
            candidates.append(min(choices, key=lambda c: (c[0], c[1]))[2])
    if not candidates:
        raise ValueError("No numerically valid candidate could be fitted")
    return candidates


def select_model(candidates: list[Predictor]) -> Predictor:
    # A simpler initial predictor is a declared prior, not a hidden evaluation decision.
    return min(candidates, key=lambda m: (
        0 if m.validation_rmse_c is not None else 1,
        m.validation_rmse_c if m.validation_rmse_c is not None else 0., m.order))


def choose_disagreement(candidates: list[Predictor], schedules: list) -> tuple[object, dict]:
    scored = []
    for plan in schedules:
        predictions = np.asarray([m.predict(plan.commands()) for m in candidates])
        score = float(np.mean(np.var(predictions[:, 1:], axis=0)))
        scored.append((score, plan))
    # Disagreement is a heuristic across families, not calibrated information gain.
    score, plan = max(scored, key=lambda p: (p[0], p[1].id))
    return plan, {"selector": "between_family_prediction_disagreement",
                  "disagreement_c_squared": score,
                  "candidate_count": len(candidates), "calibrated_uncertainty": False}
