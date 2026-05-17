"""Firefly image model catalog and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass


VIDEO_PREFIXES = ("firefly-sora2", "firefly-veo31", "firefly-kling")


@dataclass(frozen=True)
class ModelFamily:
    name: str
    resolutions: tuple[str, ...]
    ratios: tuple[str, ...]


FAMILIES: dict[str, ModelFamily] = {
    "firefly-gpt-image": ModelFamily(
        name="firefly-gpt-image",
        resolutions=("1k", "2k", "4k"),
        ratios=("1x1", "5x4", "9x16", "21x9", "16x9", "3x2", "4x3", "4x5", "3x4", "2x3"),
    ),
    "firefly-nano-banana2": ModelFamily(
        name="firefly-nano-banana2",
        resolutions=("1k", "2k", "4k"),
        ratios=("1x1", "16x9", "9x16", "4x3", "3x4", "1x8", "1x4", "4x1", "8x1"),
    ),
    "firefly-nano-banana-pro": ModelFamily(
        name="firefly-nano-banana-pro",
        resolutions=("1k", "2k", "4k"),
        ratios=("1x1", "16x9", "9x16", "4x3", "3x4"),
    ),
    "firefly-nano-banana": ModelFamily(
        name="firefly-nano-banana",
        resolutions=("1k", "2k", "4k"),
        ratios=("1x1", "16x9", "9x16", "4x3", "3x4"),
    ),
}


def model_id(family: str, resolution: str, ratio: str) -> str:
    return f"{family}-{resolution}-{ratio}"


def supports(family: str, resolution: str, ratio: str) -> bool:
    info = FAMILIES.get(family)
    return bool(info and resolution in info.resolutions and ratio in info.ratios)


def is_video_model_id(value: str) -> bool:
    return value.startswith(VIDEO_PREFIXES)


def parse_model_id(value: str) -> tuple[str, str, str] | None:
    for family in sorted(FAMILIES, key=len, reverse=True):
        prefix = f"{family}-"
        if value.startswith(prefix):
            rest = value[len(prefix) :]
            parts = rest.split("-", 1)
            if len(parts) != 2:
                return None
            resolution, ratio = parts
            return family, resolution, ratio
    return None


def is_valid_model_id(value: str) -> bool:
    parsed = parse_model_id(value)
    if parsed is None:
        return False
    family, resolution, ratio = parsed
    return supports(family, resolution, ratio)
