"""Local configuration helpers shared by Meta model adapters."""

from __future__ import annotations

import os
from pathlib import Path


def model_api_key(env_file: Path | None = None) -> str | None:
    """Read MODEL_API_KEY from the process environment, then the repo's .env."""
    key = os.environ.get("MODEL_API_KEY")
    if key:
        return key
    path = env_file or Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "MODEL_API_KEY":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            return value or None
    return None
