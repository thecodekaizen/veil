"""Raw-archive temporal discovery with deterministic evidence validation."""

from __future__ import annotations

from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from .cli import DatasetError
from .config import model_api_key

MODEL = "muse-spark-1.3"
PROMPT_VERSION = "raw-temporal-discovery-v4"
REASONING_EFFORT = "minimal"
MAX_OUTPUT_TOKENS = 4096
DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "datasets" / "synthetic" / "creative-evolution.json"
REPO_CACHE_DIR = Path(__file__).resolve().parents[2] / ".thread-cache"
_cache_dir = Path(os.environ.get("THREAD_CACHE_DIR", str(REPO_CACHE_DIR))).expanduser()
CACHE_DIR = _cache_dir if _cache_dir.is_absolute() else REPO_CACHE_DIR.parent / _cache_dir

PROMPT = (
    "You are THREAD, a careful archivist of creative projects. Review the dated raw artifacts "
    "for one project and identify any meaningful evolution in the project's focus over time. "
    "If evidence is insufficient, say so and leave candidate_finding empty. Separate direct "
    "observations from interpretation. Cite only supplied artifact IDs and exact dates. Include "
    "evidence that complicates the interpretation. Do not infer the creator's personality or "
    "invent causes. For each observation, classify its evidence stage using only explicit wording: "
    "planned (an intention or proposal), experimental (a test, prototype, pilot, or rehearsal), "
    "ongoing (active practice without evidence of a completed release), released (a completed "
    "or publicly issued deliverable), or unclear (the source does not establish status). Never "
    "upgrade a plan or experiment to ongoing or released. Phrase an interpretation as a tentative hypothesis (for example, use "
    "'appears to' rather than stating an inference as settled fact)."
)

EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "artifact_id": {"type": "string"},
        "date": {"type": "string"},
        "relevance": {"type": "string"},
    },
    "required": ["artifact_id", "date", "relevance"],
    "additionalProperties": False,
}
OBSERVATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "artifact_id": {"type": "string"},
        "date": {"type": "string"},
        "observation": {"type": "string"},
        "evidence_stage": {
            "type": "string",
            "enum": ["planned", "experimental", "ongoing", "released", "unclear"],
        },
    },
    "required": ["artifact_id", "date", "observation", "evidence_stage"],
    "additionalProperties": False,
}
DISCOVERY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "observations": {"type": "array", "items": OBSERVATION_SCHEMA},
        "candidate_finding": {"type": "string"},
        "supporting_artifacts": {"type": "array", "items": EVIDENCE_SCHEMA},
        "complicating_artifacts": {"type": "array", "items": EVIDENCE_SCHEMA},
        "limitations": {"type": "string"},
    },
    "required": [
        "observations", "candidate_finding", "supporting_artifacts",
        "complicating_artifacts", "limitations",
    ],
    "additionalProperties": False,
}

# A small output gate catches the specific failure observed in the preregistered
# run. This is a wording check only; it does not establish calibrated confidence.
TENTATIVE_LANGUAGE = re.compile(
    r"\b(?:appears?\s+to|seems?\s+to|may|might|could|possibly|potentially|"
    r"suggests?|tentatively|one\s+possible\s+(?:interpretation|explanation|pattern)|"
    r"a\s+possible\s+(?:interpretation|evolution|pattern|shift)|"
    r"consistent\s+with)\b",
    re.IGNORECASE,
)


class DiscoveryValidationError(ValueError):
    """Model output cannot be safely tied back to the supplied archive."""


def load_raw_archive(path: Path = DEFAULT_DATASET) -> dict[str, Any]:
    """Read source artifacts only; never pass cached memories or labels to Muse."""
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DatasetError("unreadable", f"cannot read dataset {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetError("invalid_json", f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(source, dict) or source.get("schema_version") != 1:
        raise DatasetError("schema", "dataset must declare schema_version: 1")
    project = source.get("project")
    artifacts = source.get("artifacts")
    if not isinstance(project, dict) or not project.get("id") or not project.get("title"):
        raise DatasetError("project", "dataset must include project.id and project.title")
    if not isinstance(artifacts, list) or not artifacts:
        raise DatasetError("artifacts", "dataset must include a non-empty artifacts list")

    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise DatasetError("artifact_shape", "each artifact must be a JSON object")
        required = ("id", "date", "modality", "title", "content")
        missing = [field for field in required if not isinstance(item.get(field), str) or not item[field]]
        if missing:
            raise DatasetError("artifact_fields", f"artifact is missing non-empty field(s): {', '.join(missing)}")
        artifact_id = item["id"]
        if artifact_id in seen:
            raise DatasetError("duplicate_source", f"artifact ID appears more than once: {artifact_id}")
        seen.add(artifact_id)
        try:
            parsed_date = date.fromisoformat(item["date"])
        except ValueError as exc:
            raise DatasetError("invalid_date", f"artifact {artifact_id!r} has invalid date {item['date']!r}") from exc
        if parsed_date.isoformat() != item["date"]:
            raise DatasetError("invalid_date", f"artifact {artifact_id!r} date must use YYYY-MM-DD")
        # Explicit projection is the leakage boundary: all other source-file keys are dropped.
        cleaned.append({field: item[field] for field in required})

    cleaned.sort(key=lambda item: (item["date"], item["id"]))
    return {
        "project": {"id": str(project["id"]), "title": str(project["title"])},
        "artifacts": cleaned,
    }


def validate_discovery(value: Any, archive: dict[str, Any]) -> dict[str, Any]:
    """Validate response shape and prove each citation refers to the supplied source."""
    if not isinstance(value, dict):
        raise DiscoveryValidationError("discovery response must be a JSON object")
    required = set(DISCOVERY_SCHEMA["required"])
    if set(value) != required:
        raise DiscoveryValidationError("discovery response has missing or unexpected fields")
    if not isinstance(value["candidate_finding"], str) or not isinstance(value["limitations"], str):
        raise DiscoveryValidationError("candidate_finding and limitations must be strings")
    candidate_finding = value["candidate_finding"].strip()
    if candidate_finding and not TENTATIVE_LANGUAGE.search(candidate_finding):
        raise DiscoveryValidationError(
            "candidate finding must use explicit tentative wording; no finding was emitted"
        )
    for key in ("observations", "supporting_artifacts", "complicating_artifacts"):
        if not isinstance(value[key], list):
            raise DiscoveryValidationError(f"{key} must be a list")

    source_by_id = {item["id"]: item for item in archive["artifacts"]}
    for observation in value["observations"]:
        if not isinstance(observation, dict) or set(observation) != {
            "artifact_id", "date", "observation", "evidence_stage"
        }:
            raise DiscoveryValidationError(
                "each observation must include artifact_id, date, observation, and evidence_stage"
            )
        artifact_id = observation["artifact_id"]
        observed_date = observation["date"]
        if not isinstance(artifact_id, str) or not isinstance(observed_date, str):
            raise DiscoveryValidationError("observation artifact_id and date must be strings")
        source = source_by_id.get(artifact_id)
        if source is None or observed_date != source["date"]:
            raise DiscoveryValidationError("observation cites an unknown artifact or mismatched date")
        if not isinstance(observation["observation"], str) or not observation["observation"].strip():
            raise DiscoveryValidationError("observation text must be non-empty")
        evidence_stage = observation["evidence_stage"]
        if not isinstance(evidence_stage, str) or evidence_stage not in {
            "planned", "experimental", "ongoing", "released", "unclear"
        }:
            raise DiscoveryValidationError("observation evidence_stage must be a recognized stage")

    def validate_refs(key: str) -> list[dict[str, str]]:
        refs: list[dict[str, str]] = []
        seen: set[str] = set()
        for ref in value[key]:
            if not isinstance(ref, dict) or set(ref) != {"artifact_id", "date", "relevance"}:
                raise DiscoveryValidationError(f"each {key} entry must include artifact_id, date, and relevance")
            artifact_id = ref["artifact_id"]
            cited_date = ref["date"]
            if not isinstance(artifact_id, str) or not isinstance(cited_date, str):
                raise DiscoveryValidationError(f"{key} artifact_id and date must be strings")
            source = source_by_id.get(artifact_id)
            if source is None or cited_date != source["date"]:
                raise DiscoveryValidationError(f"{key} cites an unknown artifact or mismatched date")
            if artifact_id in seen:
                raise DiscoveryValidationError(f"{key} contains a duplicate artifact citation")
            seen.add(artifact_id)
            if not isinstance(ref["relevance"], str) or not ref["relevance"].strip():
                raise DiscoveryValidationError(f"{key} relevance must be non-empty")
            refs.append(ref)
        return refs

    support = validate_refs("supporting_artifacts")
    validate_refs("complicating_artifacts")
    if value["candidate_finding"].strip():
        if len(support) < 2:
            raise DiscoveryValidationError("an evolution hypothesis needs at least two cited artifacts")
        if len({ref["date"] for ref in support}) < 2:
            raise DiscoveryValidationError("an evolution hypothesis needs evidence from distinct dates")
        chronologically_ordered = sorted(archive["artifacts"], key=lambda item: (item["date"], item["id"]))
        quarter_size = max(1, (len(chronologically_ordered) + 3) // 4)
        earliest_ids = {item["id"] for item in chronologically_ordered[:quarter_size]}
        latest_ids = {item["id"] for item in chronologically_ordered[-quarter_size:]}
        supporting_ids = {ref["artifact_id"] for ref in support}
        if not supporting_ids & earliest_ids or not supporting_ids & latest_ids:
            raise DiscoveryValidationError(
                "No sufficiently supported evolution finding: supporting artifacts must anchor both the earliest and latest timeline quarters"
            )
    return {
        **value,
        "project": archive["project"],
        "human_confirmation_required": True,
    }


def _load_api_key() -> str | None:
    return model_api_key()


def _estimated_cost(input_chars: int) -> float:
    # Conservative token estimate and reserve the full visible+reasoning output cap.
    input_tokens = int(input_chars / 2.5 + 0.999)
    return (input_tokens * 1.25 + MAX_OUTPUT_TOKENS * 4.25) / 1_000_000


def _cumulative_spend(usage_file: Path) -> float:
    total = 0.0
    try:
        for line in usage_file.read_text(encoding="utf-8").splitlines():
            total += float(json.loads(line).get("estimated_usd", 0))
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return total


def discover_raw_archive(path: Path = DEFAULT_DATASET) -> dict[str, Any]:
    """Ask Muse to discover from raw artifacts, then validate all source references."""
    archive = load_raw_archive(path)
    model_input = json.dumps(archive, ensure_ascii=False, indent=2)
    cache_key = hashlib.sha256(
        f"{MODEL}:{PROMPT_VERSION}:{REASONING_EFFORT}:{MAX_OUTPUT_TOKENS}:{PROMPT}:{model_input}".encode("utf-8")
    ).hexdigest()
    cache_file = CACHE_DIR / "raw-discoveries.json"
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    if cache_key in cache:
        cached = cache[cache_key]
        if isinstance(cached, dict) and cached.get("_invalid_output"):
            raise DiscoveryValidationError(
                cached.get("_error", "cached Muse output was rejected; no repeat call was made")
            )
        if cached is None:
            raise DiscoveryValidationError(
                "cached Muse output is invalid; no repeat call was made"
            )
        return {
            **validate_discovery(cached, archive),
            "provider": "meta-cache",
            "model": MODEL,
        }

    api_key = _load_api_key()
    if not api_key:
        raise ValueError("set MODEL_API_KEY in the local .env file or shell before using --raw-muse")
    try:
        from openai import APIConnectionError, OpenAI
    except ImportError as exc:
        raise ValueError("Meta mode needs the optional dependency: pip install -e '.[meta]'") from exc

    usage_file = CACHE_DIR / "usage.jsonl"
    budget = float(os.environ.get("THREAD_BUDGET_USD", "150"))
    projected = _estimated_cost(len(PROMPT) + len(model_input))
    if _cumulative_spend(usage_file) + projected > budget:
        raise ValueError(f"local cost estimate would exceed THREAD_BUDGET_USD=${budget:.2f}")

    client = OpenAI(api_key=api_key, base_url="https://api.meta.ai/v1", max_retries=0)
    try:
        response = client.responses.create(
            model=MODEL,
            reasoning={"effort": REASONING_EFFORT},
            max_output_tokens=MAX_OUTPUT_TOKENS,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "thread_temporal_discovery",
                    "strict": True,
                    "schema": DISCOVERY_SCHEMA,
                }
            },
            input=f"{PROMPT}\n\nDated archive (raw source artifacts):\n{model_input}",
        )
    except APIConnectionError as exc:
        raise ValueError(
            "Could not connect to the Meta Model API (network, DNS, TLS, or timeout). "
            "Automatic retries are disabled to avoid repeating a potentially billable request. "
            "The CLI received no response, so check Meta Billing before retrying."
        ) from exc
    output_text = response.output_text
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    usage_file.parent.mkdir(parents=True, exist_ok=True)
    estimated = (input_tokens * 1.25 + output_tokens * 4.25) / 1_000_000
    with usage_file.open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps({
            "model": MODEL,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_usd": estimated,
            "source": "raw-discovery",
        }) + "\n")
    status = getattr(response, "status", None)
    incomplete_details = getattr(response, "incomplete_details", None)
    incomplete_reason = getattr(incomplete_details, "reason", None)

    def cache_rejected_output(message: str) -> str:
        cached_error = f"{message}; cached to avoid a repeat charge"
        cache[cache_key] = {
            "_invalid_output": True,
            "_error": cached_error,
            "raw": output_text,
            "status": status,
            "incomplete_reason": incomplete_reason,
        }
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return cached_error

    if incomplete_reason or (status is not None and status != "completed"):
        message = (
            "Muse response was incomplete or unsuccessful "
            f"(status={status or 'unknown'}, reason={incomplete_reason or 'unknown'})"
        )
        raise DiscoveryValidationError(cache_rejected_output(message))

    try:
        parsed = json.loads(output_text)
    except (TypeError, json.JSONDecodeError) as exc:
        # Cache malformed output too, so an invalid completion cannot trigger
        # another paid call every time the same archive is retried.
        message = (
            "Muse returned invalid JSON "
            f"(status={status or 'unknown'}, reason={incomplete_reason or 'unknown'})"
        )
        raise DiscoveryValidationError(cache_rejected_output(message)) from exc
    cache[cache_key] = parsed
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    # Persist usage and raw output before validation: invalid model results are
    # still billable and must not cause a silent repeat charge.
    result = validate_discovery(parsed, archive)
    return {
        **result,
        "provider": "meta",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "response": {"status": status, "incomplete_reason": incomplete_reason},
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_usd": round(estimated, 6),
            "cumulative_estimated_usd": round(_cumulative_spend(usage_file), 6),
        },
    }
