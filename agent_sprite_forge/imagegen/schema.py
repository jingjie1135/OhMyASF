"""Request and manifest schema helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import RequestValidationError
from .config import RESERVED_PAYLOAD_KEYS


@dataclass(frozen=True)
class ImageGenRequest:
    prompt: str
    version: str = "1"
    task_type: str = "text_to_image"
    asset_role: str | None = None
    map_mode: str | None = None
    quality: str = "standard"
    quality_explicit: bool = False
    negative_prompt: str | None = None
    n: int = 1
    output_name: str = "generated-image"
    model: str | None = None
    model_policy: dict[str, str] = field(default_factory=dict)
    size_mode: str | None = None
    size: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    references: list[dict[str, Any]] = field(default_factory=list)
    extra_body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageGenRequest":
        if not isinstance(data, dict):
            raise RequestValidationError("Request JSON must be an object")
        prompt = str(data.get("prompt", "")).strip()
        if not prompt:
            raise RequestValidationError("Request requires a non-empty prompt")
        try:
            n = int(data.get("n", 1))
        except (TypeError, ValueError) as exc:
            raise RequestValidationError("Request n must be an integer") from exc
        if n < 1:
            raise RequestValidationError("Request n must be at least 1")
        extra_body = data.get("extra_body", {})
        if not isinstance(extra_body, dict):
            raise RequestValidationError("Request extra_body must be an object")
        _validate_extra_body(extra_body)
        references = data.get("references", [])
        if not isinstance(references, list):
            raise RequestValidationError("Request references must be an array")
        model_policy = data.get("model_policy", {})
        if not isinstance(model_policy, dict):
            raise RequestValidationError("Request model_policy must be an object")

        return cls(
            version=str(data.get("version", "1")),
            task_type=str(data.get("task_type", "text_to_image")),
            asset_role=_optional_str(data.get("asset_role")),
            map_mode=_optional_str(data.get("map_mode")),
            quality=str(data.get("quality", "standard")),
            quality_explicit="quality" in data,
            prompt=prompt,
            negative_prompt=_optional_str(data.get("negative_prompt")),
            n=n,
            output_name=str(data.get("output_name", "generated-image")),
            model=_optional_str(data.get("model")),
            model_policy={str(key): str(value) for key, value in model_policy.items()},
            size_mode=_optional_str(data.get("size_mode")),
            size=_optional_str(data.get("size")),
            constraints=dict(data.get("constraints", {})) if isinstance(data.get("constraints", {}), dict) else {},
            references=[dict(item) for item in references if isinstance(item, dict)],
            extra_body=dict(extra_body),
        )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_request(path: str | Path) -> ImageGenRequest:
    request_path = Path(path)
    try:
        data = json.loads(request_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RequestValidationError(f"Could not read request file {request_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RequestValidationError(f"Request file {request_path} is not valid JSON: {exc}") from exc
    return ImageGenRequest.from_dict(data)


def _validate_extra_body(extra_body: dict[str, Any]) -> None:
    reserved = RESERVED_PAYLOAD_KEYS.intersection(extra_body)
    if reserved:
        fields = ", ".join(sorted(reserved))
        raise RequestValidationError(f"Request extra_body cannot override core payload field(s): {fields}")
