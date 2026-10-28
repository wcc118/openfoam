"""Tests for structure transient viewer generator and validation."""
import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

# Import the generator module
spec = importlib.util.spec_from_file_location(
    'build_struct',
    Path(__file__).resolve().parents[1] / 'scripts/build_structure_transient.py'
)
build_struct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_struct)


def make_valid_data():
    """Create a valid minimal dataset."""
    return {
        'title': 'Test transient',
        'scope': 'aluminum wing',
        'source': 'test',
        'source_sha256': {'file': 'abc123'},
        'mesh': {
            'nodes': [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
            'quads': [[0, 1, 2, 3]],
            'perimeter_nodes': 4
        },
        'modes': [
            [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
            [[0.0, 0.0, 1.0], [0.0, 0.0, -1.0], [0.0, 0.0, 1.0], [0.0, 0.0, -1.0]]
        ],
        'modal_scale': 0.5,
        'cases': [
            {
                'name': 'case1',
                'speed_m_s': 10.0,
                'baseline_force_applied': True,
                'default_deformation_scale': 10.0,
                'note': 'test case',
                'frames': [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.5, 0.5],
                    [0.2, 1.0, 1.0]
                ],
                'peak_vertex_component_m': 0.5,
                'stopped_at_20mm_motion_guard': False
            }
        ]
    }


class BuildStructureTransientTests(unittest.TestCase):
    def test_nonfinite_scalars_rejected_before_packaging(self):
        for field in ('modal_scale', 'speed_m_s', 'default_deformation_scale', 'frame_time'):
            for value in (float('nan'), float('inf')):
                with self.subTest(field=field, value=value):
                    data = make_valid_data()
                    if field == 'modal_scale':
                        data[field] = value
                    elif field == 'frame_time':
                        data['cases'][0]['frames'][1][0] = value
                    else:
                        data['cases'][0][field] = value
                    with self.assertRaises(ValueError):
                        build_struct.validate(data)

    def test_invalid_ring_topology_and_payload_types(self):
        for count in (3, 100):
            data = make_valid_data()
            data['mesh']['perimeter_nodes'] = count
            with self.assertRaises(ValueError):
                build_struct.validate(data)
        with self.assertRaises(ValueError):
            build_struct.validate([])
        data = make_valid_data()
        data['cases'] = [None]
        with self.assertRaises(ValueError):
            build_struct.validate(data)


    def test_valid_data_accepted(self):
        """Valid data should be accepted and HTML generated."""
        data = make_valid_data()
        html = build_struct.build_html(data)
        self.assertIn('<!doctype html>', html)
        self.assertIn('Test transient', html)
        self.assertIn('case1', html)

    def test_empty_title_rejected(self):
        """Empty title should be rejected."""
        data = make_valid_data()
        data['title'] = ''
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_empty_scope_rejected(self):
        """Empty scope should be rejected."""
        data = make_valid_data()
        data['scope'] = ''
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_empty_source_rejected(self):
        """Empty source should be rejected."""
        data = make_valid_data()
        data['source'] = ''
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_empty_source_sha256_rejected(self):
        """Empty source_sha256 should be rejected."""
        data = make_valid_data()
        data['source_sha256'] = {}
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_missing_mesh_rejected(self):
        """Missing mesh should be rejected."""
        data = make_valid_data()
        del data['mesh']
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_empty_nodes_rejected(self):
        """Empty nodes should be rejected."""
        data = make_valid_data()
        data['mesh']['nodes'] = []
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_invalid_node_coordinates_rejected(self):
        """Invalid node coordinates should be rejected."""
        data = make_valid_data()
        data['mesh']['nodes'] = [[float('nan'), 0.0, 0.0]]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_empty_quads_rejected(self):
        """Empty quads should be rejected."""
        data = make_valid_data()
        data['mesh']['quads'] = []
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_invalid_quad_indices_rejected(self):
        """Quad indices out of range should be rejected."""
        data = make_valid_data()
        data['mesh']['quads'] = [[0, 1, 2, 100]]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_missing_perimeter_nodes_rejected(self):
        """Missing perimeter_nodes should be rejected."""
        data = make_valid_data()
        del data['mesh']['perimeter_nodes']
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_invalid_perimeter_nodes_rejected(self):
        """Invalid perimeter_nodes should be rejected."""
        data = make_valid_data()
        data['mesh']['perimeter_nodes'] = -1
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_empty_modes_rejected(self):
        """Empty modes should be rejected."""
        data = make_valid_data()
        data['modes'] = []
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_mode_node_count_mismatch_rejected(self):
        """Mode with wrong node count should be rejected."""
        data = make_valid_data()
        data['modes'] = [[[0.0, 0.0, 1.0]]]  # only 1 node, but mesh has 4
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_invalid_mode_coordinates_rejected(self):
        """Invalid mode coordinates should be rejected."""
        data = make_valid_data()
        data['modes'] = [[[float('inf'), 0.0, 0.0]] * 4]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_missing_modal_scale_rejected(self):
        """Missing modal_scale should be rejected."""
        data = make_valid_data()
        del data['modal_scale']
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_zero_modal_scale_rejected(self):
        """Zero modal_scale should be rejected."""
        data = make_valid_data()
        data['modal_scale'] = 0
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_empty_cases_rejected(self):
        """Empty cases should be rejected."""
        data = make_valid_data()
        data['cases'] = []
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_missing_case_fields_rejected(self):
        """Missing required case fields should be rejected."""
        data = make_valid_data()
        del data['cases'][0]['name']
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_invalid_case_speed_rejected(self):
        """Invalid case speed should be rejected."""
        data = make_valid_data()
        data['cases'][0]['speed_m_s'] = -1
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_invalid_default_deformation_scale_rejected(self):
        """Invalid default_deformation_scale should be rejected."""
        data = make_valid_data()
        data['cases'][0]['default_deformation_scale'] = 0
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_missing_frames_rejected(self):
        """Missing frames should be rejected."""
        data = make_valid_data()
        del data['cases'][0]['frames']
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_single_frame_rejected(self):
        """Single frame should be rejected (need >= 2)."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [[0.0, 0.0, 0.0]]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_non_strictly_increasing_times_rejected(self):
        """Non-strictly-increasing times should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [0.0, 0.0, 0.0],
            [0.0, 0.5, 0.5],  # same time
            [0.2, 1.0, 1.0]
        ]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_decreasing_times_rejected(self):
        """Decreasing times should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [0.2, 1.0, 1.0],
            [0.1, 0.5, 0.5],
            [0.0, 0.0, 0.0]
        ]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_invalid_time_values_rejected(self):
        """Invalid time values should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [float('nan'), 0.0, 0.0],
            [0.1, 0.5, 0.5]
        ]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_negative_time_rejected(self):
        """Negative time should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [-0.1, 0.0, 0.0],
            [0.1, 0.5, 0.5]
        ]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_q_length_mismatch_rejected(self):
        """Q length mismatch with modes should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [0.0, 0.0],  # only 1 q value, but 2 modes
            [0.1, 0.5, 0.5]
        ]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_invalid_q_values_rejected(self):
        """Invalid q values should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [0.0, float('nan'), 0.0],
            [0.1, 0.5, 0.5]
        ]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_missing_peak_vertex_component_rejected(self):
        """Missing peak_vertex_component_m should be rejected."""
        data = make_valid_data()
        del data['cases'][0]['peak_vertex_component_m']
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_missing_stopped_at_guard_rejected(self):
        """Missing stopped_at_20mm_motion_guard should be rejected."""
        data = make_valid_data()
        del data['cases'][0]['stopped_at_20mm_motion_guard']
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_cli_refuses_overwrite(self):
        """CLI should refuse to overwrite existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / 'input.json'
            output_path = Path(tmpdir) / 'output.html'
            input_path.write_text(json.dumps(make_valid_data()))
            output_path.write_text('existing')  # create existing file
            result = build_struct.main.__wrapped__ if hasattr(build_struct.main, '__wrapped__') else None
            if result is None:
                # Test via subprocess or direct call
                import subprocess
                result = subprocess.run(
                    ['python3', '-m', 'scripts.build_structure_transient', '--data', str(input_path), '--output', str(output_path)],
                    cwd=Path(__file__).resolve().parents[1],
                    capture_output=True,
                    text=True
                )
                self.assertNotEqual(result.returncode, 0)

    def test_cli_success_output(self):
        """CLI should produce valid output on success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / 'input.json'
            output_path = Path(tmpdir) / 'output.html'
            input_path.write_text(json.dumps(make_valid_data()))
            import subprocess
            result = subprocess.run(
                ['python3', '-m', 'scripts.build_structure_transient', '--data', str(input_path), '--output', str(output_path)],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True
            )
            self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")
            self.assertTrue(output_path.exists())
            html = output_path.read_text()
            self.assertIn('<!doctype html>', html)

    def test_modal_scale_zero_rejected(self):
        """Zero modal_scale should be rejected."""
        data = make_valid_data()
        data['modal_scale'] = 0
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_modal_scale_negative_rejected(self):
        """Negative modal_scale should be rejected."""
        data = make_valid_data()
        data['modal_scale'] = -1
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_true_boolean_as_speed_rejected(self):
        """Boolean true as speed should be rejected."""
        data = make_valid_data()
        data['cases'][0]['speed_m_s'] = True
        with self.assertRaises(ValueError):
            build_struct.build_html(data)

    def test_nonfinite_frames_time_rejected(self):
        """Nonfinite frame time should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [float('inf'), 0.0, 0.0],
            [0.1, 0.5, 0.5]
        ]
        with self.assertRaises(ValueError):
            build_struct.build_html(data)


if __name__ == '__main__':
    unittest.main()
