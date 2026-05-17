import json
import tempfile
import unittest
from pathlib import Path

from agent_sprite_forge.imagegen.cli import main


class CliTests(unittest.TestCase):
    def test_dry_run_writes_manifest_with_resolved_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.json"
            request_path = root / "request.json"
            output_dir = root / "out"
            config_path.write_text(
                json.dumps({"base_url": "https://new.example.com/v1", "api_key_env": "NEW_API_KEY"}),
                encoding="utf-8",
            )
            request_path.write_text(
                json.dumps({"prompt": "side scroll parallax map", "map_mode": "side_scroll_mode"}),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "generate",
                    "--config",
                    str(config_path),
                    "--request",
                    str(request_path),
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ],
                environ={},
            )

            manifest = json.loads((output_dir / "imagegen-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["provider"], "openai_compatible")
        self.assertEqual(manifest["selected_model"], "firefly-gpt-image-2k-16x9")
        self.assertTrue(manifest["dry_run"])
        self.assertEqual(manifest["outputs"], [])

    def test_generate_without_api_key_writes_failure_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.json"
            request_path = root / "request.json"
            output_dir = root / "out"
            config_path.write_text(
                json.dumps({"base_url": "https://new.example.com/v1", "api_key_env": "NEW_API_KEY"}),
                encoding="utf-8",
            )
            request_path.write_text(json.dumps({"prompt": "sprite"}), encoding="utf-8")

            exit_code = main(
                [
                    "generate",
                    "--config",
                    str(config_path),
                    "--request",
                    str(request_path),
                    "--output-dir",
                    str(output_dir),
                ],
                environ={},
            )
            manifest = json.loads((output_dir / "imagegen-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["error"]["type"], "ConfigError")
        self.assertEqual(manifest["selected_model"], "firefly-gpt-image-1k-1x1")

    def test_invalid_request_writes_failure_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.json"
            request_path = root / "request.json"
            output_dir = root / "out"
            config_path.write_text(json.dumps({"base_url": "https://new.example.com/v1"}), encoding="utf-8")
            request_path.write_text(json.dumps({"prompt": "sprite", "n": "many"}), encoding="utf-8")

            exit_code = main(
                [
                    "generate",
                    "--config",
                    str(config_path),
                    "--request",
                    str(request_path),
                    "--output-dir",
                    str(output_dir),
                ],
                environ={},
            )
            manifest = json.loads((output_dir / "imagegen-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["error"]["type"], "RequestValidationError")

    def test_preferred_references_write_text_only_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.json"
            request_path = root / "request.json"
            output_dir = root / "out"
            config_path.write_text(json.dumps({"base_url": "https://new.example.com/v1"}), encoding="utf-8")
            request_path.write_text(
                json.dumps(
                    {
                        "prompt": "sprite matching a written reference description",
                        "references": [{"path": "ref.png", "role": "identity_style"}],
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "generate",
                    "--config",
                    str(config_path),
                    "--request",
                    str(request_path),
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ],
                environ={},
            )
            manifest = json.loads((output_dir / "imagegen-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertIn("not sent", manifest["warnings"][0])

    def test_required_reference_fails_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.json"
            request_path = root / "request.json"
            output_dir = root / "out"
            config_path.write_text(json.dumps({"base_url": "https://new.example.com/v1"}), encoding="utf-8")
            request_path.write_text(
                json.dumps(
                    {
                        "prompt": "same exact character",
                        "references": [{"path": "ref.png", "role": "identity_style", "required": True}],
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "generate",
                    "--config",
                    str(config_path),
                    "--request",
                    str(request_path),
                    "--output-dir",
                    str(output_dir),
                ],
                environ={"OPENAI_API_KEY": "secret"},
            )
            manifest = json.loads((output_dir / "imagegen-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(manifest["error"]["type"], "RequestValidationError")
        self.assertIn("references", manifest["error"]["message"])

    def test_dry_run_manifest_redacts_credentials_from_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.json"
            request_path = root / "request.json"
            output_dir = root / "out"
            config_path.write_text(
                json.dumps({"base_url": "https://user:secret@new.example.com/v1"}),
                encoding="utf-8",
            )
            request_path.write_text(json.dumps({"prompt": "sprite"}), encoding="utf-8")

            exit_code = main(
                [
                    "generate",
                    "--config",
                    str(config_path),
                    "--request",
                    str(request_path),
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ],
                environ={},
            )
            manifest = json.loads((output_dir / "imagegen-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(manifest["base_url"], "https://new.example.com/v1")
        self.assertEqual(manifest["endpoint_path"], "https://new.example.com/v1/images/generations")


if __name__ == "__main__":
    unittest.main()
