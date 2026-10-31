"""Tests for local Meta API key lookup without exposing key material."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from thread_engine.config import model_api_key


class ModelApiKeyTests(unittest.TestCase):
    def test_environment_takes_precedence_over_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            env_file = Path(folder) / ".env"
            env_file.write_text("MODEL_API_KEY=file-value\n", encoding="utf-8")
            with patch.dict(os.environ, {"MODEL_API_KEY": "environment-value"}):
                self.assertEqual(model_api_key(env_file), "environment-value")

    def test_reads_quoted_value_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            env_file = Path(folder) / ".env"
            env_file.write_text('# local secret\nOTHER=value\nMODEL_API_KEY="file-value"\n', encoding="utf-8")
            with patch.dict(os.environ):
                os.environ.pop("MODEL_API_KEY", None)
                self.assertEqual(model_api_key(env_file), "file-value")

    def test_missing_key_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ):
                os.environ.pop("MODEL_API_KEY", None)
                self.assertIsNone(model_api_key(Path(folder) / ".env"))


if __name__ == "__main__":
    unittest.main()
