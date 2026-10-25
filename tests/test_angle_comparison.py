"""Synthetic fixtures test steady-angle comparison viewer contracts; these are not CFD results."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/build_angle_comparison.py'
spec = importlib.util.spec_from_file_location('angle_comparison', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    ref_speed = 30.0
    alpha1, alpha2 = 0.0, 5.0
    return {
        'schema_version': 1,
        'kind': 'steady_angle_cases',
        'reference': {
            'speed_m_s': ref_speed,
            'chord_m': 0.1,
            'reference_pressure_kinematic': 10.0,
            'dynamic_pressure_kinematic': 100.0
        },
        'wing': {
            'points': [[0, -0.5, 0], [0, 0.5, 0], [0.1, 0, 0]],
            'triangles': [[0, 1, 2]]
        },
        'samples': {
            'points': [[0, 0, 0.02], [0.2, 0.6, 0], [0.3, 0, 0]],
            'groups': ['midspan', 'tip', 'wake']
        },
        'cases': [
            {
                'id': 'case_00',
                'alpha_deg': alpha1,
                'steady_iteration': 500,
                'solver': 'fixture',
                'source_revision': 'fixture',
                'mesh_sha256': 'a' * 64,
                'field_sha256': 'b' * 64,
                'status': 'diagnostic_only',
                'limitations': ['Synthetic test, not CFD'],
                'freestream_velocity_m_s': [ref_speed * 1.0, 0, ref_speed * 0.0],
                'U': [[3, 4, 0], [0, 0, 2], [0, 0, 0]],
                'p': [110, -90, 10]
            },
            {
                'id': 'case_05',
                'alpha_deg': alpha2,
                'steady_iteration': 600,
                'solver': 'fixture',
                'source_revision': 'fixture',
                'mesh_sha256': 'a' * 64,
                'field_sha256': 'b' * 64,
                'status': 'diagnostic_only',
                'limitations': ['Synthetic test, not CFD'],
                'freestream_velocity_m_s': [ref_speed * 0.996194698, 0, ref_speed * 0.087155743],
                'U': [[3.5, 4.2, 0.1], [0.1, 0.1, 2.1], [0.1, 0.1, 0.1]],
                'p': [112, -88, 12]
            }
        ]
    }


def expected_freestream(speed_m_s, alpha_deg):
    import math
    alpha_rad = math.radians(alpha_deg)
    return [speed_m_s * math.cos(alpha_rad), 0, speed_m_s * math.sin(alpha_rad)]


class AngleComparisonTests(unittest.TestCase):
    def test_common_ranges_across_multiple_cases(self):
        data = fixture()
        ranges = module.derived_ranges(data)
        # Verify speed and cp ranges span all cases
        # Speeds: case0 [5,0,0]=5, case1 hypot(3.5,4.2,0.1)=~5.47
        self.assertAlmostEqual(ranges['speed'][0], 0.0, places=6)
        self.assertAlmostEqual(ranges['speed'][1], 5.468, places=3)
        # Cp: (110-10)/100=1.0, (-90-10)/100=-1.0, (112-10)/100=1.02, (-88-10)/100=-0.98
        self.assertAlmostEqual(ranges['cp'][0], -1.0, places=6)
        self.assertAlmostEqual(ranges['cp'][1], 1.02, places=3)

    def test_single_case_accepted(self):
        data = fixture()
        data['cases'] = [data['cases'][0]]
        module.validate(data)
        ranges = module.derived_ranges(data)
        # Speeds: case0 [5,0,0]=5
        self.assertEqual(ranges['speed'], [0.0, 5.0])
        # Cp: (110-10)/100=1.0, (-90-10)/100=-1.0
        self.assertEqual(ranges['cp'], [-1.0, 1.0])

    def test_zero_reference_pressure_accepted(self):
        data = fixture()
        data['reference']['reference_pressure_kinematic'] = 0.0
        module.validate(data)
        ranges = module.derived_ranges(data)
        # Cp: (110-0)/100=1.1, (-90-0)/100=-0.9
        self.assertEqual(ranges['cp'], [-0.9, 1.12])

    def test_negative_reference_pressure_accepted(self):
        data = fixture()
        data['reference']['reference_pressure_kinematic'] = -50.0
        module.validate(data)
        ranges = module.derived_ranges(data)
        # Cp: (110-(-50))/100=1.6, (-90-(-50))/100=-0.4
        self.assertEqual(ranges['cp'], [-0.4, 1.62])

    def test_metadata_cannot_end_data_script(self):
        data = fixture()
        bad = '</script><script>window.PWNED=true</script>&\u2028'
        data['cases'][0]['id'] = bad
        page = module.build_html(data)
        self.assertNotIn(bad, page)
        text = re.search(r'<script id="angle-data" type="application/json">(.*?)</script>', page, re.S)[1]
        self.assertNotIn('<', text)
        self.assertEqual(json.loads(text)['cases'][0]['id'], bad)

    def test_invalid_contracts(self):
        mutations = [
            lambda d: d['reference'].update(dynamic_pressure_kinematic=-1),
            lambda d: d['reference'].update(dynamic_pressure_kinematic=0),
            lambda d: d['cases'][0].update(id='   '),
            lambda d: d['cases'][0].update(solver='   '),
            lambda d: d['cases'][0].update(source_revision='   '),
            lambda d: d['cases'][0].update(field_sha256=['a']*64),
            lambda d: d['cases'][0]['freestream_velocity_m_s'].__setitem__(1, float('nan')),
            lambda d: d['cases'][0]['freestream_velocity_m_s'].__setitem__(1, False),
            lambda d: d.update(kind='physical_seconds'),
            lambda d: d['cases'][0].update(steady_iteration=True),
            lambda d: d['cases'][0].update(steady_iteration=-1),
            lambda d: d['cases'][0].update(steady_iteration=0),
            lambda d: d['cases'][0].update(alpha_deg=float('nan')),
            lambda d: d['cases'][0].update(alpha_deg=float('inf')),
            lambda d: d['cases'][0]['U'][0].__setitem__(0, float('inf')),
            lambda d: d['cases'][0]['p'].__setitem__(0, float('nan')),
            lambda d: d['cases'][0].update(U=[[1, 2, 3]]),
            lambda d: d['cases'][0].update(p=[10]),
            lambda d: d['cases'][0].update(mesh_sha256='short'),
            lambda d: d['cases'][0].update(mesh_sha256='x' * 64),
            lambda d: d['cases'][0].update(field_sha256='x' * 64),
            lambda d: d['cases'][0].update(status='computed'),
            lambda d: d['cases'][0].update(limitations=[]),
            lambda d: d['cases'][0].update(limitations=['']),
            lambda d: d['cases'][0].update(freestream_velocity_m_s=[1, 2]),
            lambda d: d['cases'][0].update(freestream_velocity_m_s=[31, 0, 5]),
            lambda d: d['samples']['groups'].pop(),
            lambda d: d.update(cases=[]),
            lambda d: d['cases'].append(copy.deepcopy(d['cases'][0])),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data = fixture()
                mutate(data)
                with self.assertRaises(ValueError):
                    module.validate(data)

    def test_duplicate_id_rejected(self):
        data = fixture()
        data['cases'].append(copy.deepcopy(data['cases'][0]))
        data['cases'][1]['id'] = data['cases'][0]['id']
        with self.assertRaises(ValueError) as ctx:
            module.validate(data)
        self.assertIn('duplicate case.id', str(ctx.exception))

    def test_duplicate_alpha_rejected(self):
        data = fixture()
        data['cases'][1]['alpha_deg'] = data['cases'][0]['alpha_deg']
        with self.assertRaises(ValueError) as ctx:
            module.validate(data)
        self.assertIn('duplicate case.alpha_deg', str(ctx.exception))

    def test_freestream_velocity_mismatch_rejected(self):
        data = fixture()
        data['cases'][0]['freestream_velocity_m_s'] = [31.0, 0, 0]
        with self.assertRaises(ValueError) as ctx:
            module.validate(data)
        self.assertIn('freestream_velocity_m_s', str(ctx.exception))

    def test_mesh_hash_mismatch_rejected(self):
        data = fixture()
        data['cases'][1]['mesh_sha256'] = 'c' * 64
        with self.assertRaises(ValueError) as ctx:
            module.validate(data)
        self.assertIn('same mesh_sha256', str(ctx.exception))

    def test_cli_refuses_overwrite_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / 'data.json'
            out = root / 'viewer.html'
            source.write_text(json.dumps(fixture()))
            out.write_text('preserve')
            cmd = [sys.executable, str(SCRIPT), '--input', str(source), '--output', str(out)]
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertEqual(out.read_text(), 'preserve')
            out.unlink()
            data = fixture()
            data['cases'][0]['p'][0] = float('nan')
            source.write_text(json.dumps(data))
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
