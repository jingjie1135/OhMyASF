"""Adapter-specific exceptions."""

from __future__ import annotations


class ImageGenError(Exception):
    """Base class for user-facing image generation errors."""


class ConfigError(ImageGenError):
    """Raised when configuration is missing or invalid."""


class RequestValidationError(ImageGenError):
    """Raised when an image generation request is invalid."""


class ModelResolutionError(ImageGenError):
    """Raised when a model cannot be resolved safely."""


class ProviderError(ImageGenError):
    """Raised when an OpenAI-compatible provider call fails."""
