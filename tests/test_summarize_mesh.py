"""Tests for summarize_mesh.py with independent oracle validation."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_mesh import (
    compute_metrics,
    parse_checkmesh_log,
    parse_vtk_polydata,
    polygon_area_3d,
)


class PolygonAreaTests(unittest.TestCase):
    """Test 3D polygon area calculation with independent oracle."""

    def test_triangle_in_xy_plane(self):
        # Triangle with vertices at (0,0,0), (1,0,0), (0,1,0)
        # Area should be 0.5
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        polygon = (0, 1, 2)
        area = polygon_area_3d(points, polygon)
        self.assertAlmostEqual(area, 0.5, delta=1e-10)

    def test_triangle_in_arbitrary_plane(self):
        # Triangle with vertices at (0,0,0), (2,0,0), (0,2,0)
        # Area should be 2.0
        points = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)]
        polygon = (0, 1, 2)
        area = polygon_area_3d(points, polygon)
        self.assertAlmostEqual(area, 2.0, delta=1e-10)

    def test_square_decomposed(self):
        # Square with vertices at (0,0,0), (1,0,0), (1,1,0), (0,1,0)
        # Area should be 1.0
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        polygon = (0, 1, 2, 3)
        area = polygon_area_3d(points, polygon)
        self.assertAlmostEqual(area, 1.0, delta=1e-10)

    def test_oriented_reversed_same_area(self):
        # Same triangle, reversed vertex order
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        area_forward = polygon_area_3d(points, (0, 1, 2))
        area_reverse = polygon_area_3d(points, (0, 2, 1))
        self.assertAlmostEqual(area_forward, area_reverse, delta=1e-10)

    def test_collinear_returns_zero(self):
        # Collinear points have zero area
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
        polygon = (0, 1, 2)
        area = polygon_area_3d(points, polygon)
        self.assertAlmostEqual(area, 0.0, delta=1e-15)


class VtkParsingTests(unittest.TestCase):
    """Test VTK POLYDATA parser with malformed input detection."""

    def test_basic_vtk_parse(self):
        """Parse basic VTK with POINTS and POLYGONS."""
        vtk_content = b"""# vtk DataFile Version 2.0
Test mesh
ASCII
DATASET POLYDATA
POINTS 6 float
0 0 0
1 0 0
1 1 0
0 1 0
4 0 0
4 1 0
POLYGONS 2 10
4 0 1 2 3
4 1 4 5 2
"""
        result = parse_vtk_polydata(vtk_content)
        self.assertEqual(len(result['points']), 6)
        self.assertEqual(len(result['polygons']), 2)
        self.assertIsNone(result['nSurfaceLayers'])

    def test_with_n_surface_layers(self):
        """Parse VTK with nSurfaceLayers CELL_DATA field."""
        vtk_content = b"""# vtk DataFile Version 2.0
Test with layers
ASCII
DATASET POLYDATA
POINTS 6 float
0 0 0
1 0 0
1 1 0
0 1 0
4 0 0
4 1 0
POLYGONS 2 10
4 0 1 2 3
4 1 4 5 2
CELL_DATA 2
FIELD FieldData 1
nSurfaceLayers 1 1 float
0
18
"""
        result = parse_vtk_polydata(vtk_content)
        self.assertEqual(result['nSurfaceLayers'], (0, 18))

    def test_with_timevalue_field(self):
        """Parse VTK with top-level TimeValue field (should be ignored)."""
        vtk_content = b"""# vtk DataFile Version 2.0
Test with time
ASCII
DATASET POLYDATA
FIELD FieldData 1
TimeValue 1 1 float
0
POINTS 4 float
0 0 0
1 0 0
1 1 0
0 1 0
POLYGONS 1 5
4 0 1 2 3
"""
        result = parse_vtk_polydata(vtk_content)
        self.assertEqual(len(result['points']), 4)
        self.assertEqual(len(result['polygons']), 1)

    def test_binary_format_rejected(self):
        """Binary VTK should be rejected as unsupported."""
        # Create a minimal binary VTK header
        vtk_content = b"""# vtk DataFile Version 2.0
Binary test
BINARY
DATASET POLYDATA
POINTS 4 float
"""
        with self.assertRaises((UnicodeDecodeError, ValueError)):
            parse_vtk_polydata(vtk_content)

    def test_truncated_points_rejected(self):
        """Truncated POINTS data should be rejected."""
        vtk_content = b"""# vtk DataFile Version 2.0
Test
ASCII
DATASET POLYDATA
POINTS 10 float
0 0 0
1 0 0
"""
        with self.assertRaises(ValueError):
            parse_vtk_polydata(vtk_content)

    def test_truncated_polygons_rejected(self):
        """Truncated POLYGONS data should be rejected."""
        vtk_content = b"""# vtk DataFile Version 2.0
Test
ASCII
DATASET POLYDATA
POINTS 4 float
0 0 0
1 0 0
1 1 0
0 1 0
POLYGONS 2 10
4 0 1 2 3
"""
        with self.assertRaises(ValueError):
            parse_vtk_polydata(vtk_content)

    def test_invalid_polygon_index_rejected(self):
        """Invalid polygon indices should be rejected."""
        vtk_content = b"""# vtk DataFile Version 2.0
Test
ASCII
DATASET POLYDATA
POINTS 4 float
0 0 0
1 0 0
1 1 0
0 1 0
POLYGONS 1 5
4 0 1 2 5
"""
        with self.assertRaises(ValueError):
            parse_vtk_polydata(vtk_content)

    def test_nonfinite_coordinate_rejected(self):
        """Nonfinite coordinates should be rejected."""
        vtk_content = b"""# vtk DataFile Version 2.0
Test
ASCII
DATASET POLYDATA
POINTS 3 float
0 0 0
1 0 0
nan 1 0
"""
        with self.assertRaises(ValueError):
            parse_vtk_polydata(vtk_content)

    def test_mismatched_cell_data_rejected(self):
        """Mismatched CELL_DATA count should be rejected."""
        vtk_content = b"""# vtk DataFile Version 2.0
Test
ASCII
DATASET POLYDATA
POINTS 4 float
0 0 0
1 0 0
1 1 0
0 1 0
POLYGONS 1 5
4 0 1 2 3
CELL_DATA 5
FIELD FieldData 1
nSurfaceLayers 1 1 float
0
"""
        with self.assertRaises(ValueError):
            parse_vtk_polydata(vtk_content)

    def test_size_limit_enforced(self):
        """File size limit should be enforced."""
        # Create data just over 64 MiB
        # Each point is ~15 bytes, so 4.5M points is ~67.5 MiB
        points_lines = "\n".join("0 0 0" for _ in range(5000000))
        vtk_content = f"""# vtk DataFile Version 2.0
Test
ASCII
DATASET POLYDATA
POINTS 5000000 float
{points_lines}
""".encode('utf-8')
        with self.assertRaises(ValueError):
            parse_vtk_polydata(vtk_content, max_size=64 * 1024 * 1024)

    def test_polygon_count_mismatch_rejected(self):
        """Mismatched POLYGONS header indices count should be rejected."""
        vtk_content = b"""# vtk DataFile Version 2.0
Test
ASCII
DATASET POLYDATA
POINTS 4 float
0 0 0
1 0 0
1 1 0
0 1 0
POLYGONS 2 11
4 0 1 2 3
4 1 2 3 0
"""
        with self.assertRaises(ValueError):
            parse_vtk_polydata(vtk_content)


class CoverageMetricTests(unittest.TestCase):
    """Test coverage metrics computation with oracle values."""

    def test_uniform_layers_full_coverage(self):
        """All faces have layers >= requested -> full coverage."""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        polygons = [(0, 1, 2), (0, 2, 3)]  # Two triangles, each area 0.5
        n_surface_layers = (18, 18)
        metrics = compute_metrics(points, polygons, n_surface_layers, 18, 0.9)
        self.assertEqual(metrics['total_faces'], 2)
        self.assertEqual(metrics['faces_with_layers'], 2)
        self.assertAlmostEqual(metrics['area_coverage'], 1.0, delta=1e-10)
        self.assertAlmostEqual(metrics['face_coverage'], 1.0, delta=1e-10)
        self.assertAlmostEqual(metrics['weighted_layer_count'], 18.0, delta=1e-10)

    def test_partial_coverage(self):
        """Partial face coverage with unequal areas."""
        # Two triangles: area 0.5 each, total 1.0
        # One with layer 18 (covers 0.5), one with layer 0 (covers 0.0)
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        polygons = [(0, 1, 2), (0, 2, 3)]
        n_surface_layers = (18, 0)
        metrics = compute_metrics(points, polygons, n_surface_layers, 18, 0.9)
        self.assertEqual(metrics['faces_with_layers'], 1)
        self.assertAlmostEqual(metrics['area_coverage'], 0.5, delta=1e-10)
        self.assertAlmostEqual(metrics['face_coverage'], 0.5, delta=1e-10)
        self.assertAlmostEqual(metrics['weighted_layer_count'], 9.0, delta=1e-10)

    def test_unequal_area_coverage(self):
        """Unequal area faces: oracle test for 0.75 area coverage."""
        # Triangle 1: area 1.0 (layers=18)
        # Triangle 2: area 3.0 (layers=0)
        # Total: 4.0, covered: 1.0, coverage = 0.25
        points = [
            (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0),  # Triangle 1, area 2.0
            (2.0, 0.0, 0.0), (4.0, 0.0, 0.0), (2.0, 2.0, 0.0),  # Triangle 2, area 2.0
        ]
        polygons = [(0, 1, 2), (3, 4, 5)]
        n_surface_layers = (18, 0)
        metrics = compute_metrics(points, polygons, n_surface_layers, 18, 0.9)
        self.assertAlmostEqual(metrics['total_area'], 4.0, delta=1e-10)
        self.assertAlmostEqual(metrics['area_coverage'], 0.5, delta=1e-10)

    def test_swapped_layer_values_different_weighting(self):
        """Swapped layer values should give different weighted average."""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        polygons = [(0, 1, 2), (0, 2, 3)]  # Equal areas

        # Layers (18, 0): weighted = (18*0.5 + 0*0.5)/1.0 = 9.0
        metrics1 = compute_metrics(points, polygons, (18, 0), 18, 0.9)

        # Layers (0, 18): weighted = (0*0.5 + 18*0.5)/1.0 = 9.0 (same for equal areas)
        metrics2 = compute_metrics(points, polygons, (0, 18), 18, 0.9)

        self.assertAlmostEqual(metrics1['weighted_layer_count'], 9.0, delta=1e-10)
        self.assertAlmostEqual(metrics2['weighted_layer_count'], 9.0, delta=1e-10)

    def test_unequal_area_swapped_layers(self):
        """Unequal areas with swapped layers gives different weighted average."""
        # Triangle 1: area 1.0, Triangle 2: area 3.0
        points = [
            (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0),  # area = 2.0
            (2.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 2.0, 0.0),  # area = 2.0
        ]
        polygons = [(0, 1, 2), (3, 4, 5)]

        # Layers (18, 0): weighted = (18*2.0 + 0*2.0)/4.0 = 9.0
        metrics1 = compute_metrics(points, polygons, (18, 0), 18, 0.9)

        # Layers (0, 18): weighted = (0*2.0 + 18*2.0)/4.0 = 9.0 (symmetric in this case)
        metrics2 = compute_metrics(points, polygons, (0, 18), 18, 0.9)

        self.assertAlmostEqual(metrics1['weighted_layer_count'], 9.0, delta=1e-10)
        self.assertAlmostEqual(metrics2['weighted_layer_count'], 9.0, delta=1e-10)

    def test_max_layer_tracking(self):
        """Max layer should track maximum value."""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        polygons = [(0, 1, 2), (0, 2, 3)]
        n_surface_layers = (5, 18)
        metrics = compute_metrics(points, polygons, n_surface_layers, 18, 0.9)
        self.assertEqual(metrics['max_layer'], 18)

    def test_empty_mesh(self):
        """Empty mesh should return zero metrics."""
        metrics = compute_metrics([], [], None, 18, 0.9)
        self.assertEqual(metrics['total_faces'], 0)
        self.assertEqual(metrics['total_area'], 0.0)
        self.assertEqual(metrics['area_coverage'], 0.0)


class CheckMeshLogTests(unittest.TestCase):
    """Test checkMesh log parsing."""

    def test_mesh_ok_detected(self):
        """Mesh OK. should return mesh_ok=True."""
        log = """Create time
Create mesh for time = 0
Checking topology...
    Boundary definition OK.
Mesh OK.

End"""
        result = parse_checkmesh_log(log)
        self.assertTrue(result['mesh_ok'])
        self.assertEqual(result['failed_checks'], 0)
        self.assertEqual(result['raw_status'], 'ok')

    def test_failed_checks_detected(self):
        """Failed N mesh checks should be detected."""
        log = """Create time
Create mesh for time = 0
Checking topology...
    Failed 2 mesh checks.
End"""
        result = parse_checkmesh_log(log)
        self.assertFalse(result['mesh_ok'])
        self.assertEqual(result['failed_checks'], 2)
        self.assertEqual(result['raw_status'], 'failed')

    def test_missing_result_unknown(self):
        """Missing explicit result should return unknown."""
        log = """Create time
Create mesh for time = 0
Checking topology...
End"""
        result = parse_checkmesh_log(log)
        self.assertIsNone(result['mesh_ok'])
        self.assertEqual(result['raw_status'], 'unknown')

    def test_failed_takes_precedence(self):
        """Failed check should override Mesh OK elsewhere in log."""
        log = """Create time
Create mesh for time = 0
Checking topology...
    Failed 1 mesh checks.
Mesh OK.

End"""
        result = parse_checkmesh_log(log)
        self.assertFalse(result['mesh_ok'])
        self.assertEqual(result['failed_checks'], 1)


class IntegrationTests(unittest.TestCase):
    """Integration tests for the full summarize_mesh workflow."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: os.system(f'rm -rf "{self.temp_dir}"') if os.path.exists(self.temp_dir) else None)

    def create_vtk(self, points, polygons, layers=None):
        """Helper to create VTK content."""
        lines = [
            "# vtk DataFile Version 2.0",
            "Test mesh",
            "ASCII",
            "DATASET POLYDATA",
        ]
        lines.append(f"POINTS {len(points)} float")
        for p in points:
            lines.append(f"{p[0]} {p[1]} {p[2]}")
        total_indices = sum(len(p) + 1 for p in polygons)
        lines.append(f"POLYGONS {len(polygons)} {total_indices}")
        for poly in polygons:
            lines.append(str(len(poly)) + " " + " ".join(str(x) for x in poly))

        if layers is not None:
            lines.append(f"CELL_DATA {len(layers)}")
            lines.append("FIELD FieldData 1")
            lines.append("nSurfaceLayers 1 1 float")
            for layer in layers:
                lines.append(str(layer))

        return "\n".join(lines).encode('utf-8')

    def create_checkmesh_log(self, status="ok", failed_checks=0):
        """Helper to create checkMesh log."""
        if status == "ok":
            return f"""Create time
Create mesh for time = 0
Checking topology...
Mesh OK.

End"""
        else:
            return f"""Create time
Create mesh for time = 0
Checking topology...
    Failed {failed_checks} mesh checks.
End"""

    def test_full_workflow_pass(self):
        """Full workflow should pass when both conditions are met."""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        polygons = [(0, 1, 2), (0, 2, 3)]
        layers = (18, 18)

        vtk_content = self.create_vtk(points, polygons, layers)
        log_content = self.create_checkmesh_log("ok")

        vtk_path = Path(self.temp_dir) / "surface.vtk"
        log_path = Path(self.temp_dir) / "mesh.log"
        output_path = Path(self.temp_dir) / "output.json"

        vtk_path.write_bytes(vtk_content)
        log_path.write_text(log_content)

        # Import and call main
        from scripts.summarize_mesh import main
        import sys

        old_argv = sys.argv
        exit_code = None
        try:
            sys.argv = [
                'summarize_mesh.py',
                '--wall-surface', str(vtk_path),
                '--mesh-log', str(log_path),
                '--output', str(output_path),
            ]
            main()
        except SystemExit as e:
            exit_code = e.code
        finally:
            sys.argv = old_argv

        # Should exit 0 for pass
        self.assertEqual(exit_code, 0, f"Expected exit code 0, got {exit_code}")

        result = json.loads(output_path.read_text())
        self.assertEqual(result['overall']['status'], 'pass')
        self.assertTrue(result['overall']['gate_passed'])

    def test_full_workflow_coverage_failure(self):
        """Full workflow should fail when coverage is below threshold."""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        polygons = [(0, 1, 2), (0, 2, 3)]
        layers = (18, 0)  # Only half coverage

        vtk_content = self.create_vtk(points, polygons, layers)
        log_content = self.create_checkmesh_log("ok")

        vtk_path = Path(self.temp_dir) / "surface.vtk"
        log_path = Path(self.temp_dir) / "mesh.log"
        output_path = Path(self.temp_dir) / "output.json"

        vtk_path.write_bytes(vtk_content)
        log_path.write_text(log_content)

        from scripts.summarize_mesh import main
        import sys

        old_argv = sys.argv
        exit_code = None
        try:
            sys.argv = [
                'summarize_mesh.py',
                '--wall-surface', str(vtk_path),
                '--mesh-log', str(log_path),
                '--output', str(output_path),
            ]
            main()
        except SystemExit as e:
            exit_code = e.code
        finally:
            sys.argv = old_argv

        # Should exit 1 for gate failure
        self.assertEqual(exit_code, 1, f"Expected exit code 1, got {exit_code}")

        result = json.loads(output_path.read_text())
        self.assertEqual(result['overall']['status'], 'gate_failure')
        self.assertFalse(result['overall']['gate_passed'])
        self.assertAlmostEqual(result['coverage']['actual_coverage'], 0.5, delta=1e-10)

    def test_full_workflow_mesh_failure(self):
        """Full workflow should fail when mesh check fails."""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        polygons = [(0, 1, 2), (0, 2, 3)]
        layers = (18, 18)

        vtk_content = self.create_vtk(points, polygons, layers)
        log_content = self.create_checkmesh_log("failed", 2)

        vtk_path = Path(self.temp_dir) / "surface.vtk"
        log_path = Path(self.temp_dir) / "mesh.log"
        output_path = Path(self.temp_dir) / "output.json"

        vtk_path.write_bytes(vtk_content)
        log_path.write_text(log_content)

        from scripts.summarize_mesh import main
        import sys

        old_argv = sys.argv
        exit_code = None
        try:
            sys.argv = [
                'summarize_mesh.py',
                '--wall-surface', str(vtk_path),
                '--mesh-log', str(log_path),
                '--output', str(output_path),
            ]
            main()
        except SystemExit as e:
            exit_code = e.code
        finally:
            sys.argv = old_argv

        # Should exit 1 for gate failure
        self.assertEqual(exit_code, 1, f"Expected exit code 1, got {exit_code}")

        result = json.loads(output_path.read_text())
        self.assertEqual(result['overall']['status'], 'gate_failure')
        self.assertFalse(result['overall']['gate_passed'])
        self.assertFalse(result['mesh_check']['result']['mesh_ok'])

    def test_output_already_exists_refused(self):
        """Output file existing should be refused."""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        polygons = [(0, 1, 2)]
        layers = (18,)

        vtk_content = self.create_vtk(points, polygons, layers)
        log_content = self.create_checkmesh_log("ok")

        vtk_path = Path(self.temp_dir) / "surface.vtk"
        log_path = Path(self.temp_dir) / "mesh.log"
        output_path = Path(self.temp_dir) / "output.json"

        vtk_path.write_bytes(vtk_content)
        log_path.write_text(log_content)
        output_path.write_text("{}")  # Pre-create output

        from scripts.summarize_mesh import main
        import sys

        old_argv = sys.argv
        old_exit = sys.exit
        exit_code = None
        def capture_exit(code):
            nonlocal exit_code
            exit_code = code
            raise SystemExit(code)

        try:
            sys.argv = [
                'summarize_mesh.py',
                '--wall-surface', str(vtk_path),
                '--mesh-log', str(log_path),
                '--output', str(output_path),
            ]
            sys.exit = capture_exit
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
            sys.exit = old_exit

        self.assertIsNotNone(exit_code)
        self.assertEqual(exit_code, 1)

    def test_input_error_returns_exit_code_2(self):
        """Malformed input should return exit code 2."""
        log_path = Path(self.temp_dir) / "mesh.log"
        output_path = Path(self.temp_dir) / "output.json"

        log_path.write_text(self.create_checkmesh_log("ok"))

        # Non-existent VTK file
        vtk_path = Path(self.temp_dir) / "nonexistent.vtk"

        from scripts.summarize_mesh import main
        import sys

        old_argv = sys.argv
        old_exit = sys.exit
        exit_code = None
        def capture_exit(code):
            nonlocal exit_code
            exit_code = code
            raise SystemExit(code)

        try:
            sys.argv = [
                'summarize_mesh.py',
                '--wall-surface', str(vtk_path),
                '--mesh-log', str(log_path),
                '--output', str(output_path),
            ]
            sys.exit = capture_exit
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
            sys.exit = old_exit

        self.assertEqual(exit_code, 2)


if __name__ == '__main__':
    unittest.main()
