"""Independent geometry oracles and fail-closed evidence contracts."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/summarize_mesh.py"
spec = importlib.util.spec_from_file_location("mesh", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
VTK = b"""# vtk DataFile Version 2.0
surface
ASCII
DATASET POLYDATA
POINTS 6 float
0 0 0 1 0 0 1 1 0 0 1 0 4 0 0 4 1 0
POLYGONS 2 10
4 0 1 2 3 4 1 4 5 2
CELL_DATA 2
FIELD FieldData 1
nSurfaceLayers 1 2 float
0 18
"""


class EvidenceTests(unittest.TestCase):
    def metrics(self, data=VTK):
        v = m.parse_vtk_polydata(data)
        return m.compute_metrics(
            v["points"], v["polygons"], v["nSurfaceLayers"], 18, 0.9
        )

    def test_unequal_area_oracle(self):
        # Adjacent rectangles independently have widths 1 and 3, height 1.
        r = self.metrics()
        for key, value in dict(
            total_area=4,
            area_coverage=0.75,
            face_coverage=0.5,
            weighted_layer_count=13.5,
            full_area=3,
            full_area_coverage=0.75,
            min_layer=0,
            max_layer=18,
        ).items():
            self.assertEqual(r[key], value)

    def test_swapped_area_oracle(self):
        r = self.metrics(VTK.replace(b"0 18\n", b"18 0\n"))
        self.assertEqual(r["area_coverage"], 0.25)
        self.assertEqual(r["weighted_layer_count"], 4.5)
        self.assertEqual(r["full_area"], 1)

    def test_partial_layers_not_full(self):
        r = self.metrics(VTK.replace(b"0 18\n", b"0 9\n"))
        self.assertEqual(r["area_coverage"], 0.75)
        self.assertEqual(r["full_area"], 0)
        self.assertEqual(r["weighted_layer_count"], 6.75)

    def test_wrapping_numeric_type_and_metadata(self):
        lines = VTK.decode().splitlines()
        wrapped = (
            "\n".join(lines[:4]) + "\n" + "\n".join(" ".join(lines[4:]).split())
        ).encode()
        self.assertEqual(self.metrics(wrapped), self.metrics())
        self.assertEqual(self.metrics(VTK.replace(b"float", b"double")), self.metrics())
        metadata = VTK.replace(
            b"POINTS", b"FIELD FieldData 1\nTimeValue 1 1 double\n0\nPOINTS"
        )
        self.assertEqual(self.metrics(metadata), self.metrics())

    def test_rotated_translated_polygon(self):
        self.assertEqual(
            m.polygon_area_3d(
                [(10, 20, 30), (10, 22, 30), (10, 22, 33), (10, 20, 33)], (0, 1, 2, 3)
            ),
            6,
        )

    def test_malformed_inputs(self):
        replacements = [
            (b"ASCII", b"BINARY"),
            (b"Version 2.0", b"Version 5.1"),
            (b"POLYDATA", b"UNSTRUCTURED_GRID"),
            (b"POINTS 6", b"POINTS 1000001"),
            (b"POINTS 6", b"POINTS 0"),
            (b"POLYGONS 2 10", b"POLYGONS 2 11"),
            (b"POLYGONS 2 10", b"POLYGONS 1000001 10"),
            (b"4 0 1 2 3", b"4 0 1 2 6"),
            (b"4 0 1 2 3", b"4 0 1 2 -1"),
            (b"4 0 1 2 3", b"4 0 1 2 2"),
            (b"CELL_DATA 2", b"CELL_DATA 1"),
            (b"nSurfaceLayers 1 2", b"nSurfaceLayers 1 1"),
            (b"nSurfaceLayers 1 2", b"nSurfaceLayers 2 2"),
            (b"nSurfaceLayers", b"other"),
            (b"0 18\n", b"0\n"),
            (b"0 18\n", b"0 18 1\n"),
            (b"0 18\n", b"0 -1\n"),
            (b"0 18\n", b"0 1.5\n"),
            (b"0 18\n", b"0 nan\n"),
            (b"0 18\n", b"0 inf\n"),
            (b"0 0 0 1", b"inf 0 0 1"),
            (b"0 0 0 1", b"nan 0 0 1"),
            (b"0 0 0 1", b"1e999 0 0 1"),
        ]
        for old, new in replacements:
            with self.subTest(new=new), self.assertRaises(ValueError):
                m.parse_vtk_polydata(VTK.replace(old, new))
        for data in (VTK.split(b"CELL_DATA")[0], VTK[:80], VTK + b"garbage", b""):
            with self.subTest(data=data), self.assertRaises(ValueError):
                m.parse_vtk_polydata(data)

    def test_degenerate_facets_rejected(self):
        for face in ((0, 1, 2), (0, 0, 1)):
            with self.assertRaises(ValueError):
                m.polygon_area_3d([(0, 0, 0), (1, 0, 0), (2, 0, 0)], face)

    def test_bounds(self):
        for kw in ({"max_size": 10}, {"max_points": 5}, {"max_polygons": 1}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                m.parse_vtk_polydata(VTK, **kw)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large"
            path.write_bytes(b"12345")
            with patch.object(m, "MAX_BYTES", 4), self.assertRaises(ValueError):
                m.read_bounded(path)

    def test_invalid_parameters(self):
        for layers, coverage in [
            (0, 0.9),
            (-1, 0.9),
            (1.5, 0.9),
            (True, 0.9),
            (1001, 0.9),
            (18, -0.1),
            (18, 1.1),
            (18, float("nan")),
            (18, float("inf")),
        ]:
            with (
                self.subTest(layers=layers, coverage=coverage),
                self.assertRaises(ValueError),
            ):
                m.validate_parameters(layers, coverage)

    def test_missing_and_invalid_metric_data(self):
        v = m.parse_vtk_polydata(VTK)
        for layers in (None, (), (0,), (0, 19), (0, 1.5), (0, float("inf"))):
            with self.subTest(layers=layers), self.assertRaises(ValueError):
                m.compute_metrics(v["points"], v["polygons"], layers, 18, 0.9)
        with self.assertRaises(ValueError):
            m.compute_metrics([], [], [], 18, 0.9)

    def test_complete_log_and_failure_precedence(self):
        self.assertTrue(m.parse_checkmesh_log("Mesh OK.\n\nEnd\n")["mesh_ok"])
        for log in ("", "Mesh OK.\n", "End\nMesh OK.\n", "no result"):
            self.assertIsNone(m.parse_checkmesh_log(log)["mesh_ok"])
        for log in (
            "Mesh OK.\nEnd\nFailed 2 mesh checks.\n",
            "FOAM FATAL ERROR\nMesh OK.\nEnd\n",
        ):
            self.assertFalse(m.parse_checkmesh_log(log)["mesh_ok"])
        self.assertEqual(
            m.parse_checkmesh_log("Failed 10 mesh checks.\nEnd")["failed_checks"], 10
        )

    def run_cli(self, root, data=VTK, log=b"Mesh OK.\r\n\r\nEnd\r\n", extra=()):
        surface = root / "wall.vtk"
        meshlog = root / "log"
        output = root / "out.json"
        surface.write_bytes(data)
        meshlog.write_bytes(log)
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--wall-surface",
                str(surface),
                "--mesh-log",
                str(meshlog),
                "--output",
                str(output),
                *extra,
            ],
            capture_output=True,
            text=True,
        )
        return result, output

    def test_cli_pass_and_raw_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, out = self.run_cli(root, extra=("--minimum-coverage", ".75"))
            self.assertEqual(result.returncode, 0, result.stderr)
            r = json.loads(out.read_text())
            self.assertEqual(
                r["input"]["mesh_log_hash"],
                hashlib.sha256((root / "log").read_bytes()).hexdigest(),
            )
            self.assertEqual(
                r["input"]["wall_surface_hash"], hashlib.sha256(VTK).hexdigest()
            )
            self.assertTrue(r["overall"]["gate_passed"])
            self.assertIn("not yPlus", r["evidence_scope"])

    def test_cli_gate_failures(self):
        for log in (b"Mesh OK.\nEnd\n", b"Failed 2 mesh checks.\nEnd\n", b""):
            with self.subTest(log=log), tempfile.TemporaryDirectory() as tmp:
                result, out = self.run_cli(Path(tmp), log=log)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(
                    json.loads(out.read_text())["overall"]["status"], "gate_failure"
                )

    def test_cli_input_error_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, out = self.run_cli(Path(tmp), data=VTK.replace(b"ASCII", b"BINARY"))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(
                json.loads(out.read_text())["overall"]["status"], "input_error"
            )

    def test_cli_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out.json"
            out.write_text("preserve")
            result, _ = self.run_cli(root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(out.read_text(), "preserve")

    def test_cli_invalid_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, out = self.run_cli(Path(tmp), extra=("--minimum-coverage", "nan"))
            self.assertEqual(result.returncode, 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
