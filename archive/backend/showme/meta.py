"""Explicit, auditable Muse Spark video calls for the SHOWME experiment."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import base64

from .process import PROCESS_SCHEMA

MODEL = "muse-spark-1.3"
PROMPT_VERSION = "showme-video-analysis-v4"


class MuseSparkClient:
    def __init__(self, api_key: str, model: str = MODEL) -> None:
        try:
            from openai import APIError, OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the optional Meta client with: pip install -e '.[meta]'") from exc
        self.client = OpenAI(api_key=api_key, base_url="https://api.meta.ai/v1", max_retries=0)
        self._api_error = APIError
        self.model = model

    @classmethod
    def from_env(cls) -> "MuseSparkClient":
        api_key = os.environ.get("MODEL_API_KEY") or _read_repo_key()
        if not api_key:
            raise ValueError("Set MODEL_API_KEY in the local .env file or environment")
        return cls(api_key=api_key, model=os.environ.get("SHOWME_META_MODEL", MODEL))

    def learn(
        self,
        video: Path,
        *,
        duration_seconds: float,
        narration: str = "",
        reference_pdf: Path | None = None,
    ) -> dict[str, Any]:
        """Infer a candidate process, optionally grounded in a reference PDF."""
        prompt = _learning_prompt(duration_seconds, narration, has_reference=reference_pdf is not None)
        return self.analyze_video(
            video,
            prompt=prompt,
            schema=PROCESS_SCHEMA,
            schema_name="showme_process_model",
            max_output_tokens=6000 if reference_pdf is not None else 3000,
            reference_pdf=reference_pdf,
        )

    def analyze_video(
        self,
        video: Path,
        *,
        prompt: str,
        schema: dict[str, Any],
        schema_name: str,
        max_output_tokens: int = 3000,
        reference_pdf: Path | None = None,
    ) -> dict[str, Any]:
        """Upload the video and optional PDF, request strict JSON, then clean up."""
        video = video.expanduser().resolve()
        if not video.is_file():
            raise ValueError(f"video file does not exist: {video}")
        if reference_pdf is not None:
            reference_pdf = reference_pdf.expanduser().resolve()
            if not reference_pdf.is_file():
                raise ValueError(f"reference PDF does not exist: {reference_pdf}")
        uploaded = []
        try:
            for source in (video, reference_pdf):
                if source is None:
                    continue
                with source.open("rb") as media:
                    uploaded.append(self.client.files.create(
                        purpose="user_data",
                        file=media,
                        expires_after={"anchor": "created_at", "seconds": 3600},
                    ))
            content = [
                {"type": "input_text", "text": prompt},
                {"type": "input_file", "file_id": uploaded[0].id},
            ]
            if reference_pdf is not None:
                content.append({"type": "input_file", "file_id": uploaded[1].id})
            return self._structured_response(
                content,
                schema=schema,
                schema_name=schema_name,
                max_output_tokens=max_output_tokens,
                remote_file_id=uploaded[0].id,
                reference_filename=reference_pdf.name if reference_pdf else None,
            )
        except self._api_error as exc:
            raise RuntimeError(
                "Meta Model API request failed. Automatic retries are disabled to avoid "
                "repeating a potentially billable request; inspect billing before retrying."
            ) from exc
        finally:
            for file in uploaded:
                try:
                    self.client.files.delete(file.id)
                except Exception:
                    # The one-hour expiry is the fallback if remote cleanup fails.
                    pass

    def analyze_image(
        self,
        image: Path,
        *,
        prompt: str,
        schema: dict[str, Any],
        schema_name: str,
        max_output_tokens: int = 1200,
    ) -> dict[str, Any]:
        """Analyze one local image as a data URL; no image file is uploaded or retained."""
        image = image.expanduser().resolve()
        if not image.is_file():
            raise ValueError(f"image file does not exist: {image}")
        encoded = base64.b64encode(image.read_bytes()).decode("ascii")
        data_url = f"data:image/jpeg;base64,{encoded}"
        try:
            return self._structured_response(
                [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url, "detail": "high"},
                ],
                schema=schema,
                schema_name=schema_name,
                max_output_tokens=max_output_tokens,
            )
        except self._api_error as exc:
            raise RuntimeError(
                "Meta Model API request failed. Automatic retries are disabled to avoid "
                "repeating a potentially billable request; inspect billing before retrying."
            ) from exc

    def analyze_images(self, images: list[Path], *, prompt: str, schema: dict[str, Any],
                       schema_name: str, max_output_tokens: int = 2400) -> dict[str, Any]:
        """Send explicitly ordered evidence images in one structured request; no retries."""
        if not 2 <= len(images) <= 6:
            raise ValueError("select between two and six evidence images")
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        for index, source in enumerate(images):
            path = source.expanduser().resolve()
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png"} or not path.is_file():
                raise ValueError("evidence image must be a local JPEG or PNG")
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            content.extend([{"type": "input_text", "text": f"Evidence image {index}"},
                            {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}", "detail": "high"}])
        try:
            return self._structured_response(content, schema=schema, schema_name=schema_name,
                                             max_output_tokens=max_output_tokens)
        except self._api_error as exc:
            raise RuntimeError("Meta image comparison failed; automatic retries are disabled.") from exc

    def _structured_response(
        self,
        content: list[dict[str, Any]],
        *,
        schema: dict[str, Any],
        schema_name: str,
        max_output_tokens: int,
        remote_file_id: str | None = None,
        reference_filename: str | None = None,
    ) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "minimal"},
            max_output_tokens=max_output_tokens,
            text={"format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }},
            input=[{"type": "message", "role": "user", "content": content}],
        )
        if getattr(response, "status", None) not in (None, "completed"):
            raise ValueError(f"Muse Spark response did not complete (status={response.status})")
        if getattr(response, "incomplete_details", None):
            raise ValueError("Muse Spark returned an incomplete response")
        output_text = response.output_text
        if not output_text:
            raise ValueError("Muse Spark returned no structured output")
        try:
            result = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Muse Spark returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise ValueError("Muse Spark output must be a JSON object")
        result["_run"] = {
            "model": self.model,
            "prompt_version": PROMPT_VERSION,
            "remote_file_id": remote_file_id,
            "reference_filename": reference_filename,
            "api_response_id": getattr(response, "id", None),
            "usage": _usage(response),
        }
        return result


def _learning_prompt(duration_seconds: float, narration: str = "", *, has_reference: bool = False) -> str:
    narration_section = (
        f"\n\nExpert narration (use as additional evidence, but distinguish spoken claims from visible facts):\n{narration.strip()}"
        if narration.strip()
        else ""
    )
    reference_section = (
        "An attached PDF is the task's reference instructions. Treat explicit visual/text instructions in that PDF "
        "as the source for intended steps and constraints; treat the video only as evidence of what this person "
        "actually did. Do not promote an action from the video to a requirement unless the PDF supports it. "
        "If the PDF and video differ, preserve the PDF target and describe the video difference as an observed "
        "deviation or uncertainty. Model up to 18 distinct steps when the reference contains them. For each "
        "transition, include timestamped video evidence when the action is visible and page/step reference_evidence "
        "when supported by the PDF; a transition may rely on either source. Cite page and step details when legible. "
    ) if has_reference else ""
    source_instruction = (
        "Without an attached reference document, this single clip is one observed trace, not proof of which steps are necessary. "
        "Identify actions and states only when supported by visible video evidence. Keep the model to at most 8 states and 7 transitions. "
        "Each transition must cite timestamped video evidence. Set reference_evidence to an empty array. "
    ) if not has_reference else (
        "Build the intended sequence from the PDF, including steps not shown in the video. Set video evidence to an empty array "
        "for a transition not visible in the clip, and cite its PDF page and step in reference_evidence. Use up to 20 states "
        "and 18 transitions when needed to represent the reference procedure. "
    )
    return f"""Learn a candidate process from this demonstration video. Do not assume a task or inject an expected mistake. {reference_section}{source_instruction}Give each transition a stable unique ID. Every state/action claim must be grounded in the source allowed above. Use observable_facts and postconditions to describe visible attachment points, relative placement, and facing relationships when the video or explicit reference supports them. Describe orientation relative to the assembly or another component, not screen coordinates. Keep repeated parts distinguishable when merging them would erase a task-relevant placement or orientation difference; disclose when identity cannot be maintained. Avoid making a generic statement such as assembly complete the only final-state fact. If a relationship is not visible or legible, record it as uncertain instead of inventing it. Distinguish observed video facts from intended reference instructions. Record ordering_observations only for pairs whose order is visibly supported in the video, with timestamp evidence. These observations mean only “happened before in this clip”; they are not prerequisites. Do not infer dependencies or required order from the demonstration. If a potential constraint is useful to preserve, put it in candidate_constraints as an unverified hypothesis and disclose uncertainty. Do not claim hidden conditions. If the procedure or an object is ambiguous, put that uncertainty in uncertainties. Return the requested JSON schema.{narration_section}"""


def _usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
    }


def _read_repo_key() -> str | None:
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / ".env"
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("MODEL_API_KEY="):
            value = line.split("=", 1)[1].strip().strip("'\"")
            return value or None
    return None
