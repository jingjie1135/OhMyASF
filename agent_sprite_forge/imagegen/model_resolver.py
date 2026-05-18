"""Model selection rules for Firefly image models."""

from __future__ import annotations

from dataclasses import dataclass

from .config import ImageGenConfig
from .errors import ModelResolutionError
from .model_catalog import is_valid_model_id, is_video_model_id, model_id, parse_model_id, supports
from .schema import ImageGenRequest


QUALITY_PROFILES: dict[str, tuple[str, str]] = {
    "draft": ("firefly-nano-banana2", "1k"),
    "standard": ("firefly-gpt-image", "2k"),
    "high": ("firefly-gpt-image", "2k"),
    "final": ("firefly-gpt-image", "4k"),
}

SIMPLE_SMALL_ROLES = {
    "item_icon",
    "ui_icon",
    "portrait",
    "headshot",
    "simple_projectile",
    "simple_impact",
    "simple_fx",
    "tiny_prop",
}

LARGE_WIDESCREEN_ROLES = {
    "map_base",
    "dressed_reference",
    "tileset",
    "side_scroll_layer",
    "parallax_layer",
}

DERIVED_SIZES: dict[tuple[str, str], str] = {
    ("1k", "1x1"): "1024x1024",
    ("2k", "1x1"): "2048x2048",
    ("4k", "1x1"): "4096x4096",
    ("1k", "16x9"): "1024x576",
    ("2k", "16x9"): "2048x1152",
    ("4k", "16x9"): "4096x2304",
    ("1k", "9x16"): "576x1024",
    ("2k", "9x16"): "1152x2048",
    ("4k", "9x16"): "2304x4096",
    ("1k", "4x3"): "1024x768",
    ("2k", "4x3"): "2048x1536",
    ("4k", "4x3"): "4096x3072",
    ("1k", "3x4"): "768x1024",
    ("2k", "3x4"): "1536x2048",
    ("4k", "3x4"): "3072x4096",
    ("1k", "4x1"): "1024x256",
    ("2k", "4x1"): "2048x512",
    ("1k", "8x1"): "1024x128",
    ("2k", "8x1"): "2048x256",
}


@dataclass(frozen=True)
class ModelSelection:
    model: str
    family: str
    resolution: str
    ratio: str
    source: str
    reason: str
    size_mode: str
    sent_size: str | None


def resolve_model(request: ImageGenRequest, config: ImageGenConfig) -> ModelSelection:
    if request.model:
        return _explicit_selection(request, config)

    family, resolution, ratio, reason = _route(request, config)
    if not supports(family, resolution, ratio):
        family, resolution, ratio, reason = _fallback(family, resolution, ratio, reason)
    candidate = model_id(family, resolution, ratio)
    if not is_valid_model_id(candidate):
        raise ModelResolutionError(f"Resolved model {candidate!r} is not in the configured image catalog")
    size_mode = request.size_mode or config.size_mode
    return ModelSelection(
        model=candidate,
        family=family,
        resolution=resolution,
        ratio=ratio,
        source="routing",
        reason=reason,
        size_mode=size_mode,
        sent_size=_sent_size(size_mode, request.size, resolution, ratio),
    )


def _explicit_selection(request: ImageGenRequest, config: ImageGenConfig) -> ModelSelection:
    assert request.model is not None
    if is_video_model_id(request.model):
        raise ModelResolutionError(f"Video model {request.model!r} cannot be used for image generation")
    if not is_valid_model_id(request.model):
        raise ModelResolutionError(f"Explicit model {request.model!r} is not a supported Firefly image model")
    parsed = parse_model_id(request.model)
    if parsed is None:
        raise ModelResolutionError(f"Could not parse explicit model {request.model!r}")
    family, resolution, ratio = parsed
    size_mode = request.size_mode or config.size_mode
    return ModelSelection(
        model=request.model,
        family=family,
        resolution=resolution,
        ratio=ratio,
        source="explicit",
        reason="explicit model override",
        size_mode=size_mode,
        sent_size=_sent_size(size_mode, request.size, resolution, ratio),
    )


def _route(request: ImageGenRequest, config: ImageGenConfig) -> tuple[str, str, str, str]:
    role = (request.asset_role or "").lower()
    map_mode = (request.map_mode or "").lower()
    quality = request.quality.lower()
    family, resolution = QUALITY_PROFILES.get(quality, (config.default_family, config.default_resolution))
    ratio = config.default_ratio
    quality_overrides_resolution = request.quality_explicit and quality != "standard" and quality in QUALITY_PROFILES

    if quality_overrides_resolution:
        return family, resolution, _policy_ratio(role, map_mode, ratio), f"explicit quality={quality} override"

    if role in config.routing:
        override = config.routing[role]
        return (
            override.get("family", family),
            override.get("resolution", resolution),
            override.get("ratio", ratio),
            f"routing override for asset_role={role}",
        )

    if _is_dense_grid(request):
        return "firefly-gpt-image", "4k", "1x1", "dense 5x5/6x6 grid requires 4K sheet detail"
    if role in SIMPLE_SMALL_ROLES:
        return "firefly-gpt-image", "1k", "1x1", f"simple small asset_role={role} uses 1K"
    if role in {"player_sheet", "hero_sheet", "boss_sheet"}:
        return "firefly-gpt-image", "2k", "1x1", f"{role} requires dense square sheet detail"
    if role in {"prop_pack", "compact_prop_pack"}:
        return "firefly-gpt-image", "2k", "1x1", "compact prop packs use square grids"
    if role in {"platform_strip", "wide_strip", "bridge", "long_hazard"}:
        return "firefly-nano-banana2", "1k", "4x1", "wide strips need a family with 4x1/8x1 support"
    if role in LARGE_WIDESCREEN_ROLES or map_mode == "side_scroll_mode":
        return "firefly-gpt-image", "4k", "16x9", "large map/stage assets use a 4K widescreen canvas"
    if role in {"mobile_background", "portrait_map"} or map_mode in {"mobile_portrait", "portrait"}:
        return "firefly-gpt-image", "2k", "9x16", "portrait gameplay scenes use 9x16"
    if role in {"tall_map", "route_map"} or map_mode == "tall_route":
        return "firefly-gpt-image", "2k", "3x4", "tall route maps use 3x4"

    return family, resolution, ratio, "default square image routing"


def _policy_ratio(role: str, map_mode: str, default_ratio: str) -> str:
    if role in LARGE_WIDESCREEN_ROLES or map_mode == "side_scroll_mode":
        return "16x9"
    if role in {"mobile_background", "portrait_map"} or map_mode in {"mobile_portrait", "portrait"}:
        return "9x16"
    if role in {"tall_map", "route_map"} or map_mode == "tall_route":
        return "3x4"
    if role in {"platform_strip", "wide_strip", "bridge", "long_hazard"}:
        return "4x1"
    return default_ratio


def _is_dense_grid(request: ImageGenRequest) -> bool:
    rows = _int_hint(request, "grid_rows")
    cols = _int_hint(request, "grid_cols")
    if rows is None or cols is None:
        return False
    return rows >= 5 and cols >= 5


def _int_hint(request: ImageGenRequest, key: str) -> int | None:
    for source in (request.model_policy, request.constraints):
        value = source.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _fallback(family: str, resolution: str, ratio: str, reason: str) -> tuple[str, str, str, str]:
    if ratio in {"4x1", "8x1", "1x4", "1x8"}:
        return "firefly-nano-banana2", resolution, ratio, f"{reason}; fallback to nano-banana2 for wide ratio support"
    if supports(family, resolution, "1x1"):
        return family, resolution, "1x1", f"{reason}; fallback to square ratio"
    raise ModelResolutionError(f"No fallback model supports {family=} {resolution=} {ratio=}")


def _sent_size(size_mode: str, request_size: str | None, resolution: str, ratio: str) -> str | None:
    if size_mode == "model_id":
        return None
    if size_mode == "explicit":
        if not request_size:
            raise ModelResolutionError("size_mode=explicit requires request size")
        return request_size
    if size_mode == "derived":
        try:
            return DERIVED_SIZES[(resolution, ratio)]
        except KeyError as exc:
            raise ModelResolutionError(f"Cannot derive size for {resolution}-{ratio}") from exc
    if size_mode == "auto":
        return request_size
    raise ModelResolutionError(f"Unsupported size_mode {size_mode!r}")
