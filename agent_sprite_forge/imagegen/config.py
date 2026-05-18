"""Configuration loading for the image generation adapter."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .errors import ConfigError


ENV_BASE_URL = "AGENT_SPRITE_FORGE_IMAGEGEN_BASE_URL"
ENV_API_KEY_ENV = "AGENT_SPRITE_FORGE_IMAGEGEN_API_KEY_ENV"
ENV_SIZE_MODE = "AGENT_SPRITE_FORGE_IMAGEGEN_SIZE_MODE"
DEFAULT_API_KEY_ENV = "OHMYASF_IMAGEGEN_API_KEY"
DEFAULT_CONFIG_DIR = ".agent-sprite-forge"
DEFAULT_CONFIG_FILENAME = "imagegen.json"
RESERVED_PAYLOAD_KEYS = {"model", "prompt", "n", "size", "response_format"}


@dataclass(frozen=True)
class ImageGenConfig:
    base_url: str
    api_key_env: str = DEFAULT_API_KEY_ENV
    api_key_value: str | None = None
    provider: str = "openai_compatible"
    default_family: str = "firefly-gpt-image"
    default_resolution: str = "2k"
    default_ratio: str = "1x1"
    size_mode: str = "model_id"
    response_format: str = "b64_json"
    timeout_seconds: int = 120
    routing: dict[str, dict[str, str]] = field(default_factory=dict)
    extra_body: dict[str, object] = field(default_factory=dict)

    def api_key(self, environ: Mapping[str, str] | None = None) -> str:
        env = os.environ if environ is None else environ
        value = env.get(self.api_key_env, "")
        if not value and self.api_key_value:
            value = self.api_key_value
        if not value:
            raise ConfigError(f"Missing API key in environment variable {self.api_key_env!r}")
        return value


def _load_json(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except OSError as exc:
        raise ConfigError(f"Could not read config file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("Config JSON must be an object")
    return data


def default_config_path(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    home = env.get("USERPROFILE") or env.get("HOME")
    if home:
        return Path(home) / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILENAME
    return Path.home() / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILENAME


def load_config(path: str | Path | None, environ: Mapping[str, str] | None = None) -> ImageGenConfig:
    env = os.environ if environ is None else environ
    config_path = default_config_path(env) if path is None else Path(path)
    if path is None and not config_path.exists():
        raise ConfigError(f"Default imagegen config not found at {config_path}. Run `ohmyasf setup` first.")
    data = _load_json(config_path)

    if ENV_BASE_URL in env:
        data["base_url"] = env[ENV_BASE_URL]
    if ENV_API_KEY_ENV in env:
        data["api_key_env"] = env[ENV_API_KEY_ENV]
    if ENV_SIZE_MODE in env:
        data["size_mode"] = env[ENV_SIZE_MODE]

    base_url = str(data.get("base_url", "")).strip()
    if not base_url:
        raise ConfigError("Config requires a non-empty base_url")

    routing = data.get("routing", {})
    if not isinstance(routing, dict):
        raise ConfigError("Config field routing must be an object")

    extra_body = data.get("extra_body", {})
    if not isinstance(extra_body, dict):
        raise ConfigError("Config field extra_body must be an object")
    _validate_extra_body(extra_body, "Config")
    try:
        timeout_seconds = int(data.get("timeout_seconds", 120))
    except (TypeError, ValueError) as exc:
        raise ConfigError("Config field timeout_seconds must be an integer") from exc
    if timeout_seconds < 1:
        raise ConfigError("Config field timeout_seconds must be at least 1")

    return ImageGenConfig(
        base_url=base_url,
        api_key_env=str(data.get("api_key_env", DEFAULT_API_KEY_ENV)),
        api_key_value=str(data["api_key"]) if data.get("api_key") else None,
        provider=str(data.get("provider", "openai_compatible")),
        default_family=str(data.get("default_family", "firefly-gpt-image")),
        default_resolution=str(data.get("default_resolution", "2k")),
        default_ratio=str(data.get("default_ratio", "1x1")),
        size_mode=str(data.get("size_mode", "model_id")),
        response_format=str(data.get("response_format", "b64_json")),
        timeout_seconds=timeout_seconds,
        routing={str(key): dict(value) for key, value in routing.items() if isinstance(value, dict)},
        extra_body=dict(extra_body),
    )


def _validate_extra_body(extra_body: Mapping[str, object], label: str) -> None:
    reserved = RESERVED_PAYLOAD_KEYS.intersection(extra_body)
    if reserved:
        fields = ", ".join(sorted(reserved))
        raise ConfigError(f"{label} extra_body cannot override core payload field(s): {fields}")
