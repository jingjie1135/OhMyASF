import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


def load_generate2dsprite_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "skills" / "generate2dsprite" / "scripts" / "generate2dsprite.py"
    spec = importlib.util.spec_from_file_location("generate2dsprite_script", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load generate2dsprite script from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Generate2DSpriteProcessTests(unittest.TestCase):
    def _write_two_by_two_raw_sheet(self, input_path: Path) -> None:
        raw = Image.new("RGBA", (128, 128), (255, 0, 255, 255))
        for row in range(2):
            for col in range(2):
                x0 = col * 64 + 12
                y0 = row * 64 + 12
                raw.paste((20 + row * 100, 40 + col * 100, 80, 255), (x0, y0, x0 + 40, y0 + 40))
        raw.save(input_path)

    def _process_idle_sheet(self, module, input_path: Path, output_dir: Path, cell_size: int | None) -> None:
        module.cmd_process(
            argparse.Namespace(
                input=input_path,
                target="asset",
                mode="idle",
                output_dir=output_dir,
                role=None,
                prompt=None,
                prompt_file=None,
                threshold=100,
                edge_threshold=150,
                cell_size=cell_size,
                rows=None,
                cols=None,
                label_prefix=None,
                fit_scale=0.85,
                trim_border=4,
                edge_clean_depth=3,
                align="center",
                shared_scale=False,
                component_mode="all",
                component_padding=0,
                min_component_area=1,
                edge_touch_margin=0,
                reject_edge_touch=False,
                single_size=256,
                duration=200,
            )
        )

    def test_process_without_cell_size_preserves_grid_cell_dimensions(self) -> None:
        module = load_generate2dsprite_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "raw.png"
            output_dir = root / "out"
            self._write_two_by_two_raw_sheet(input_path)

            self._process_idle_sheet(module, input_path, output_dir, cell_size=None)

            with Image.open(output_dir / "sheet-transparent.png") as sheet_image:
                sheet_size = sheet_image.size
            with Image.open(output_dir / "idle-1.png") as frame_image:
                frame_size = frame_image.size
            metadata = json.loads((output_dir / "pipeline-meta.json").read_text(encoding="utf-8"))

        self.assertEqual(sheet_size, (128, 128))
        self.assertEqual(frame_size, (64, 64))
        self.assertEqual(metadata["cell_size_source"], "inferred_from_input")
        self.assertEqual(metadata["source_cell_width"], 64)
        self.assertEqual(metadata["source_cell_height"], 64)
        self.assertEqual(metadata["output_cell_width"], 64)
        self.assertEqual(metadata["output_cell_height"], 64)

    def test_process_with_explicit_cell_size_keeps_fixed_resize_behavior(self) -> None:
        module = load_generate2dsprite_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "raw.png"
            output_dir = root / "out"
            self._write_two_by_two_raw_sheet(input_path)

            self._process_idle_sheet(module, input_path, output_dir, cell_size=32)

            with Image.open(output_dir / "sheet-transparent.png") as sheet_image:
                sheet_size = sheet_image.size
            with Image.open(output_dir / "idle-1.png") as frame_image:
                frame_size = frame_image.size
            metadata = json.loads((output_dir / "pipeline-meta.json").read_text(encoding="utf-8"))

        self.assertEqual(sheet_size, (64, 64))
        self.assertEqual(frame_size, (32, 32))
        self.assertEqual(metadata["cell_size"], 32)
        self.assertEqual(metadata["cell_size_source"], "explicit")
        self.assertEqual(metadata["source_cell_width"], 64)
        self.assertEqual(metadata["source_cell_height"], 64)
        self.assertEqual(metadata["output_cell_width"], 32)
        self.assertEqual(metadata["output_cell_height"], 32)


if __name__ == "__main__":
    unittest.main()
