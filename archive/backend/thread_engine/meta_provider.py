"""Muse Spark adapter for converting source artifacts into typed memories."""

from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Any

from .contracts import Memory
from .config import model_api_key

MODEL = "muse-spark-1.3"
PROJECT_PROMPT_VERSION = "project-memory-extraction-v1"
PROJECT_MAX_OUTPUT_TOKENS = 4096

THEMES_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "string", "minLength": 1, "maxLength": 40, "pattern": "^[a-z0-9][a-z0-9 -]*$"},
    "maxItems": 3,
}

PROJECT_MEMORY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "memories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "themes": THEMES_SCHEMA,
                },
                "required": ["source_id", "summary", "themes"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["memories"],
    "additionalProperties": False,
}


class MetaModelProvider:
    """Extract a project's auditable temporal memories with Muse Spark."""

    def __init__(self, *, api_key: str, model: str = MODEL, cache_dir: Path | None = None) -> None:
        try:
            from openai import APIConnectionError, OpenAI
        except ImportError as exc:
            raise ValueError("Meta mode needs the optional dependency: pip install -e '.[meta]'") from exc
        self.client = OpenAI(api_key=api_key, base_url="https://api.meta.ai/v1", max_retries=0)
        self._api_connection_error = APIConnectionError
        self.model = model
        repo_cache_dir = Path(__file__).resolve().parents[2] / ".thread-cache"
        configured_cache_dir = cache_dir or Path(os.environ.get("THREAD_CACHE_DIR", str(repo_cache_dir))).expanduser()
        self.cache_dir = (
            configured_cache_dir
            if configured_cache_dir.is_absolute()
            else repo_cache_dir.parent / configured_cache_dir
        )
        self.usage_file = self.cache_dir / "usage.jsonl"
        self.budget_usd = float(os.environ.get("THREAD_BUDGET_USD", "150"))
        self.run_usage: dict[str, int | float] = {
            "requests": 0, "cache_hits": 0, "input_tokens": 0,
            "cached_input_tokens": 0, "output_tokens": 0, "estimated_usd": 0.0,
        }

    @classmethod
    def from_env(cls) -> "MetaModelProvider":
        api_key = model_api_key()
        if not api_key:
            raise ValueError("set MODEL_API_KEY in the local .env file or shell")
        return cls(api_key=api_key, model=os.environ.get("THREAD_META_MODEL", MODEL))

    def extract_project(self, archive: dict[str, Any]) -> list[Memory]:
        """Extract all project memories together so theme tags share one context."""
        project = archive["project"]
        artifacts = archive["artifacts"]
        artifact_by_id = {item["id"]: item for item in artifacts}
        encoded_archive = json.dumps(archive, ensure_ascii=False, sort_keys=True)
        cache_key = sha256(
            f"{self.model}:{PROJECT_PROMPT_VERSION}:{encoded_archive}".encode()
        ).hexdigest()
        cache_file = self.cache_dir / "project-memories.json"
        cache: dict[str, Any] = {}
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cache = {}
        if not isinstance(cache, dict):
            cache = {}
        if cache_key in cache:
            cached = cache[cache_key]
            if isinstance(cached, dict) and "_invalid_output" in cached:
                raise ValueError(cached.get("_error", "cached project memory output was rejected"))
            self.run_usage["cache_hits"] += 1
            return [Memory.from_dict(item) for item in cached]

        input_chars = len(encoded_archive) + 1200
        projected_input_tokens = input_chars / 2.5
        contributor = self.model.endswith("-contributor")
        input_rate, output_rate = ((0.10, 0.20) if contributor else (1.25, 4.25))
        projected_cost = (
            projected_input_tokens * input_rate + PROJECT_MAX_OUTPUT_TOKENS * output_rate
        ) / 1_000_000
        if self.cumulative_estimated_usd() + projected_cost > self.budget_usd:
            raise ValueError(
                f"local cost estimate would exceed THREAD_BUDGET_USD=${self.budget_usd:.2f}; "
                "review billing and usage before continuing"
            )

        schema = json.loads(json.dumps(PROJECT_MEMORY_SCHEMA))
        schema["properties"]["memories"]["items"]["properties"]["source_id"]["enum"] = list(artifact_by_id)
        prompt = (
            "Extract one concise, neutral temporal memory for every artifact in this single project's archive. "
            "Use only explicit source evidence. Create up to three short lowercase topic tags per memory. "
            "Because you can see the entire archive, use the same tag for the same recurring project concept "
            "across dates; prefer stable project themes over one-off details or generic media labels. "
            "Do not infer creator personality, motivations, or causes. Preserve uncertainty in each summary. "
            "Return exactly one memory per source artifact. The application will copy dates and other provenance "
            "from the source archive; do not invent them."
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                reasoning={"effort": "minimal"},
                max_output_tokens=PROJECT_MAX_OUTPUT_TOKENS,
                text={"format": {
                    "type": "json_schema",
                    "name": "project_temporal_memories",
                    "strict": True,
                    "schema": schema,
                }},
                input=f"{prompt}\n\nRaw project archive:\n{encoded_archive}",
            )
        except self._api_connection_error as exc:
            raise ValueError(
                "Could not connect to the Meta Model API (network, DNS, TLS, or timeout). "
                "Automatic retries are disabled to avoid repeating a potentially billable request. "
                "The CLI received no response, so check Meta Billing before retrying."
            ) from exc
        content = response.output_text
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        details = getattr(usage, "input_tokens_details", None)
        cached_tokens = int(getattr(details, "cached_tokens", 0) or 0)
        cached_rate = 0.002 if contributor else 0.15
        estimated_usd = (
            max(input_tokens - cached_tokens, 0) * input_rate
            + cached_tokens * cached_rate
            + output_tokens * output_rate
        ) / 1_000_000
        self.run_usage["requests"] += 1
        self.run_usage["input_tokens"] += input_tokens
        self.run_usage["cached_input_tokens"] += cached_tokens
        self.run_usage["output_tokens"] += output_tokens
        self.run_usage["estimated_usd"] += estimated_usd

        status = getattr(response, "status", None)
        incomplete = getattr(response, "incomplete_details", None)
        incomplete_reason = getattr(incomplete, "reason", None)
        error_message = "Meta model returned no project memories" if not content else "Meta project memories were rejected"
        if status or incomplete_reason:
            error_message += f" (status={status or 'unknown'}, reason={incomplete_reason or 'unknown'})"
        cache[cache_key] = {
            "_invalid_output": True,
            "_error": f"{error_message}; cached to avoid a repeat charge",
            "raw": content,
            "status": status,
            "incomplete_reason": incomplete_reason,
        }
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        with self.usage_file.open("a", encoding="utf-8") as ledger:
            ledger.write(json.dumps({
                "model": self.model,
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_tokens,
                "output_tokens": output_tokens,
                "estimated_usd": estimated_usd,
                "source": "project-memory-extraction",
            }) + "\n")

        if not content:
            raise ValueError(cache[cache_key]["_error"])
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Meta model returned invalid project memory JSON; cached to avoid a repeat charge") from exc
        records = parsed.get("memories") if isinstance(parsed, dict) else None
        if not isinstance(records, list) or len(records) != len(artifacts):
            raise ValueError("Meta model must return exactly one memory for every source artifact")
        records_by_id: dict[str, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict) or set(record) != {"source_id", "summary", "themes"}:
                raise ValueError("each project memory must include only source_id, summary, and themes")
            source_id = record["source_id"]
            if not isinstance(source_id, str) or source_id not in artifact_by_id or source_id in records_by_id:
                raise ValueError("project memory contains an unknown or duplicate source_id")
            records_by_id[source_id] = record
        if set(records_by_id) != set(artifact_by_id):
            raise ValueError("project memories do not cover every source artifact")

        memories: list[Memory] = []
        for artifact in artifacts:
            record = records_by_id[artifact["id"]]
            memory = Memory.from_dict({
                "id": f"memory-{artifact['id']}",
                "source_id": artifact["id"],
                "date": artifact["date"],
                "modality": artifact["modality"],
                "title": artifact["title"],
                "summary": record["summary"],
                "themes": record["themes"],
            })
            if len(memory.themes) > 3 or any(len(theme) > 40 for theme in memory.themes):
                raise ValueError("project memory tags exceed the allowed count or length")
            memories.append(memory)

        cache[cache_key] = [{
            "id": memory.id,
            "source_id": memory.source_id,
            "date": memory.date,
            "modality": memory.modality,
            "title": memory.title,
            "summary": memory.summary,
            "themes": list(memory.themes),
        } for memory in memories]
        cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return memories

    def usage_summary(self) -> dict[str, int | float]:
        """Return this run's token accounting and the local cumulative estimate."""
        cumulative = self.cumulative_estimated_usd()
        return {
            **self.run_usage,
            "cumulative_estimated_usd": round(cumulative, 6),
            "budget_usd": self.budget_usd,
            "remaining_estimated_usd": round(max(self.budget_usd - cumulative, 0.0), 6),
        }

    def cumulative_estimated_usd(self) -> float:
        cumulative = 0.0
        try:
            for line in self.usage_file.read_text(encoding="utf-8").splitlines():
                cumulative += float(json.loads(line).get("estimated_usd", 0))
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        return cumulative
