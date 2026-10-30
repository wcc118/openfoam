"""Tests for equilibrium comparison viewer generator and validation."""
import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

# Import the generator module
spec = importlib.util.spec_from_file_location(
    'build_eq',
    Path(__file__).resolve().parents[1] / 'scripts/build_equilibrium_comparison.py'
)
build_eq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_eq)


def make_valid_data():
    """Create a valid minimal dataset with miniature mesh."""
    # 8-node miniature mesh (2 quads per side, 4 nodes per ring)
    nodes = [
        [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0],  # bottom ring
        [0.0, 0.0, 0.5], [1.0, 0.0, 0.5], [1.0, 1.0, 0.5], [0.0, 1.0, 0.5]   # top ring
    ]
    quads = [
        [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7],  # side quads
        [0, 3, 2, 1], [4, 5, 6, 7]  # bottom and top quads
    ]
    n_modes = 3

    # Create modes (node displacements)
    modes_baseline = []
    for m in range(n_modes):
        mode = []
        for p in nodes:
            mode.append([0.0, 0.0, 0.0])
            mode[-1][2] = p[0] * m * 0.1  # bending mode
        modes_baseline.append(mode)

    modes_thicker = []
    for m in range(n_modes):
        mode = []
        for p in nodes:
            mode.append([0.0, 0.0, 0.0])
            mode[-1][2] = p[0] * m * 0.08  # slightly less deflection for thicker
        modes_thicker.append(mode)

    return {
        'title': 'Test equilibrium comparison',
        'scope': 'aluminum wing equilibrium',
        'source': 'test data',
        'mesh': {
            'nodes': nodes,
            'quads': quads
        },
        'models': {
            'baseline': {
                'modes': modes_baseline,
                'mass_kg': 10.0,
                'thickness_m': 0.00127
            },
            'thicker': {
                'modes': modes_thicker,
                'mass_kg': 12.0,
                'thickness_m': 0.001524
            }
        },
        'cases': [
            {
                'name': 'baseline frozen-load',
                'model': 'baseline',
                'reference_q': [0.0, 0.0, 0.0],
                'frames': [
                    [0.0, 0.0, 0.0, 0.0],
                    [0.1, 0.5, 0.3, 0.2],
                    [0.2, 1.0, 0.6, 0.4]
                ],
                'note': 'Frozen-load experiment: aerodynamic load held fixed.',
                'stopped_at_50mm_guard': False
            },
            {
                'name': 'baseline loaded-perturbation',
                'model': 'baseline',
                'reference_q': [0.1, 0.05, 0.02],
                'frames': [
                    [0.0, 0.1, 0.05, 0.02],
                    [0.1, 0.6, 0.35, 0.22],
                    [0.2, 1.1, 0.65, 0.42]
                ],
                'note': 'Loaded perturbation: aero feedback about clamped loaded equilibrium.',
                'stopped_at_50mm_guard': False
            },
            {
                'name': 'thicker frozen-load',
                'model': 'thicker',
                'reference_q': [0.0, 0.0, 0.0],
                'frames': [
                    [0.0, 0.0, 0.0, 0.0],
                    [0.1, 0.4, 0.25, 0.15],
                    [0.2, 0.8, 0.5, 0.3]
                ],
                'note': 'Thicker skin frozen-load comparison.',
                'stopped_at_50mm_guard': False
            }
        ]
    }


class EquilibriumComparisonTests(unittest.TestCase):
    def test_valid_data_accepted(self):
        """Valid data should be accepted and HTML generated."""
        data = make_valid_data()
        html = build_eq.build_html(data)
        self.assertIn('<!doctype html>', html)
        self.assertIn('Test equilibrium comparison', html)
        self.assertIn('baseline frozen-load', html)

    def test_nonfinite_modes_rejected(self):
        """Nonfinite mode coordinates should be rejected."""
        data = make_valid_data()
        data['models']['baseline']['modes'][0][0][0] = float('nan')
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_nonfinite_reference_q_rejected(self):
        """Nonfinite reference_q values should be rejected."""
        data = make_valid_data()
        data['cases'][0]['reference_q'][0] = float('inf')
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_nonfinite_frames_q_rejected(self):
        """Nonfinite frame q values should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'][1][1] = float('nan')
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_empty_title_rejected(self):
        """Empty title should be rejected."""
        data = make_valid_data()
        data['title'] = ''
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_empty_scope_rejected(self):
        """Empty scope should be rejected."""
        data = make_valid_data()
        data['scope'] = ''
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_empty_source_rejected(self):
        """Empty source should be rejected."""
        data = make_valid_data()
        data['source'] = ''
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_missing_mesh_rejected(self):
        """Missing mesh should be rejected."""
        data = make_valid_data()
        del data['mesh']
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_empty_nodes_rejected(self):
        """Empty nodes should be rejected."""
        data = make_valid_data()
        data['mesh']['nodes'] = []
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_empty_quads_rejected(self):
        """Empty quads should be rejected."""
        data = make_valid_data()
        data['mesh']['quads'] = []
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_invalid_quad_indices_rejected(self):
        """Quad indices out of range should be rejected."""
        data = make_valid_data()
        data['mesh']['quads'] = [[0, 1, 2, 100]]
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_missing_models_rejected(self):
        """Missing models should be rejected."""
        data = make_valid_data()
        del data['models']
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_missing_model_keys_rejected(self):
        """A case referencing a missing model must be rejected."""
        data = make_valid_data()
        del data['models']['baseline']
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_missing_model_fields_rejected(self):
        """Missing model fields should be rejected."""
        data = make_valid_data()
        del data['models']['baseline']['mass_kg']
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_zero_mass_rejected(self):
        """Zero mass_kg should be rejected."""
        data = make_valid_data()
        data['models']['baseline']['mass_kg'] = 0
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_zero_thickness_rejected(self):
        """Zero thickness_m should be rejected."""
        data = make_valid_data()
        data['models']['baseline']['thickness_m'] = 0
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_empty_cases_rejected(self):
        """Empty cases should be rejected."""
        data = make_valid_data()
        data['cases'] = []
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_missing_case_fields_rejected(self):
        """Missing required case fields should be rejected."""
        data = make_valid_data()
        del data['cases'][0]['name']
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_invalid_model_reference_rejected(self):
        """Invalid model reference should be rejected."""
        data = make_valid_data()
        data['cases'][0]['model'] = 'invalid'
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_missing_reference_q_rejected(self):
        """Missing reference_q should be rejected."""
        data = make_valid_data()
        del data['cases'][0]['reference_q']
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_reference_q_length_mismatch_rejected(self):
        """Reference q length mismatch should be rejected."""
        data = make_valid_data()
        data['cases'][0]['reference_q'] = [0.0, 0.0]  # only 2, but 3 modes
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_invalid_reference_q_values_rejected(self):
        """Invalid reference q values should be rejected."""
        data = make_valid_data()
        data['cases'][0]['reference_q'][0] = float('nan')
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_missing_frames_rejected(self):
        """Missing frames should be rejected."""
        data = make_valid_data()
        del data['cases'][0]['frames']
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_single_frame_rejected(self):
        """Single frame should be rejected (need >= 2)."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [[0.0, 0.0, 0.0, 0.0]]
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_non_strictly_increasing_times_rejected(self):
        """Non-strictly-increasing times should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 0.5, 0.5, 0.5],  # same time
            [0.2, 1.0, 1.0, 1.0]
        ]
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_decreasing_times_rejected(self):
        """Decreasing times should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [0.2, 1.0, 1.0, 1.0],
            [0.1, 0.5, 0.5, 0.5],
            [0.0, 0.0, 0.0, 0.0]
        ]
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_invalid_time_values_rejected(self):
        """Invalid time values should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [float('nan'), 0.0, 0.0, 0.0],
            [0.1, 0.5, 0.5, 0.5]
        ]
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_negative_time_rejected(self):
        """Negative time should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [-0.1, 0.0, 0.0, 0.0],
            [0.1, 0.5, 0.5, 0.5]
        ]
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_q_length_mismatch_rejected(self):
        """Q length mismatch with modes should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'] = [
            [0.0, 0.0, 0.0],  # only 2 q values, but 3 modes
            [0.1, 0.5, 0.5, 0.5]
        ]
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_invalid_q_values_rejected(self):
        """Invalid q values should be rejected."""
        data = make_valid_data()
        data['cases'][0]['frames'][1][1] = float('inf')
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_invalid_stopped_at_guard_rejected(self):
        """Invalid stopped_at_50mm_guard should be rejected."""
        data = make_valid_data()
        data['cases'][0]['stopped_at_50mm_guard'] = 'yes'
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_missing_stopped_at_guard_rejected(self):
        """Missing stopped_at_50mm_guard should be rejected."""
        data = make_valid_data()
        del data['cases'][0]['stopped_at_50mm_guard']
        with self.assertRaises(ValueError):
            build_eq.build_html(data)

    def test_cli_refuses_overwrite(self):
        """CLI should refuse to overwrite existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / 'input.json'
            output_path = Path(tmpdir) / 'output.html'
            input_path.write_text(json.dumps(make_valid_data()))
            output_path.write_text('existing')
            result = build_eq.main.__wrapped__ if hasattr(build_eq.main, '__wrapped__') else None
            if result is None:
                import subprocess
                result = subprocess.run(
                    ['python3', '-m', 'scripts.build_equilibrium_comparison', '--data', str(input_path), '--output', str(output_path)],
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
                ['python3', '-m', 'scripts.build_equilibrium_comparison', '--data', str(input_path), '--output', str(output_path)],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True
            )
            self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")
            self.assertTrue(output_path.exists())
            html = output_path.read_text()
            self.assertIn('<!doctype html>', html)

    def test_referenced_models_required(self):
        """Both models referenced by these cases must be present."""
        data = make_valid_data()
        data['models'] = {'baseline': data['models']['baseline']}
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_empty_note_accepted(self):
        """Empty note should be accepted (optional)."""
        data = make_valid_data()
        data['cases'][0]['note'] = ''
        html = build_eq.build_html(data)
        self.assertIn('<!doctype html>', html)

    def test_null_note_accepted(self):
        """Null note should be accepted (optional)."""
        data = make_valid_data()
        data['cases'][0]['note'] = None
        html = build_eq.build_html(data)
        self.assertIn('<!doctype html>', html)

    def test_model_modes_count_mismatch_accepted(self):
        """Baseline and thicker can have different mode counts."""
        data = make_valid_data()
        # Remove one mode from thicker
        data['models']['thicker']['modes'] = data['models']['thicker']['modes'][:2]
        # Update frames to match
        for c in data['cases']:
            if c['model'] == 'thicker':
                for f in c['frames']:
                    f.pop()  # remove last q value
        # Update thicker case to have 2 modes
        data['cases'][2]['reference_q'] = [0.0, 0.0]
        data['cases'][2]['frames'] = [
            [0.0, 0.0, 0.0],
            [0.1, 0.4, 0.25],
            [0.2, 0.8, 0.5]
        ]
        html = build_eq.build_html(data)
        self.assertIn('<!doctype html>', html)

    def test_description_only_model_accepted(self):
        """Description-only model without numeric metadata should be accepted."""
        data = make_valid_data()
        data['models']['baseline'] = {
            'modes': data['models']['baseline']['modes'],
            'description': 'Benchmark wind tunnel measurement at Re=500k'
        }
        # Also update thicker to be description-only to avoid mm skin entirely
        data['models']['thicker'] = {
            'modes': data['models']['thicker']['modes'],
            'description': 'CFD reference case'
        }
        data['cases'][0]['model'] = 'baseline'
        data['cases'][1]['model'] = 'baseline'
        data['cases'][2]['model'] = 'thicker'
        html = build_eq.build_html(data)
        self.assertIn('Benchmark wind tunnel measurement at Re=500k', html)
        self.assertIn('CFD reference case', html)
        # The viewer.js renders description when present, not physical values
        # Verify the description appears in the info text
        # Check that model.thickness_m and model.mass_kg are not used in info string
        self.assertIn("model.description", html)

    def test_description_with_physical_metadata_accepted(self):
        """Model with both description and physical metadata should be accepted."""
        data = make_valid_data()
        data['models']['baseline']['description'] = 'Experimental reference case'
        html = build_eq.build_html(data)
        self.assertIn('Experimental reference case', html)
        self.assertIn('mm skin', html)

    def test_empty_description_rejected(self):
        """Empty string description should be rejected."""
        data = make_valid_data()
        data['models']['baseline']['description'] = ''
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_whitespace_only_description_rejected(self):
        """Whitespace-only description should be rejected."""
        data = make_valid_data()
        data['models']['baseline']['description'] = '   '
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_missing_both_description_and_physical_rejected(self):
        """Model missing both description and numeric physical metadata should be rejected."""
        data = make_valid_data()
        del data['models']['baseline']['mass_kg']
        del data['models']['baseline']['thickness_m']
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_only_mass_kg_rejected(self):
        """Model with only mass_kg (without thickness_m) should be rejected."""
        data = make_valid_data()
        data['models']['baseline']['description'] = 'Hypothetical model'
        del data['models']['baseline']['thickness_m']
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_only_thickness_m_rejected(self):
        """Model with only thickness_m (without mass_kg) should be rejected."""
        data = make_valid_data()
        data['models']['baseline']['description'] = 'Hypothetical model'
        del data['models']['baseline']['mass_kg']
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_partial_physical_metadata_rejected_without_description(self):
        """Model with only mass_kg and no description should be rejected."""
        data = make_valid_data()
        del data['models']['baseline']['thickness_m']
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_description_with_html_entities_safe(self):
        """Description with HTML special characters should be safely escaped."""
        data = make_valid_data()
        data['models']['baseline']['description'] = 'Benchmark & comparison <test> "quote"'
        html = build_eq.build_html(data)
        # JSON escaping uses \uXXXX format for special chars in script context
        # The description is embedded in JSON, which uses \u0026 for &, etc.
        self.assertIn('\\u0026', html)  # escaped &
        self.assertIn('\\u003c', html)  # escaped <
        self.assertIn('\\u003e', html)  # escaped >

    def test_description_null_accepted(self):
        """Null description should be accepted (optional field)."""
        data = make_valid_data()
        data['models']['baseline']['description'] = None
        html = build_eq.build_html(data)
        self.assertIn('<!doctype html>', html)
        self.assertIn('mm skin', html)


class TestComparisonBoundaries(unittest.TestCase):
    def test_named_modal_bases_and_single_model(self):
        data = make_valid_data()
        data['models'] = {'modes10': data['models']['baseline']}
        data['cases'] = data['cases'][:2]
        for case in data['cases']:
            case['model'] = 'modes10'
        build_eq.validate(data)
        self.assertIn('modes10', build_eq.build_html(data))

    def test_empty_model_key_rejected(self):
        data = make_valid_data()
        data['models'][''] = data['models'].pop('baseline')
        with self.assertRaises(ValueError):
            build_eq.validate(data)

    def test_nonfinite_material_metadata(self):
        for field in ('mass_kg', 'thickness_m'):
            for value in (float('nan'), float('inf')):
                data = make_valid_data()
                data['models']['baseline'][field] = value
                with self.assertRaises(ValueError):
                    build_eq.validate(data)

    def test_no_common_time_interval(self):
        data = make_valid_data()
        for frame in data['cases'][0]['frames']:
            frame[0] += 1.0
        with self.assertRaisesRegex(ValueError, 'common positive time interval'):
            build_eq.validate(data)

    def test_unequal_end_times_with_overlap(self):
        data = make_valid_data()
        data['cases'][0]['frames'] = data['cases'][0]['frames'][:2]
        build_eq.validate(data)


if __name__ == '__main__':
    unittest.main()
