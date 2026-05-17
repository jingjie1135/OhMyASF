import base64
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from agent_sprite_forge.imagegen.config import ImageGenConfig
from agent_sprite_forge.imagegen.errors import ProviderError
from agent_sprite_forge.imagegen.openai_compatible import (
    DEFAULT_MAX_DOWNLOAD_BYTES,
    build_generation_payload,
    call_images_generations,
    endpoint_url,
    save_generation_response,
)
from agent_sprite_forge.imagegen.schema import ImageGenRequest


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class OpenAICompatibleTests(unittest.TestCase):
    def test_endpoint_url_appends_images_generations_to_base_url(self) -> None:
        self.assertEqual(
            endpoint_url("https://new.example.com/v1/"),
            "https://new.example.com/v1/images/generations",
        )

    def test_payload_merges_negative_prompt_and_extra_body_without_size_in_model_id_mode(self) -> None:
        request = ImageGenRequest.from_dict(
            {
                "prompt": "2x2 fire mage sprite sheet",
                "negative_prompt": "text, labels",
                "n": 2,
                "extra_body": {"quality": "low"},
            }
        )

        payload = build_generation_payload(
            request=request,
            model="firefly-gpt-image-1k-1x1",
            sent_size=None,
            response_format="b64_json",
        )

        self.assertEqual(payload["model"], "firefly-gpt-image-1k-1x1")
        self.assertEqual(payload["n"], 2)
        self.assertNotIn("size", payload)
        self.assertIn("Avoid: text, labels", payload["prompt"])
        self.assertEqual(payload["response_format"], "b64_json")
        self.assertEqual(payload["quality"], "low")

    def test_payload_uses_config_extra_body_and_request_overrides(self) -> None:
        request = ImageGenRequest.from_dict(
            {
                "prompt": "sprite",
                "extra_body": {"quality": "high"},
            }
        )

        payload = build_generation_payload(
            request=request,
            model="firefly-gpt-image-1k-1x1",
            sent_size=None,
            response_format="b64_json",
            extra_body={"quality": "low", "output_format": "png"},
        )

        self.assertEqual(payload["quality"], "high")
        self.assertEqual(payload["output_format"], "png")

    def test_save_generation_response_writes_b64_png_and_metadata(self) -> None:
        response = {
            "created": 1715850000,
            "data": [
                {
                    "b64_json": base64.b64encode(PNG_1X1).decode("ascii"),
                    "revised_prompt": "revised prompt",
                }
            ],
            "usage": {"total_tokens": 10},
        }

        with tempfile.TemporaryDirectory() as tmp:
            outputs = save_generation_response(
                response=response,
                output_dir=Path(tmp),
                output_name="sprite-sheet",
            )

            image_path = Path(outputs[0]["path"])
            meta_path = image_path.with_suffix(".json")
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))

        self.assertEqual(image_path.name, "sprite-sheet.png")
        self.assertEqual(outputs[0]["dimensions"], {"width": 1, "height": 1})
        self.assertEqual(outputs[0]["role"], "raw")
        self.assertEqual(metadata["revised_prompt"], "revised prompt")

    def test_save_generation_response_downloads_url_when_b64_is_absent(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            def read(self, size: int = -1) -> bytes:
                return PNG_1X1

        called_urls: list[str] = []

        def fake_urlopen(url: str, timeout: int) -> FakeResponse:
            called_urls.append(url)
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmp:
            outputs = save_generation_response(
                response={"data": [{"url": "https://cdn.example.com/image.png"}]},
                output_dir=Path(tmp),
                output_name="downloaded",
                urlopen_func=fake_urlopen,
                resolver_func=public_resolver,
            )

        self.assertEqual(called_urls, ["https://cdn.example.com/image.png"])
        self.assertEqual(outputs[0]["dimensions"], {"width": 1, "height": 1})

    def test_save_generation_response_rejects_non_image_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ProviderError, "not a readable image"):
                save_generation_response(
                    response={
                        "data": [
                            {
                                "b64_json": base64.b64encode(b"not an image").decode("ascii"),
                            }
                        ]
                    },
                    output_dir=Path(tmp),
                    output_name="bad-image",
                )

    def test_save_generation_response_sanitizes_output_name(self) -> None:
        response = {"data": [{"b64_json": base64.b64encode(PNG_1X1).decode("ascii")}]} 
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            outputs = save_generation_response(response=response, output_dir=output_dir, output_name="../escape")
            image_path = Path(outputs[0]["path"])

        self.assertEqual(image_path.parent, output_dir)
        self.assertEqual(image_path.name, "escape.png")

    def test_save_generation_response_wraps_url_download_failure(self) -> None:
        def fake_urlopen(url: str, timeout: int) -> object:
            raise urllib.error.URLError(
                "download failed https://user:pass@example.com/path?token=abc Authorization: Bearer sk-secret"
            )

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ProviderError) as caught:
                save_generation_response(
                    response={"data": [{"url": "https://cdn.example.com/image.png"}]},
                    output_dir=Path(tmp),
                    output_name="downloaded",
                    urlopen_func=fake_urlopen,
                    resolver_func=public_resolver,
                )

        message = str(caught.exception)
        self.assertIn("download failed", message)
        self.assertNotIn("sk-secret", message)
        self.assertNotIn("user:pass", message)
        self.assertNotIn("token=abc", message)
        self.assertIn("[REDACTED]", message)

    def test_save_generation_response_rejects_unsafe_url_schemes_and_private_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ProviderError, "Only HTTPS"):
                save_generation_response(
                    response={"data": [{"url": "file:///etc/passwd"}]},
                    output_dir=Path(tmp),
                    output_name="file-url",
                )

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ProviderError, "blocked network"):
                save_generation_response(
                    response={"data": [{"url": "https://169.254.169.254/latest/meta-data"}]},
                    output_dir=Path(tmp),
                    output_name="metadata-url",
                )

        def private_resolver(host: str, port: int, type: int = 0) -> list[tuple[object, ...]]:
            return [(None, None, None, "", ("127.0.0.1", port))]

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ProviderError, "blocked network"):
                save_generation_response(
                    response={"data": [{"url": "https://cdn.example.com/image.png"}]},
                    output_dir=Path(tmp),
                    output_name="private-dns",
                    resolver_func=private_resolver,
                )

    def test_save_generation_response_redacts_signed_source_url_metadata(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            def geturl(self) -> str:
                return "https://cdn.example.com/image.png?X-Amz-Signature=secret&token=abc#frag"

            def read(self, size: int = -1) -> bytes:
                return PNG_1X1

        def fake_urlopen(url: str, timeout: int) -> FakeResponse:
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmp:
            outputs = save_generation_response(
                response={
                    "data": [
                        {
                            "url": "https://cdn.example.com/image.png?X-Amz-Signature=secret&token=abc#frag"
                        }
                    ]
                },
                output_dir=Path(tmp),
                output_name="signed-url",
                urlopen_func=fake_urlopen,
                resolver_func=public_resolver,
            )
            metadata = json.loads(Path(outputs[0]["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(metadata["source_url"], "https://cdn.example.com/image.png")

    def test_save_generation_response_rejects_downloads_over_size_limit(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            def read(self, size: int = -1) -> bytes:
                return b"x" * size

        def fake_urlopen(url: str, timeout: int) -> FakeResponse:
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ProviderError, "too large"):
                save_generation_response(
                    response={"data": [{"url": "https://cdn.example.com/image.png"}]},
                    output_dir=Path(tmp),
                    output_name="huge",
                    urlopen_func=fake_urlopen,
                    resolver_func=public_resolver,
                    max_download_bytes=16,
                )

        self.assertGreater(DEFAULT_MAX_DOWNLOAD_BYTES, 16)

    def test_config_reads_api_key_from_configured_environment_variable(self) -> None:
        config = ImageGenConfig(base_url="https://new.example.com/v1", api_key_env="NEW_API_KEY")

        self.assertEqual(config.api_key({"NEW_API_KEY": "secret"}), "secret")

    def test_call_images_generations_extracts_http_error_message(self) -> None:
        def fake_urlopen(request: object, timeout: int) -> object:
            raise urllib.error.HTTPError(
                url="https://new.example.com/v1/images/generations",
                code=400,
                msg="Bad Request",
                hdrs=None,
                fp=_BytesReader(b'{"error":{"message":"unsupported size"}}'),
            )

        with self.assertRaisesRegex(ProviderError, "unsupported size"):
            call_images_generations(
                config=ImageGenConfig(base_url="https://new.example.com/v1"),
                request=ImageGenRequest.from_dict({"prompt": "sprite"}),
                model="firefly-gpt-image-1k-1x1",
                sent_size=None,
                api_key="secret",
                urlopen_func=fake_urlopen,
            )

    def test_call_images_generations_redacts_secrets_from_provider_errors(self) -> None:
        def fake_urlopen(request: object, timeout: int) -> object:
            raise urllib.error.HTTPError(
                url="https://new.example.com/v1/images/generations",
                code=500,
                msg="Server Error",
                hdrs=None,
                fp=_BytesReader(
                    b'{"error":{"message":"Authorization: Bearer sk-secret https://user:pass@example.com/path?token=abc"}}'
                ),
            )

        with self.assertRaises(ProviderError) as caught:
            call_images_generations(
                config=ImageGenConfig(base_url="https://new.example.com/v1"),
                request=ImageGenRequest.from_dict({"prompt": "sprite"}),
                model="firefly-gpt-image-1k-1x1",
                sent_size=None,
                api_key="secret",
                urlopen_func=fake_urlopen,
            )

        message = str(caught.exception)
        self.assertNotIn("sk-secret", message)
        self.assertNotIn("user:pass", message)
        self.assertNotIn("token=abc", message)
        self.assertIn("[REDACTED]", message)

    def test_call_images_generations_redacts_secrets_from_success_error_payload(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            def read(self) -> bytes:
                return (
                    b'{"error":{"message":"Authorization: Bearer sk-secret '
                    b'https://user:pass@example.com/path?token=abc"}}'
                )

        def fake_urlopen(request: object, timeout: int) -> FakeResponse:
            return FakeResponse()

        with self.assertRaises(ProviderError) as caught:
            call_images_generations(
                config=ImageGenConfig(base_url="https://new.example.com/v1"),
                request=ImageGenRequest.from_dict({"prompt": "sprite"}),
                model="firefly-gpt-image-1k-1x1",
                sent_size=None,
                api_key="secret",
                urlopen_func=fake_urlopen,
            )

        message = str(caught.exception)
        self.assertNotIn("sk-secret", message)
        self.assertNotIn("user:pass", message)
        self.assertNotIn("token=abc", message)
        self.assertIn("[REDACTED]", message)

    def test_call_images_generations_redacts_secrets_from_request_url_errors(self) -> None:
        def fake_urlopen(request: object, timeout: int) -> object:
            raise urllib.error.URLError(
                "Authorization: Bearer sk-secret https://user:pass@example.com/path?token=abc"
            )

        with self.assertRaises(ProviderError) as caught:
            call_images_generations(
                config=ImageGenConfig(base_url="https://new.example.com/v1"),
                request=ImageGenRequest.from_dict({"prompt": "sprite"}),
                model="firefly-gpt-image-1k-1x1",
                sent_size=None,
                api_key="secret",
                urlopen_func=fake_urlopen,
            )

        message = str(caught.exception)
        self.assertNotIn("sk-secret", message)
        self.assertNotIn("user:pass", message)
        self.assertNotIn("token=abc", message)
        self.assertIn("[REDACTED]", message)

    def test_call_images_generations_rejects_malformed_json_response(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            def read(self) -> bytes:
                return b"not-json"

        def fake_urlopen(request: object, timeout: int) -> FakeResponse:
            return FakeResponse()

        with self.assertRaisesRegex(ProviderError, "not valid JSON"):
            call_images_generations(
                config=ImageGenConfig(base_url="https://new.example.com/v1"),
                request=ImageGenRequest.from_dict({"prompt": "sprite"}),
                model="firefly-gpt-image-1k-1x1",
                sent_size=None,
                api_key="secret",
                urlopen_func=fake_urlopen,
            )

    def test_call_images_generations_reports_timeout(self) -> None:
        def fake_urlopen(request: object, timeout: int) -> object:
            raise TimeoutError("timed out")

        with self.assertRaisesRegex(ProviderError, "timed out"):
            call_images_generations(
                config=ImageGenConfig(base_url="https://new.example.com/v1"),
                request=ImageGenRequest.from_dict({"prompt": "sprite"}),
                model="firefly-gpt-image-1k-1x1",
                sent_size=None,
                api_key="secret",
                urlopen_func=fake_urlopen,
            )


class _BytesReader:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, size: int = -1) -> bytes:
        return self._data


def public_resolver(host: str, port: int, type: int = 0) -> list[tuple[object, ...]]:
    return [(None, None, None, "", ("93.184.216.34", port))]


if __name__ == "__main__":
    unittest.main()
