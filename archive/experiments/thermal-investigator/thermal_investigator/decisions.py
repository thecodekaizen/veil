"""Public decision contract. Future evaluation measurements never enter this context."""
from __future__ import annotations

from .design import design_scores


UNCERTAINTY = ("provisional", "validated_within_observed_range", "insufficient_evidence")


def public_context(observations, candidates, plans, *, decisions=(), final=False):
    public = []
    for obs in observations:
        # Deliberate allowlist: do not serialize a lab/client/config object.
        public.append({key: obs[key] for key in (
            "observation_id", "source", "ambient_c", "sample_interval_s", "noise_std_c",
            "commands_fraction", "temperature_c", "actions_remaining", "reset_policy",
            "reset_charge_s", "experiment_s")})
    return {
        "goal": "Minimize future two-sensor temperature prediction error within the remaining experiment budget.",
        "phase": "submit_predictor" if final else "choose_experiment",
        "observations": public,
        "candidate_models": [model.to_dict() for model in candidates],
        "legal_experiment_scores": [] if final else design_scores(candidates, observations, plans),
        "previous_decisions": list(decisions),
        "constraints": {
            "source": "simulation", "allowed_model_orders": [model.order for model in candidates],
            "legal_schedule_ids": ["submit"] if final else [plan.id for plan in plans],
            "model_families_are_supplied": True,
            "causal_mechanism_not_identified_by_arx": True,
            "candidate_disagreement_is_not_calibrated_uncertainty": True,
            "d_optimality_is_an_approximation": True,
        },
    }


def decision_schema(context):
    return {"type": "object", "properties": {
        "schedule_id": {"type": "string", "enum": context["constraints"]["legal_schedule_ids"]},
        "model_order": {"type": "integer", "enum": context["constraints"]["allowed_model_orders"]},
        "rationale": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string", "enum": [o["observation_id"] for o in context["observations"]]}},
        "uncertainty": {"type": "string", "enum": list(UNCERTAINTY)},
    }, "required": ["schedule_id", "model_order", "rationale", "evidence_ids", "uncertainty"],
        "additionalProperties": False}


def validate_decision(value, context):
    fields = {"schedule_id", "model_order", "rationale", "evidence_ids", "uncertainty"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("Decision fields do not match the contract")
    if value["schedule_id"] not in context["constraints"]["legal_schedule_ids"]:
        raise ValueError("Unknown, repeated or unavailable experiment")
    if type(value["model_order"]) is not int or value["model_order"] not in context["constraints"]["allowed_model_orders"]:
        raise ValueError("Unsupported model family")
    if not isinstance(value["rationale"], str) or not 1 <= len(value["rationale"].strip()) <= 2000:
        raise ValueError("Decision needs a bounded explanation")
    ids = value["evidence_ids"]
    known = {o["observation_id"] for o in context["observations"]}
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in known for i in ids):
        raise ValueError("Decision must cite available observations")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate evidence references")
    if value["uncertainty"] not in UNCERTAINTY:
        raise ValueError("Unknown uncertainty status")
    return value


def instructions(strategy):
    base = (
        "You are selecting experiments and numerical predictor families for an unfamiliar thermal system. "
        "Use the supplied measurements and numerical tools' results. Supplied ARX families are predictive "
        "models, not identified physical mechanisms. Do not claim exact physical causes from their order. "
        "Choose an available schedule, or submit in the final phase. Cite observation IDs. "
        "Your model_order determines the submitted forecast in the final phase. "
        "D-optimal regressor gain approximates parameter information; prediction disagreement is not calibrated uncertainty. "
        "Do not infer future measurements or hidden parameters. Return the required JSON decision. "
    )
    if strategy == "meta_direct":
        return base
    if strategy == "meta_investigator":
        return base + (
            "Maintain a consistent investigation across previous decisions. Compare your prior working family "
            "with the observed fit and whole-trial validation evidence. Revise it when the evidence supports "
            "another predictive structure. Explain which unresolved predictive ambiguity your next experiment "
            "would address, or why it should improve input excitation. Keep unverified interpretations provisional. "
        )
    raise ValueError("Unknown Meta strategy")
