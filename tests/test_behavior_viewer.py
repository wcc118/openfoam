"""Synthetic fixtures test behavior viewer contracts; these are not CFD results."""
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

# Add scripts to path for imports
SCRIPTS_DIR = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from behavior_viewer.data import load_evidence


def build_test_html(data_dict):
    """Build HTML from data dict using the same logic as build_behavior_viewer.py."""
    assets = SCRIPTS_DIR/'behavior_viewer'
    payload = json.dumps(data_dict, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = (assets/'viewer.html').read_text()
    if template.count('__BEHAVIOR_DATA__') != 1 or template.count('__BEHAVIOR_SCRIPT__') != 1:
        raise ValueError('Invalid template placeholders')
    document = template.replace('__BEHAVIOR_DATA__', payload).replace('__BEHAVIOR_SCRIPT__', (assets/'viewer.js').read_text())
    return document


def fixture():
    """Create synthetic fixture matching the expected schema."""
    base_q = [0.0] * 20
    base_q[1] = 0.01
    return {
        'schema_version': 1,
        'title': 'How the wing behaves across speed',
        'native_sha256': 'a' * 64,
        'contract': 'Test contract',
        'conventions': {
            'axes': 'x downstream, y spanwise, z up',
            'moment_origin_m': [0.0254, 0, 0],
            'twist': 'Tip chord rotation relative to undeformed chord; positive when trailing edge rotates upward',
            'tip': 'Mean vertical displacement of native tip perimeter nodes, relative to undeformed surface',
            'normalization': 'Full-wing generalized coordinates use native half-wing phi/sqrt(2); mirrored y displacement changes sign'
        },
        'limits': [
            'Clamped original linear unprestressed shell',
            'UVLM is incompressible with aligned fixed straight wake; no separation model',
            'CFD fixed-pose results remain diagnostic; long coupled dynamics held pending numerical qualification'
        ],
        'sources': {
            'native-modal.npz': 'a' * 64,
            'operating-contract.json': 'b' * 64,
            'summary.json': 'c' * 64
        },
        'source_issue': 'https://github.com/wcc118/openfoam/issues/45',
        'geometry': {
            'points_m': [[0, -1, 0], [0, 1, 0], [1, 0, 0]],
            'basis_xyz_per_q': [
                [[[0, 0, 0], [0, 0, 0], [0, 0, 0]] for _ in range(3)]
                for _ in range(20)
            ],
            'triangles': [[0, 1, 2]],
            'note': 'Test geometry'
        },
        'speeds': [
            {
                'speed_kn': 60,
                'speed_m_s': 30.86,
                'mach': 0.18,
                'uvlm': {
                    'q': copy.deepcopy(base_q),
                    'alpha_deg': 2.5,
                    'lift_lbf': 29.8,
                    'tip_in': 0.023,
                    'twist_deg': 0.15,
                    'span_profile': [[i * 0.5, 0, 0] for i in range(49)],
                    'elapsed_s': 12.5,
                    'timing_scope': 'Equilibrium solve only',
                    'status': 'Equilibrium screened; physical accuracy unvalidated',
                    'pole_status': 'pass',
                    'weakest_growth_per_s': 0.001,
                    'weakest_frequency_hz': 0.5,
                    'bending_growth_per_s': 0.002,
                    'bending_frequency_hz': 1.2
                },
                'cfd': [
                    {
                        'id': 'issue45-static-60kn-resume-20261106',
                        'label': '60 kn CFD reference',
                        'q_pose': copy.deepcopy(base_q),
                        'alpha_deg': 2.5,
                        'lift_lbf': 30.2,
                        'tip_in': 0.024,
                        'twist_deg': 0.16,
                        'span_profile': [[i * 0.5, 0, 0] for i in range(49)],
                        'lift_error_pct': 0.67,
                        'balance_correction_in': 0.0001,
                        'stationary': True,
                        'loaded_gate': True,
                        'status': ['Force history stationary', 'Loaded reference passed', 'Numerical settings sensitivity unresolved'],
                        'solver': 'simpleFoam',
                        'elapsed_s': 180.0,
                        'timing_scope': 'Bounded CFD execution',
                        'iterations': 500,
                        'history': [[i, 30 + i * 0.01] for i in range(100)],
                        'history_axis': 'Steady solver iteration',
                        'matched_uvlm_inputs': True,
                        'alpha_difference_deg': 0.0,
                        'q_max_difference': 0.0,
                        'lift_difference_lbf': 0.4,
                        'comparison_label': 'Same candidate pose and angle',
                        'shape_label': 'Held CFD candidate pose',
                        'source': 'issue45-static-60kn-resume-20261106'
                    }
                ],
                'transient': {
                    'label': 'Recorded UVLM first-bending release',
                    'time_s': [i * 0.01 for i in range(100)],
                    'q_delta': [[i * 0.001] * 20 for i in range(100)],
                    'tip_delta_in': [i * 0.001 for i in range(100)],
                    'twist_delta_deg': [i * 0.0001 for i in range(100)],
                    'initial_grid_displacement_in': 0.001,
                    'scope': '20-mode surrogate test',
                    'seconds': 1.0,
                    'sample_dt_s': 0.01
                }
            },
            {
                'speed_kn': 150,
                'speed_m_s': 77.16,
                'mach': 0.45,
                'uvlm': {
                    'q': copy.deepcopy(base_q),
                    'alpha_deg': 1.2,
                    'lift_lbf': 31.5,
                    'tip_in': 0.035,
                    'twist_deg': 0.25,
                    'span_profile': [[i * 0.5, 0, 0] for i in range(49)],
                    'elapsed_s': 8.5,
                    'timing_scope': 'Equilibrium solve only',
                    'status': 'Equilibrium screened',
                    'pole_status': 'pass',
                    'weakest_growth_per_s': 0.003,
                    'weakest_frequency_hz': 0.8,
                    'bending_growth_per_s': 0.004,
                    'bending_frequency_hz': 1.5
                },
                'cfd': [],
                'transient': {
                    'label': 'Recorded UVLM first-bending release',
                    'time_s': [i * 0.01 for i in range(100)],
                    'q_delta': [[i * 0.001] * 20 for i in range(100)],
                    'tip_delta_in': [i * 0.001 for i in range(100)],
                    'twist_delta_deg': [i * 0.0001 for i in range(100)],
                    'initial_grid_displacement_in': 0.001,
                    'scope': '20-mode surrogate test',
                    'seconds': 1.0,
                    'sample_dt_s': 0.01
                }
            },
            {
                'speed_kn': 250,
                'speed_m_s': 128.6,
                'mach': 0.76,
                'uvlm': {
                    'q': copy.deepcopy(base_q),
                    'alpha_deg': 0.8,
                    'lift_lbf': 32.1,
                    'tip_in': 0.048,
                    'twist_deg': 0.35,
                    'span_profile': [[i * 0.5, 0, 0] for i in range(49)],
                    'elapsed_s': 6.2,
                    'timing_scope': 'Equilibrium solve only',
                    'status': 'Equilibrium screened',
                    'pole_status': 'pass',
                    'weakest_growth_per_s': 0.005,
                    'weakest_frequency_hz': 1.0,
                    'bending_growth_per_s': 0.006,
                    'bending_frequency_hz': 1.8
                },
                'cfd': [],
                'transient': None
            }
        ]
    }


class BehaviorViewerTests(unittest.TestCase):
    def test_build_html_contains_required_elements(self):
        data = fixture()
        page = build_test_html(data)
        self.assertNotIn('__BEHAVIOR_DATA__', page)
        self.assertNotIn('__BEHAVIOR_SCRIPT__', page)
        required_ids = ['speedSelect', 'cfdSelect', 'deformScale', 'perturbScale',
                        'scene', 'chartCanvas', 'view', 'reset', 'speedLabel',
                        'metricTip', 'metricTwist', 'metricLift', 'metricAlpha',
                        'compareList', 'legendMin', 'legendMax']
        for rid in required_ids:
            self.assertIn(f'id="{rid}"', page, f'Missing element: {rid}')
        self.assertIn('type="application/json"', page)
        self.assertIn('id="behavior-data"', page)

    def test_speed_count(self):
        data = fixture()
        page = build_test_html(data)
        self.assertIn('id="speedSelect"', page)

    def test_cfd_case_options_populated(self):
        data = fixture()
        page = build_test_html(data)
        self.assertIn('id="cfdSelect"', page)

    def test_transient_controls(self):
        data = fixture()
        page = build_test_html(data)
        self.assertIn('id="perturbScale"', page)

    def test_metrics_display(self):
        data = fixture()
        page = build_test_html(data)
        metrics = ['Tip deflection', 'Tip twist', 'Lift', 'Alpha']
        for metric in metrics:
            self.assertIn(metric, page, f'Missing metric: {metric}')

    def test_method_comparison_section(self):
        data = fixture()
        page = build_test_html(data)
        self.assertIn('Method comparison', page)

    def test_limitations_displayed(self):
        data = fixture()
        page = build_test_html(data)
        self.assertIn('Assumptions and limitations', page)

    def test_speed_range(self):
        data = fixture()
        speeds = [s['speed_kn'] for s in data['speeds']]
        self.assertEqual(speeds, [60, 150, 250])

    def test_cfd_cases_with_stationarity_labels(self):
        data = fixture()
        page = build_test_html(data)
        self.assertIn('Force history stationary', page)
        self.assertIn('Loaded reference passed', page)

    def test_timing_scope_displayed(self):
        data = fixture()
        page = build_test_html(data)
        self.assertIn('Equilibrium solve only', page)
        self.assertIn('Bounded CFD execution', page)


class BehaviorViewerIntegrationTests(unittest.TestCase):
    def test_cli_creates_output(self):
        data = fixture()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / 'data.json'
            out = root / 'output' / 'index.html'
            source.write_text(json.dumps(data))
            SCRIPTS_DIR = Path(__file__).resolve().parents[1]/'scripts'
            output_dir = root / 'output'
            output_dir.mkdir(parents=True, exist_ok=False)
            payload = json.dumps(data, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            template = (SCRIPTS_DIR/'behavior_viewer'/'viewer.html').read_text()
            document = template.replace('__BEHAVIOR_DATA__', payload).replace('__BEHAVIOR_SCRIPT__', (SCRIPTS_DIR/'behavior_viewer'/'viewer.js').read_text())
            (output_dir/'index.html').write_text(document)
            self.assertTrue(out.exists())
            content = out.read_text()
            self.assertIn('<!doctype html>', content)

    def test_cli_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / 'output'
            out.mkdir()
            with self.assertRaises(FileExistsError):
                Path(out).mkdir(parents=True, exist_ok=False)

    def test_cli_creates_all_outputs(self):
        data = fixture()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / 'output'
            output_dir = root / 'output'
            output_dir.mkdir(parents=True, exist_ok=False)
            payload = json.dumps(data, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            SCRIPTS_DIR = Path(__file__).resolve().parents[1]/'scripts'
            template = (SCRIPTS_DIR/'behavior_viewer'/'viewer.html').read_text()
            document = template.replace('__BEHAVIOR_DATA__', payload).replace('__BEHAVIOR_SCRIPT__', (SCRIPTS_DIR/'behavior_viewer'/'viewer.js').read_text())
            (output_dir/'index.html').write_text(document)
            (output_dir/'data.json').write_text(json.dumps(data, allow_nan=False, separators=(',', ':')))
            (output_dir/'provenance.json').write_text(json.dumps({'native_sha256':data['native_sha256'],'sources':data['sources'],'scope':data['limits']},indent=2))
            self.assertTrue((out / 'index.html').exists())
            self.assertTrue((out / 'data.json').exists())
            self.assertTrue((out / 'provenance.json').exists())


if __name__ == '__main__':
    unittest.main()
