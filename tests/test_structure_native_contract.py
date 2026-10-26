"""Regression checks against independently executed native decks and CLI bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/generate_structure_benchmarks.py'
FIXTURES = ROOT / 'tests/fixtures/structure-native'


def bulk(text):
    return [line.split(',') for line in text.split('BEGIN BULK\n', 1)[1].splitlines()
            if line and line != 'ENDDATA' and not line.startswith('$')]


class NativeContract(unittest.TestCase):
    def run_cli(self, target, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--output-directory', str(target), *args],
                              capture_output=True, text=True)

    def test_default_bulk_semantics_match_native_fixtures_and_file_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out'
            result = self.run_cli(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            ref = json.loads((target / 'reference.json').read_text())
            for generated, fixture in [('bend_static', 'bend'), ('torsion_static', 'torsion'), ('modal_bend', 'modal')]:
                data = (target / (generated + '.bdf')).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), ref['output_files'][generated]['sha256'])
                actual = bulk(data.decode())
                expected = bulk((FIXTURES / (fixture + '.bdf')).read_text())
                self.assertEqual(len(actual), len(expected))
                for a, b in zip(actual, expected):
                    self.assertEqual(a[0], b[0])
                    self.assertEqual(len(a), len(b))
                    for av, bv in zip(a[1:], b[1:]):
                        if not bv:
                            self.assertEqual(av, '')
                        else:
                            self.assertAlmostEqual(float(av), float(bv), delta=max(1e-15, abs(float(bv))*1e-9))
                        self.assertLessEqual(len(av), 16)
                self.assertIn('SPC = 1', data.decode().split('BEGIN BULK')[0])

    def test_custom_parameters_change_geometry_material_and_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out'
            result = self.run_cli(target, '--length', '2', '--element-count', '10',
                                  '--radius', '.004', '--young-modulus', '60000000000',
                                  '--density', '2500.125', '--poisson', '0')
            self.assertEqual(result.returncode, 0, result.stderr)
            ref = json.loads((target / 'reference.json').read_text())
            for name in ['bend_static', 'torsion_static', 'modal_bend']:
                cards = bulk((target / (name + '.bdf')).read_text())
                grids = [c for c in cards if c[0] == 'GRID']
                self.assertEqual(len(grids), 11)
                self.assertEqual(float(grids[-1][3]), 2.)
                mat = next(c for c in cards if c[0] == 'MAT1')
                self.assertEqual(float(mat[2]), 60e9)
                self.assertEqual(float(mat[4]), 0.)
                self.assertIn('.', mat[4])
                self.assertEqual(float(mat[5]), 2500.125)
                self.assertTrue(all(len(v) <= 16 for c in cards for v in c))
            model = ref['model']
            self.assertAlmostEqual(ref['mass']['total_kg'], 2500.125 * model['section']['area_m2'] * 2)
            self.assertAlmostEqual(ref['static_bending']['analytic_delta_m'], 8/(3*60e9*model['section']['I_y_m4']))

    def test_zero_physical_parameters_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            for flag in ['--length', '--radius', '--density', '--young-modulus']:
                target = Path(tmp) / flag[2:]
                result = self.run_cli(target, flag, '0')
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(target.exists())
