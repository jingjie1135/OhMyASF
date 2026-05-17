import json
import tempfile
import unittest
from pathlib import Path

from agent_sprite_forge.imagegen.config import ImageGenConfig, load_config
from agent_sprite_forge.imagegen.errors import RequestValidationError
from agent_sprite_forge.imagegen.schema import ImageGenRequest


class ConfigSchemaTests(unittest.TestCase):
    def test_load_config_applies_environment_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "base_url": "https://old.example.com/v1",
                        "api_key_env": "OLD_KEY",
                        "size_mode": "model_id",
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(
                config_path,
                environ={
                    "AGENT_SPRITE_FORGE_IMAGEGEN_BASE_URL": "https://new.example.com/v1",
                    "AGENT_SPRITE_FORGE_IMAGEGEN_API_KEY_ENV": "NEW_API_KEY",
                    "AGENT_SPRITE_FORGE_IMAGEGEN_SIZE_MODE": "explicit",
                },
            )

        self.assertEqual(config.base_url, "https://new.example.com/v1")
        self.assertEqual(config.api_key_env, "NEW_API_KEY")
        self.assertEqual(config.size_mode, "explicit")

    def test_request_requires_prompt(self) -> None:
        with self.assertRaises(RequestValidationError):
            ImageGenRequest.from_dict({"asset_role": "sprite_sheet"})

    def test_request_rejects_invalid_n(self) -> None:
        with self.assertRaises(RequestValidationError):
            ImageGenRequest.from_dict({"prompt": "sprite", "n": "many"})

    def test_request_extra_body_cannot_override_core_payload_fields(self) -> None:
        with self.assertRaises(RequestValidationError):
            ImageGenRequest.from_dict({"prompt": "sprite", "extra_body": {"model": "bad-model"}})

    def test_config_extra_body_cannot_override_core_payload_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "base_url": "https://new.example.com/v1",
                        "extra_body": {"prompt": "override"},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(Exception, "extra_body"):
                load_config(config_path, environ={})

    def test_config_rejects_invalid_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                json.dumps({"base_url": "https://new.example.com/v1", "timeout_seconds": "slow"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(Exception, "timeout_seconds"):
                load_config(config_path, environ={})

    def test_request_normalizes_defaults(self) -> None:
        request = ImageGenRequest.from_dict({"prompt": "a 2x2 idle sprite sheet"})

        self.assertEqual(request.version, "1")
        self.assertEqual(request.n, 1)
        self.assertEqual(request.output_name, "generated-image")
        self.assertEqual(request.extra_body, {})

    def test_config_defaults_are_openai_compatible(self) -> None:
        config = ImageGenConfig(base_url="https://new.example.com/v1")

        self.assertEqual(config.provider, "openai_compatible")
        self.assertEqual(config.api_key_env, "OPENAI_API_KEY")
        self.assertEqual(config.default_family, "firefly-gpt-image")
        self.assertEqual(config.default_resolution, "1k")
        self.assertEqual(config.default_ratio, "1x1")
        self.assertEqual(config.size_mode, "model_id")


if __name__ == "__main__":
    unittest.main()
