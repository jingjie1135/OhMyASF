"""Command line interface for image generation."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Sequence
from urllib.parse import urlsplit, urlunsplit

from agent_sprite_forge import __version__

from .config import load_config
from .config import ImageGenConfig
from .errors import ImageGenError, RequestValidationError
from .io_utils import ensure_dir, write_json
from .model_resolver import ModelSelection, resolve_model
from .openai_compatible import call_images_generations, endpoint_url, prompt_with_negative, save_generation_response
from .schema import ImageGenRequest, load_request


def main(argv: Sequence[str] | None = None, environ: dict[str, str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    if args.command == "generate":
        return generate(args, env)
    parser.error("unknown command")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-sprite-forge-imagegen")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate_parser = subparsers.add_parser("generate", help="Generate raw images through an OpenAI-compatible endpoint")
    generate_parser.add_argument("--config", required=True, type=Path)
    generate_parser.add_argument("--request", required=True, type=Path)
    generate_parser.add_argument("--output-dir", required=True, type=Path)
    generate_parser.add_argument("--dry-run", action="store_true")
    return parser


def generate(args: argparse.Namespace, environ: dict[str, str]) -> int:
    started = time.perf_counter()
    output_dir = ensure_dir(args.output_dir)
    request_path = args.request
    config: ImageGenConfig | None = None
    request: ImageGenRequest | None = None
    selection: ModelSelection | None = None
    warnings: list[str] = []
    try:
        config = load_config(args.config, environ=environ)
        request = load_request(request_path)
        warnings = _reference_warnings_or_error(request)
        selection = resolve_model(request, config)
        if args.dry_run:
            manifest = _manifest(
                config=config,
                request=request,
                request_path=request_path,
                selection=selection,
                started=started,
                status="succeeded",
                dry_run=True,
                outputs=[],
                warnings=warnings,
            )
            write_json(output_dir / "imagegen-manifest.json", manifest)
            return 0

        api_key = config.api_key(environ)
        response = call_images_generations(config, request, selection.model, selection.sent_size, api_key)
        outputs = save_generation_response(
            response=response,
            output_dir=output_dir,
            output_name=request.output_name,
            timeout_seconds=config.timeout_seconds,
        )
        manifest = _manifest(
            config=config,
            request=request,
            request_path=request_path,
            selection=selection,
            started=started,
            status="succeeded",
            dry_run=False,
            outputs=outputs,
            warnings=warnings,
            response_summary=_response_summary(response),
        )
        write_json(output_dir / "imagegen-manifest.json", manifest)
        return 0
    except ImageGenError as exc:
        manifest = _failure_manifest(
            config_path=args.config,
            request_path=request_path,
            started=started,
            exc=exc,
            dry_run=bool(args.dry_run),
            config=config,
            request=request,
            selection=selection,
            warnings=warnings,
        )
        write_json(output_dir / "imagegen-manifest.json", manifest)
        return 1


def _manifest(
    config: object,
    request: ImageGenRequest,
    request_path: Path,
    selection: ModelSelection,
    started: float,
    status: str,
    dry_run: bool,
    outputs: list[dict[str, object]],
    warnings: list[str],
    response_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    safe_base_url = _redact_url_credentials(str(getattr(config, "base_url")))
    return {
        "adapter_version": __version__,
        "provider": getattr(config, "provider"),
        "base_url": safe_base_url,
        "endpoint_path": endpoint_url(safe_base_url),
        "status": status,
        "dry_run": dry_run,
        "request_path": str(request_path),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "selected_model": selection.model,
        "model_selection": {
            "source": selection.source,
            "reason": selection.reason,
            "family": selection.family,
            "resolution": selection.resolution,
            "ratio": selection.ratio,
        },
        "size_mode": selection.size_mode,
        "sent_size": selection.sent_size,
        "prompt_used": prompt_with_negative(request),
        "negative_prompt": request.negative_prompt,
        "outputs": outputs,
        "warnings": warnings,
        "response_summary": response_summary or {},
    }


def _failure_manifest(
    config_path: Path,
    request_path: Path,
    started: float,
    exc: ImageGenError,
    dry_run: bool,
    config: ImageGenConfig | None,
    request: ImageGenRequest | None,
    selection: ModelSelection | None,
    warnings: list[str],
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "adapter_version": __version__,
        "provider": "openai_compatible",
        "status": "failed",
        "dry_run": dry_run,
        "config_path": str(config_path),
        "request_path": str(request_path),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "outputs": [],
        "warnings": warnings,
        "error": {"type": exc.__class__.__name__, "message": str(exc)},
    }
    if config is not None:
        safe_base_url = _redact_url_credentials(config.base_url)
        manifest["base_url"] = safe_base_url
        manifest["endpoint_path"] = endpoint_url(safe_base_url)
    if selection is not None:
        manifest["selected_model"] = selection.model
        manifest["model_selection"] = {
            "source": selection.source,
            "reason": selection.reason,
            "family": selection.family,
            "resolution": selection.resolution,
            "ratio": selection.ratio,
        }
        manifest["size_mode"] = selection.size_mode
        manifest["sent_size"] = selection.sent_size
    if request is not None:
        manifest["prompt_used"] = prompt_with_negative(request)
        manifest["negative_prompt"] = request.negative_prompt
    return manifest


def _response_summary(response: dict[str, object]) -> dict[str, object]:
    data = response.get("data")
    return {
        "created": response.get("created"),
        "image_count": len(data) if isinstance(data, list) else 0,
        "usage": response.get("usage"),
    }


def _redact_url_credentials(value: str) -> str:
    parts = urlsplit(value)
    if not parts.username and not parts.password:
        return value
    host = parts.hostname or ""
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def _reference_warnings_or_error(request: ImageGenRequest) -> list[str]:
    if not request.references:
        return []
    required = [item for item in request.references if bool(item.get("required"))]
    if required:
        raise RequestValidationError(
            "references[] contains required image references, but this adapter path is text-to-image only"
        )
    return [
        "references[] were recorded for planning but not sent; this adapter path is text-to-image only"
    ]


if __name__ == "__main__":
    raise SystemExit(main())
