import unittest

from agent_sprite_forge.imagegen.config import ImageGenConfig
from agent_sprite_forge.imagegen.errors import ModelResolutionError
from agent_sprite_forge.imagegen.model_catalog import is_valid_model_id, is_video_model_id
from agent_sprite_forge.imagegen.model_resolver import resolve_model
from agent_sprite_forge.imagegen.schema import ImageGenRequest


class ModelResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ImageGenConfig(base_url="https://new.example.com/v1")

    def test_catalog_accepts_firefly_image_models_and_rejects_video_models(self) -> None:
        self.assertTrue(is_valid_model_id("firefly-gpt-image-1k-1x1"))
        self.assertTrue(is_valid_model_id("firefly-nano-banana2-2k-8x1"))
        self.assertFalse(is_valid_model_id("firefly-gpt-image-1k-8x1"))
        self.assertTrue(is_video_model_id("firefly-sora2-pro"))

    def test_default_sprite_sheet_routes_to_square_gpt_image_model(self) -> None:
        request = ImageGenRequest.from_dict(
            {"prompt": "fire mage 2x2 idle", "asset_role": "sprite_sheet"}
        )

        selection = resolve_model(request, self.config)

        self.assertEqual(selection.model, "firefly-gpt-image-1k-1x1")
        self.assertEqual(selection.ratio, "1x1")
        self.assertEqual(selection.sent_size, None)
        self.assertEqual(selection.size_mode, "model_id")

    def test_high_value_player_sheet_uses_higher_resolution_square_model(self) -> None:
        request = ImageGenRequest.from_dict(
            {"prompt": "samurai 4x4 player sheet", "asset_role": "player_sheet"}
        )

        selection = resolve_model(request, self.config)

        self.assertEqual(selection.model, "firefly-gpt-image-2k-1x1")
        self.assertIn("player_sheet", selection.reason)

    def test_side_scroll_maps_route_to_sixteen_by_nine(self) -> None:
        request = ImageGenRequest.from_dict(
            {"prompt": "cyberpunk parallax layer", "map_mode": "side_scroll_mode"}
        )

        selection = resolve_model(request, self.config)

        self.assertEqual(selection.model, "firefly-gpt-image-2k-16x9")
        self.assertEqual(selection.ratio, "16x9")

    def test_wide_platform_strips_fallback_to_family_that_supports_wide_ratios(self) -> None:
        request = ImageGenRequest.from_dict(
            {"prompt": "long bridge strip", "asset_role": "platform_strip"}
        )

        selection = resolve_model(request, self.config)

        self.assertEqual(selection.model, "firefly-nano-banana2-1k-4x1")
        self.assertEqual(selection.family, "firefly-nano-banana2")

    def test_manual_override_wins_but_video_models_are_rejected(self) -> None:
        request = ImageGenRequest.from_dict(
            {"prompt": "portrait map", "model": "firefly-gpt-image-4k-9x16"}
        )

        selection = resolve_model(request, self.config)

        self.assertEqual(selection.model, "firefly-gpt-image-4k-9x16")
        self.assertEqual(selection.source, "explicit")

        with self.assertRaises(ModelResolutionError):
            resolve_model(
                ImageGenRequest.from_dict({"prompt": "bad", "model": "firefly-sora2-pro"}),
                self.config,
            )

    def test_size_modes_control_whether_size_is_sent(self) -> None:
        request = ImageGenRequest.from_dict(
            {
                "prompt": "side scroll stage",
                "map_mode": "side_scroll_mode",
                "size_mode": "derived",
            }
        )
        selection = resolve_model(request, self.config)
        self.assertEqual(selection.sent_size, "2048x1152")

        explicit = resolve_model(
            ImageGenRequest.from_dict(
                {
                    "prompt": "sprite",
                    "size_mode": "explicit",
                    "size": "1024x1024",
                }
            ),
            self.config,
        )
        self.assertEqual(explicit.sent_size, "1024x1024")


if __name__ == "__main__":
    unittest.main()
