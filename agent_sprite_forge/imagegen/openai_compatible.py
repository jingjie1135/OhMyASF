"""OpenAI-compatible /images/generations client."""

from __future__ import annotations

import base64
import ipaddress
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from PIL import UnidentifiedImageError

from .config import ImageGenConfig
from .errors import ProviderError
from .io_utils import ensure_dir, image_dimensions, sha256_bytes, write_json
from .schema import ImageGenRequest


UrlOpen = Callable[..., Any]
Resolver = Callable[..., list[tuple[object, ...]]]
DEFAULT_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        return None


def _urlopen_no_redirect(request: object, timeout: int) -> object:
    opener = urllib.request.build_opener(_NoRedirectHandler)
    return opener.open(request, timeout=timeout)


def endpoint_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/images/generations"


def prompt_with_negative(request: ImageGenRequest) -> str:
    if not request.negative_prompt:
        return request.prompt
    return f"{request.prompt}\n\nAvoid: {request.negative_prompt}"


def build_generation_payload(
    request: ImageGenRequest,
    model: str,
    sent_size: str | None,
    response_format: str,
    extra_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt_with_negative(request),
        "n": request.n,
        "response_format": response_format,
    }
    if sent_size is not None:
        payload["size"] = sent_size
    if extra_body:
        payload.update(extra_body)
    payload.update(request.extra_body)
    return payload


def call_images_generations(
    config: ImageGenConfig,
    request: ImageGenRequest,
    model: str,
    sent_size: str | None,
    api_key: str,
    urlopen_func: UrlOpen = urllib.request.urlopen,
) -> dict[str, Any]:
    payload = build_generation_payload(request, model, sent_size, config.response_format, config.extra_body)
    body = json.dumps(payload).encode("utf-8")
    http_request = urllib.request.Request(
        endpoint_url(config.base_url),
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen_func(http_request, timeout=config.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(_extract_error_message(error_body, f"HTTP {exc.code}")) from exc
    except urllib.error.URLError as exc:
        raise ProviderError(redact_message(f"Provider request failed: {exc.reason}")) from exc
    except TimeoutError as exc:
        raise ProviderError("Provider request timed out") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise ProviderError("Provider response JSON must be an object")
    if "error" in data:
        raise ProviderError(redact_message(_error_object_message(data["error"])))
    return data


def save_generation_response(
    response: dict[str, Any],
    output_dir: Path,
    output_name: str,
    urlopen_func: UrlOpen = _urlopen_no_redirect,
    timeout_seconds: int = 120,
    resolver_func: Resolver = socket.getaddrinfo,
    max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
) -> list[dict[str, Any]]:
    ensure_dir(output_dir)
    data = response.get("data")
    if not isinstance(data, list) or not data:
        raise ProviderError("Provider response did not include data[] images")
    outputs: list[dict[str, Any]] = []
    multiple = len(data) > 1
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ProviderError("Provider response data[] entries must be objects")
        image_bytes, source_url = _image_bytes(item, urlopen_func, timeout_seconds, resolver_func, max_download_bytes)
        safe_output_name = sanitize_output_name(output_name)
        filename = f"{safe_output_name}-{index}.png" if multiple else f"{safe_output_name}.png"
        image_path = output_dir / filename
        image_path.write_bytes(image_bytes)
        metadata_path = image_path.with_suffix(".json")
        write_json(
            metadata_path,
            {
                "revised_prompt": item.get("revised_prompt"),
                "source_url": redact_url(source_url) if source_url else None,
            },
        )
        outputs.append(
            {
                "path": str(image_path),
                "role": "raw",
                "dimensions": _read_image_dimensions(image_path),
                "sha256": sha256_bytes(image_bytes),
                "metadata_path": str(metadata_path),
            }
        )
    return outputs


def _image_bytes(
    item: dict[str, Any],
    urlopen_func: UrlOpen,
    timeout_seconds: int,
    resolver_func: Resolver,
    max_download_bytes: int,
) -> tuple[bytes, str | None]:
    b64_json = item.get("b64_json")
    if isinstance(b64_json, str) and b64_json:
        try:
            return base64.b64decode(b64_json), None
        except ValueError as exc:
            raise ProviderError("Provider b64_json image was not valid base64") from exc
    url = item.get("url")
    if isinstance(url, str) and url:
        _validate_download_url(url, resolver_func)
        try:
            with urlopen_func(url, timeout=timeout_seconds) as response:
                final_url = response.geturl() if hasattr(response, "geturl") else url
                _validate_download_url(final_url, resolver_func)
                data = response.read(max_download_bytes + 1)
                if len(data) > max_download_bytes:
                    raise ProviderError("Provider image download was too large")
                return data, final_url
        except urllib.error.URLError as exc:
            raise ProviderError(redact_message(f"Provider image download failed: {exc.reason}")) from exc
        except TimeoutError as exc:
            raise ProviderError("Provider image download timed out") from exc
    raise ProviderError("Provider image entry had neither b64_json nor url")


def _validate_download_url(url: str, resolver_func: Resolver) -> None:
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise ProviderError("Only HTTPS image response URLs are allowed")
    if parts.username or parts.password:
        raise ProviderError("Image response URLs must not contain credentials")
    if not parts.hostname:
        raise ProviderError("Image response URL must include a hostname")
    host = parts.hostname
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        port = parts.port or 443
        try:
            resolved = resolver_func(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ProviderError(f"Could not resolve image response URL host: {host}") from exc
        addresses = []
        for item in resolved:
            sockaddr = item[4]
            if isinstance(sockaddr, tuple) and sockaddr:
                addresses.append(ipaddress.ip_address(str(sockaddr[0])))
    if not addresses:
        raise ProviderError(f"Could not resolve image response URL host: {host}")
    for address in addresses:
        if _is_blocked_address(address):
            raise ProviderError("Image response URL resolves to a blocked network address")


def _is_blocked_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def sanitize_output_name(value: str) -> str:
    name = Path(value).name
    stem = Path(name).stem if Path(name).suffix else name
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-_")
    return slug or "generated-image"


def _read_image_dimensions(path: Path) -> dict[str, int]:
    try:
        return image_dimensions(path)
    except (OSError, UnidentifiedImageError) as exc:
        raise ProviderError(f"Provider output was not a readable image: {path.name}") from exc


def _extract_error_message(raw: str, fallback: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return redact_message(f"{fallback}: {raw}") if raw else fallback
    if isinstance(data, dict) and "error" in data:
        return redact_message(_error_object_message(data["error"]))
    return redact_message(fallback)


def _error_object_message(error: Any) -> str:
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            return str(message)
    return str(error)


def redact_message(value: str) -> str:
    text = re.sub(r"Bearer\s+[^\s]+", "Bearer [REDACTED]", value, flags=re.IGNORECASE)
    text = re.sub(r"sk-[A-Za-z0-9._-]+", "[REDACTED]", text)
    text = re.sub(r"https?://[^\s]+", lambda match: redact_url(match.group(0)), text)
    return text


def redact_url(value: str) -> str:
    parts = urlsplit(value)
    host = parts.hostname or ""
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))
