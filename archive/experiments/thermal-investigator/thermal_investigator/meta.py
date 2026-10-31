"""Bounded Meta Responses transport with persistent reservations and no retries.

Uses the same endpoint/structured-output shape as the existing backend adapter.
Only generated public simulation context is accepted by the calling pilot.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .decisions import decision_schema, instructions, validate_decision

MODEL = "muse-spark-1.3"
MAX_OUTPUT_TOKENS = 2048
MAX_REQUEST_BYTES = 80000
INPUT_PER_M = 1.25
OUTPUT_PER_M = 4.25
CACHED_PER_M = .15
PRICE_SOURCE = "https://dev.meta.ai/docs/pricing-rate-limits"


def load_api_key(env_file: Path | None = None) -> str:
    # Same credential convention as backend/thread_engine/config.py. Never log values.
    if os.environ.get("MODEL_API_KEY"):
        return os.environ["MODEL_API_KEY"]
    if env_file and env_file.is_file():
        for line in env_file.read_text().splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            if key.strip() == "MODEL_API_KEY":
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                if value:
                    return value
    raise ValueError("MODEL_API_KEY is unavailable")


class MetaDecider:
    def __init__(self, api_key: str, directory: Path, *, max_calls=6, budget_usd=1.0, transport=None):
        if not api_key or not 1 <= max_calls <= 12 or not 0 < budget_usd <= 5:
            raise ValueError("Invalid credentials or bounded pilot limits")
        self._api_key = api_key
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_calls = max_calls
        self.budget_usd = budget_usd
        self._transport = transport or self._send
        self.state_path = directory / "usage-state.json"

    @contextmanager
    def _locked(self):
        with (self.directory / "usage.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _state(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {"attempts": 0, "charged_or_reserved_usd": 0., "input_tokens": 0, "output_tokens": 0}

    def _send(self, payload):
        request = Request("https://api.meta.ai/v1/responses", data=payload, method="POST",
                          headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._api_key})
        with urlopen(request, timeout=45) as response:
            return json.load(response)

    def decide(self, context, strategy):
        return self.decide_contract(context, instructions(strategy), decision_schema(context),
                                    lambda value: validate_decision(value, context))

    def decide_contract(self, context, instruction, schema, validator):
        """Reuse the guarded transport for a separately validated bounded contract."""
        payload = {"model": MODEL, "reasoning": {"effort": "minimal"},
                   "max_output_tokens": MAX_OUTPUT_TOKENS,
                   "input": instruction + "\n\n" + json.dumps(context, separators=(",", ":")),
                   "text": {"format": {"type": "json_schema", "name": "thermal_investigation_decision",
                                       "strict": True, "schema": schema}}}
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        if len(encoded) > MAX_REQUEST_BYTES:
            raise ValueError("Public decision context exceeds the pilot input limit")
        fingerprint = hashlib.sha256(encoded).hexdigest()
        response_path = self.directory / (fingerprint + ".json")
        # Conservative byte-based input reservation plus formatting allowance. This is
        # a local guard, not a provider-enforced spending limit or tokenizer guarantee.
        reserved = ((len(encoded) + 2048) * INPUT_PER_M + MAX_OUTPUT_TOKENS * OUTPUT_PER_M) / 1e6
        with self._locked():
            if response_path.exists():
                cached = json.loads(response_path.read_text())
                if cached["status"] != "completed":
                    raise ValueError("An attempt with this context already exists; no automatic repeat")
                return validator(cached["decision"]), {**cached["usage"], "cache_hit": True}
            state = self._state()
            if state["attempts"] >= self.max_calls or state["charged_or_reserved_usd"] + reserved > self.budget_usd:
                raise ValueError("Persistent pilot call/cost guard exhausted")
            state["attempts"] += 1
            state["charged_or_reserved_usd"] += reserved
            self.state_path.write_text(json.dumps(state))
            response_path.write_text(json.dumps({"status": "attempt_reserved", "reserved_usd": reserved}))
        raw = None
        try:
            raw = self._transport(encoded)
            raw_path = self.directory / (fingerprint + ".response.json")
            raw_path.write_text(json.dumps(raw, indent=2, allow_nan=False))
            usage = raw.get("usage") or {}
            tokens_in = usage.get("input_tokens")
            tokens_out = usage.get("output_tokens")
            accounted = type(tokens_in) is int and type(tokens_out) is int and tokens_in >= 0 and tokens_out >= 0
            details = usage.get("input_tokens_details") or {}
            cached_tokens = min(tokens_in, max(0, int(details.get("cached_tokens", 0)))) if accounted else 0
            estimated = ((tokens_in - cached_tokens) * INPUT_PER_M + cached_tokens * CACHED_PER_M + tokens_out * OUTPUT_PER_M) / 1e6 if accounted else reserved
            report = {"model": MODEL, "input_tokens": tokens_in, "output_tokens": tokens_out,
                      "cached_input_tokens": cached_tokens, "estimated_usd": estimated,
                      "usage_reported": accounted, "cache_hit": False, "price_source": PRICE_SOURCE}
            with self._locked():
                state = self._state()
                state["charged_or_reserved_usd"] += estimated - reserved
                state["input_tokens"] += tokens_in if accounted else 0
                state["output_tokens"] += tokens_out if accounted else 0
                self.state_path.write_text(json.dumps(state))
            texts = [part.get("text", "") for item in raw.get("output", []) if item.get("type") == "message"
                     for part in item.get("content", []) if part.get("type") == "output_text"]
            if raw.get("status") != "completed" or not texts:
                raise ValueError("Meta response incomplete or empty; attempt retained without retries")
            decision = validator(json.loads("".join(texts)))
            response_path.write_text(json.dumps({"status": "completed", "context_sha256": fingerprint,
                "decision": decision, "usage": report, "utc": datetime.now(timezone.utc).isoformat()}, indent=2))
            return decision, report
        except (HTTPError, URLError, TimeoutError, ValueError, TypeError, KeyError) as exc:
            # Do not expose credentials, headers or provider request bodies in exceptions.
            error = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__
            response_path.write_text(json.dumps({"status": "failed_no_retry", "error_type": error,
                                                 "response_saved": raw is not None}))
            raise ValueError("Meta attempt failed (" + error + "); saved without retry") from None
