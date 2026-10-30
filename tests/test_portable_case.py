import copy
"""Portable case validation and execution tests."""
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


def load_test_case():
    """Load the test fixture and return (case_dict, sha256)."""
    fixture_path = Path(__file__).resolve().parent / 'fixtures' / 'portable_case' / 'free_decay.json'
    with open(fixture_path, 'rb') as f:
        fixture_bytes = f.read()
    fixture_text = fixture_bytes.decode('utf-8')
    case = json.loads(fixture_text)
    sha256 = hashlib.sha256(fixture_bytes).hexdigest()
    return case, sha256


class PortableCaseValidationTests(unittest.TestCase):
    """Tests for portable_case.py validation."""

    @classmethod
    def setUpClass(cls):
        """Load the portable_case module once for all tests."""
        cls.scripts_dir = Path(__file__).resolve().parents[1] / 'scripts'

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'portable_case', cls.scripts_dir / 'portable_case.py'
        )
        cls.pc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.pc)

        # Load the fixture
        cls.fixture, cls.fixture_sha256 = load_test_case()

    def test_validate_case_valid_fixture(self):
        """Test that the valid fixture passes validation."""
        case = copy.deepcopy(self.fixture)

        is_valid, error = self.pc.validate_case(case)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_validate_case_wrong_schema_version(self):
        """Test rejection of wrong schema version."""
        case = copy.deepcopy(self.fixture)
        case['schema_version'] = 2

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("schema_version", error)

    def test_validate_case_wrong_profile(self):
        """Test rejection of wrong profile."""
        case = copy.deepcopy(self.fixture)
        case['profile'] = 'wrong_profile'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("profile", error)

    def test_validate_case_missing_case_id(self):
        """Test rejection of missing case_id."""
        case = copy.deepcopy(self.fixture)
        del case['case_id']

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("case_id", error)

    def test_validate_case_empty_case_id(self):
        """Test rejection of empty case_id."""
        case = copy.deepcopy(self.fixture)
        case['case_id'] = ""

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("case_id", error)

    def test_validate_case_wrong_axes(self):
        """Test rejection of wrong axes."""
        case = copy.deepcopy(self.fixture)
        case['configuration']['axes'] = ['x_wrong', 'y_wrong', 'z_wrong']

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("axes", error)

    def test_validate_case_wrong_handedness(self):
        """Test rejection of wrong handedness."""
        case = copy.deepcopy(self.fixture)
        case['configuration']['axes'] = ['x_downstream', 'y_spanwise', 'z_up']
        case['configuration']['handedness'] = 'left'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("handedness", error)

    def test_validate_case_wrong_length_unit(self):
        """Test rejection of wrong length unit."""
        case = copy.deepcopy(self.fixture)
        case['configuration']['axes'] = ['x_downstream', 'y_spanwise', 'z_up']
        case['configuration']['length_unit'] = 'cm'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("length_unit", error)

    def test_validate_case_duplicate_node_ids(self):
        """Test rejection of duplicate node IDs."""
        case = copy.deepcopy(self.fixture)
        case['geometry']['node_ids'] = [1, 1]

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("duplicate", error)

    def test_validate_case_wrong_normalization(self):
        """Test rejection of wrong normalization."""
        case = copy.deepcopy(self.fixture)
        case['structure']['axes'] = ['x_downstream', 'y_spanwise', 'z_up']
        case['structure']['normalization'] = 'unit_modal_mass'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("normalization", error)

    def test_validate_case_wrong_damping_kind(self):
        """Test rejection of wrong damping kind."""
        case = copy.deepcopy(self.fixture)
        case['structure']['modes'][0]['damping']['kind'] = 'invalid'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("damping kind", error)

    def test_validate_case_negative_mass(self):
        """Test rejection of negative mass."""
        case = copy.deepcopy(self.fixture)
        case['structure']['modes'][0]['mass_kg'] = -1.0

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("mass_kg", error)

    def test_validate_case_negative_damping(self):
        """Test rejection of negative damping."""
        case = copy.deepcopy(self.fixture)
        case['structure']['modes'][0]['damping']['c_kg_per_s'] = -0.1

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("damping coefficient", error)

    def test_validate_case_frequency_mismatch(self):
        """Test rejection of frequency mismatch."""
        case = copy.deepcopy(self.fixture)
        # m=2, k=18, expected freq = sqrt(18/2)/(2*pi) = 0.477... Hz
        case['structure']['modes'][0]['frequency_hz'] = 1.0

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("frequency", error)

    def test_validate_case_unknown_damping_c_not_null(self):
        """Test rejection of unknown damping with non-null c."""
        case = copy.deepcopy(self.fixture)
        case['structure']['modes'][0]['damping']['kind'] = 'unknown'
        case['structure']['modes'][0]['damping']['c_kg_per_s'] = 0.5

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("unknown", error)

    def test_validate_case_nan_value(self):
        """Test rejection of NaN values."""
        case = copy.deepcopy(self.fixture)
        case['structure']['initial_q_m'][0] = float('nan')

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("finite", error)

    def test_validate_case_bool_value(self):
        """Test rejection of boolean numeric values."""
        case = copy.deepcopy(self.fixture)
        case['structure']['initial_q_m'][0] = True

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("numeric, not boolean", error)

    def test_validate_case_incorrect_node_count(self):
        """Test rejection of incorrect node count in mode shape."""
        case = copy.deepcopy(self.fixture)
        case['structure']['modes'][0]['shape'] = [[0, 0, 0]]  # Only 1 node

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("shape", error)

    def test_validate_case_wrong_time_unit(self):
        """Test rejection of wrong time unit."""
        case = copy.deepcopy(self.fixture)
        case['configuration']['axes'] = ['x_downstream', 'y_spanwise', 'z_up']
        case['configuration']['time_unit'] = 'ms'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("time_unit", error)

    def test_validate_case_wrong_components(self):
        """Test rejection of wrong components."""
        case = copy.deepcopy(self.fixture)
        case['structure']['axes'] = ['x_downstream', 'y_spanwise', 'z_up']
        case['structure']['components'] = ['ux', 'uy']

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("components", error)

    def test_validate_case_wrong_basis_units(self):
        """Test rejection of wrong basis units."""
        case = copy.deepcopy(self.fixture)
        case['structure']['axes'] = ['x_downstream', 'y_spanwise', 'z_up']
        case['structure']['basis_units'] = 'm'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("basis_units", error)

    def test_validate_case_wrong_coordinate_units(self):
        """Test rejection of wrong coordinate units."""
        case = copy.deepcopy(self.fixture)
        case['structure']['axes'] = ['x_downstream', 'y_spanwise', 'z_up']
        case['structure']['coordinate_units'] = 'cm'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("coordinate_units", error)

    def test_validate_case_wrong_force_unit(self):
        """Test rejection of wrong force unit."""
        case = copy.deepcopy(self.fixture)
        case['aerodynamics']['force_unit'] = 'kN'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("force_unit", error)

    def test_validate_case_wrong_quantity(self):
        """Test rejection of wrong quantity."""
        case = copy.deepcopy(self.fixture)
        case['aerodynamics']['quantity'] = 'pressure'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("quantity", error)

    def test_validate_case_wrong_pressure_meaning(self):
        """Test rejection of wrong pressure meaning."""
        case = copy.deepcopy(self.fixture)
        case['aerodynamics']['pressure_meaning'] = 'stagnation'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("pressure_meaning", error)

    def test_validate_case_wrong_time_convention(self):
        """Test rejection of wrong time convention."""
        case = copy.deepcopy(self.fixture)
        case['aerodynamics']['time_convention'] = 'seconds_to_end'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("time_convention", error)

    def test_validate_case_non_strictly_increasing_times(self):
        """Test rejection of non-strictly-increasing times."""
        case = copy.deepcopy(self.fixture)
        case['aerodynamics']['times_s'] = [0.0, 0.1, 0.1, 0.2]

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("strictly increasing", error)

    def test_validate_case_times_not_start_at_zero(self):
        """Test rejection of times not starting at zero."""
        case = copy.deepcopy(self.fixture)
        case['aerodynamics']['times_s'] = [0.01, 0.1, 0.2]

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("start at zero", error)

    def test_validate_case_wrong_source_kind(self):
        """Test rejection of wrong source_kind."""
        case = copy.deepcopy(self.fixture)
        case['aerodynamics']['source_kind'] = 'wrong_kind'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("source_kind", error)

    def test_validate_case_wrong_history_kind(self):
        """Test rejection of wrong history_kind."""
        case = copy.deepcopy(self.fixture)
        case['aerodynamics']['history_kind'] = 'steady'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("history", error)

    def test_validate_case_synth_supplied_aerodynamic_params(self):
        """Synthetic metadata may contain valid flow values per the v1 contract."""
        case = copy.deepcopy(self.fixture)
        case['aerodynamics']['density_kg_m3'] = 1.225
        self.assertEqual(self.pc.validate_case(case), (True, ''))
        case['aerodynamics']['density_kg_m3'] = -1
        self.assertFalse(self.pc.validate_case(case)[0])

    def test_validate_case_solver_export_missing_params(self):
        """Test rejection of missing aerodynamic params for solver_export."""
        case = copy.deepcopy(self.fixture)
        case['aerodynamics']['source_kind'] = 'solver_export'
        case['aerodynamics']['density_kg_m3'] = None

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("density_kg_m3", error)

    def test_validate_case_wrong_reference_shape(self):
        """Test rejection of wrong reference shape."""
        case = copy.deepcopy(self.fixture)
        case['configuration']['axes'] = ['x_downstream', 'y_spanwise', 'z_up']
        case['configuration']['reference_shape'] = 'deflected'

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("reference_shape", error)

    def test_validate_case_missing_provenance_scope(self):
        """Test rejection of missing provenance scope."""
        case = copy.deepcopy(self.fixture)
        del case['provenance']['scope']

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("scope", error)

    def test_validate_case_empty_provenance_scope(self):
        """Test rejection of empty provenance scope."""
        case = copy.deepcopy(self.fixture)
        case['provenance']['scope'] = ""

        is_valid, error = self.pc.validate_case(case)
        self.assertFalse(is_valid)
        self.assertIn("scope", error)


class PortableCaseRunTests(unittest.TestCase):
    """Tests for portable_case.py run_case function."""

    @classmethod
    def setUpClass(cls):
        """Load the portable_case module once for all tests."""
        cls.scripts_dir = Path(__file__).resolve().parents[1] / 'scripts'

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'portable_case', cls.scripts_dir / 'portable_case.py'
        )
        cls.pc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.pc)

        # Load the fixture
        cls.fixture, cls.fixture_sha256 = load_test_case()

    def test_run_case_unknown_damping(self):
        """Test that run_case fails with unknown damping."""
        case = copy.deepcopy(self.fixture)
        case['structure']['modes'][0]['damping']['kind'] = 'unknown'
        case['structure']['modes'][0]['damping']['c_kg_per_s'] = None

        # Validate should pass but run should fail
        is_valid, _ = self.pc.validate_case(case)
        self.assertTrue(is_valid)

        with self.assertRaises(ValueError) as ctx:
            self.pc.run_case(case)
        self.assertIn("unknown", str(ctx.exception))

    def test_run_case_valid_fixture(self):
        """Test that valid fixture runs and produces output."""
        case = copy.deepcopy(self.fixture)

        is_valid, _ = self.pc.validate_case(case)
        self.assertTrue(is_valid)

        result = self.pc.run_case(case)

        # Check output structure
        self.assertEqual(result['schema_version'], 1)
        self.assertEqual(result['profile'], 'diagonal_modal_point_forces')
        self.assertEqual(result['case_id'], 'modal-free-decay-reference')
        self.assertEqual(result['input_sha256'], hashlib.sha256(json.dumps(case, sort_keys=True, allow_nan=False).encode()).hexdigest())

        # Check numerical results
        self.assertIn('numerical_results', result)
        nr = result['numerical_results']
        self.assertEqual(nr['time_samples'], 321)
        self.assertIn('time_history', nr)
        th = nr['time_history']

        # Check time history arrays
        self.assertIn('times_s', th)
        self.assertIn('modal_displacements_m', th)
        self.assertIn('modal_velocities_m_per_s', th)
        self.assertIn('modal_accelerations_m_per_s2', th)
        self.assertIn('generalized_forces_N', th)
        self.assertIn('physical_node_displacements_m', th)
        self.assertIn('mean_tip_displacement_m', th)

        # Check time array starts at 0
        self.assertEqual(th['times_s'][0], 0.0)

        # Check that we have the expected number of samples
        self.assertEqual(len(th['times_s']), nr['time_samples'])
        self.assertEqual(len(th['modal_displacements_m']), nr['time_samples'])

    def test_run_case_initial_conditions(self):
        """Test that initial conditions are preserved."""
        case = copy.deepcopy(self.fixture)

        result = self.pc.run_case(case)
        th = result['numerical_results']['time_history']

        # First sample should match initial conditions
        self.assertAlmostEqual(th['modal_displacements_m'][0][0], 0.7, places=10)
        self.assertAlmostEqual(th['modal_velocities_m_per_s'][0][0], -0.4, places=10)

    def test_run_case_frequency(self):
        """Test that the frequency is correct for the free-decay case."""
        case = copy.deepcopy(self.fixture)

        result = self.pc.run_case(case)
        nr = result['numerical_results']
        th = nr['time_history']

        # Time step from fixture
        dt = nr['time_steps_s'][0]
        self.assertAlmostEqual(dt, 0.00228125, places=10)

        # Check that we have 321 samples (T=0.73s, dt=0.00228125 => 320 steps + 1)
        self.assertEqual(len(th['times_s']), 321)


class PortableCaseScalingTests(unittest.TestCase):
    """Tests for mode scaling invariance."""

    @classmethod
    def setUpClass(cls):
        """Load the portable_case module once for all tests."""
        cls.scripts_dir = Path(__file__).resolve().parents[1] / 'scripts'

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'portable_case', cls.scripts_dir / 'portable_case.py'
        )
        cls.pc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.pc)

        # Load the fixture
        cls.fixture, cls.fixture_sha256 = load_test_case()

    def test_negative_mode_scaling_invariance(self):
        """Test that negative mode scaling preserves motion and work."""
        case = copy.deepcopy(self.fixture)

        # Scale mode by -2
        scale = -2.0
        case['structure']['modes'][0]['shape'] = [
            [scale * x, scale * y, scale * z]
            for node in case['structure']['modes'][0]['shape']
            for x, y, z in [node]
        ]
        case['structure']['modes'][0]['mass_kg'] *= scale * scale
        case['structure']['modes'][0]['stiffness_N_per_m'] *= scale * scale
        case['structure']['modes'][0]['damping']['c_kg_per_s'] *= scale * scale
        case['structure']['initial_q_m'][0] /= scale
        case['structure']['initial_v_m_per_s'][0] /= scale

        is_valid, _ = self.pc.validate_case(case)
        self.assertTrue(is_valid)

        result = self.pc.run_case(case)
        th = result['numerical_results']['time_history']

        # Check that physical displacements match original
        original_case = copy.deepcopy(self.fixture)
        original_result = self.pc.run_case(original_case)
        original_th = original_result['numerical_results']['time_history']

        # Physical displacements should be the same
        for t_idx in range(len(th['times_s'])):
            for node_idx in range(len(th['physical_node_displacements_m'][t_idx])):
                for coord_idx in range(3):
                    self.assertAlmostEqual(
                        th['physical_node_displacements_m'][t_idx][node_idx][coord_idx],
                        original_th['physical_node_displacements_m'][t_idx][node_idx][coord_idx],
                        places=10
                    )


class PortableCaseCLITests(unittest.TestCase):
    """Tests for portable_case.py CLI."""

    @classmethod
    def setUpClass(cls):
        """Load the portable_case module once for all tests."""
        cls.project_dir = Path(__file__).resolve().parents[1]

        # Load the fixture
        cls.fixture, cls.fixture_sha256 = load_test_case()

    def test_cli_help(self):
        """Test that CLI help works."""
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.portable_case', '--help'],
            capture_output=True,
            text=True,
            cwd=self.project_dir
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('INPUT', result.stdout)
        self.assertIn('--output', result.stdout)

    def test_cli_invalid_input(self):
        """Test that CLI handles invalid input file."""
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": "json"}')
            f.flush()
            invalid_file = f.name

        output_file = tempfile.mktemp(suffix='.json')

        try:
            result = subprocess.run(
                [sys.executable, '-m', 'scripts.portable_case', invalid_file, '--output', output_file],
                capture_output=True,
                text=True,
                cwd=self.project_dir
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Error', result.stderr)
        finally:
            os.unlink(invalid_file)
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_cli_valid_run(self):
        """Test that CLI runs successfully on valid fixture."""
        import subprocess
        import tempfile

        fixture_path = Path(__file__).resolve().parent / 'fixtures' / 'portable_case' / 'free_decay.json'
        output_file = tempfile.mktemp(suffix='.json')

        try:
            result = subprocess.run(
                [sys.executable, '-m', 'scripts.portable_case', str(fixture_path), '--output', output_file],
                capture_output=True,
                text=True,
                cwd=self.project_dir
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn('Output written', result.stdout)
            self.assertIn('Input SHA256', result.stdout)

            # Check output file exists and is valid JSON
            self.assertTrue(os.path.exists(output_file))
            with open(output_file, 'r') as f:
                output = json.load(f)

            self.assertEqual(output['case_id'], 'modal-free-decay-reference')
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_cli_output_hash_consistency(self):
        """Test that output contains correct input hash."""
        import subprocess
        import tempfile

        fixture_path = Path(__file__).resolve().parent / 'fixtures' / 'portable_case' / 'free_decay.json'
        output_file = tempfile.mktemp(suffix='.json')

        try:
            result = subprocess.run(
                [sys.executable, '-m', 'scripts.portable_case', str(fixture_path), '--output', output_file],
                capture_output=True,
                text=True,
                cwd=self.project_dir
            )
            self.assertEqual(result.returncode, 0)

            # Check output file contains correct hash
            with open(output_file, 'r') as f:
                output = json.load(f)

            self.assertEqual(output['input_sha256'], self.fixture_sha256)
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_cli_clean_copy(self):
        """A minimal copy outside this checkout produces an identical report."""
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copied = root / 'copy'
            (copied / 'scripts').mkdir(parents=True)
            for name in ('portable_case.py', 'modal_dynamics.py', 'modal_surface.py'):
                shutil.copy(self.project_dir / 'scripts' / name, copied / 'scripts' / name)
            fixture = self.project_dir / 'tests/fixtures/portable_case/free_decay.json'
            shutil.copy(fixture, copied / 'case.json')
            reports = []
            for i, (cwd, source) in enumerate(((self.project_dir, fixture), (copied, 'case.json'))):
                output = root / f'report-{i}.json'
                command = [sys.executable, '-m', 'scripts.portable_case', str(source), '--output', str(output)]
                result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                reports.append(json.loads(output.read_text()))
            self.assertEqual(*reports)


class PortablePhysicsTests(unittest.TestCase):
    def setUp(self):
        from scripts import portable_case
        self.pc = portable_case
        self.case, _ = load_test_case()

    def test_analytic_free_and_constant_force_histories(self):
        import numpy as np
        for force in (0., 3.5):
            with self.subTest(force=force):
                case = copy.deepcopy(self.case)
                for sample in case['aerodynamics']['forces_N']:
                    sample[1][2] = force
                result = self.pc.run_case(case)['numerical_results']
                history = result['time_history']
                t = np.array(history['times_s'])
                # Independent closed-form damped oscillator about F/K equilibrium.
                alpha = .8 / (2 * 2)
                omega = math.sqrt(18 / 2 - alpha**2)
                offset = force / 18
                A = .7 - offset
                B = (-.4 + alpha * A) / omega
                exact = offset + np.exp(-alpha*t) * (A*np.cos(omega*t) + B*np.sin(omega*t))
                actual = np.array(history['mean_tip_displacement_m'])[:, 2]
                self.assertLess(float(np.max(np.abs(actual-exact))), 5e-5)
                self.assertAlmostEqual(history['modal_accelerations_m_per_s2'][0][0], (force - .8*(-.4) - 18*.7)/2)
                self.assertAlmostEqual(result['physical_work_j'], force*(actual[-1]-actual[0]), places=12)
                q = np.array(history['modal_displacements_m'])[:, 0]
                v = np.array(history['modal_velocities_m_per_s'])[:, 0]
                energy = v*v + 9*q*q
                self.assertAlmostEqual(energy[-1]-energy[0], result['physical_work_j']-result['damping_loss_j'], places=10)

    def test_nonuniform_ramp_force_rigid_mode(self):
        import numpy as np
        c = self.case
        mode = c['structure']['modes'][0]
        mode.update(stiffness_N_per_m=0., frequency_hz=0.)
        mode['damping']['c_kg_per_s'] = 0.
        c['structure']['initial_q_m'] = [0.]
        c['structure']['initial_v_m_per_s'] = [0.]
        times = [0., .01, .025, .031, .05]
        c['aerodynamics']['times_s'] = times
        c['aerodynamics']['forces_N'] = [[[0., 0., 0.], [0., 0., 2+4*t]] for t in times]
        h = self.pc.run_case(c)['numerical_results']['time_history']
        # a=1+2t; trapezoidal velocity is exact for this linear acceleration.
        np.testing.assert_allclose(np.array(h['modal_accelerations_m_per_s2'])[:, 0], 1+2*np.array(times), atol=1e-14)
        np.testing.assert_allclose(np.array(h['modal_velocities_m_per_s'])[:, 0], np.array(times)+np.array(times)**2, atol=1e-14)

    def test_two_mode_work_and_signed_rescaling(self):
        import numpy as np
        c = self.case
        first = c['structure']['modes'][0]
        first['shape'] = [[.3, -.2, .7], [1.2, .4, -2.]]
        second = copy.deepcopy(first)
        second.update(id='second', shape=[[1., .2, -.6], [-.3, 2., .9]], mass_kg=3., stiffness_N_per_m=48., frequency_hz=4/(2*math.pi))
        second['damping']['c_kg_per_s'] = .6
        c['structure']['modes'].append(second)
        c['structure']['initial_q_m'].append(-.2)
        c['structure']['initial_v_m_per_s'].append(.3)
        c['aerodynamics']['forces_N'] = [[[1+t, -2., 3.], [-.5, t, 2-t]] for t in c['aerodynamics']['times_s']]
        scaled = copy.deepcopy(c)
        for i, scale in enumerate((-2., .4)):
            m = scaled['structure']['modes'][i]
            m['shape'] = (np.array(m['shape'])*scale).tolist()
            for field in ('mass_kg', 'stiffness_N_per_m'):
                m[field] *= scale**2
            m['damping']['c_kg_per_s'] *= scale**2
            for field in ('initial_q_m', 'initial_v_m_per_s'):
                scaled['structure'][field][i] /= scale
        a, b = [self.pc.run_case(x)['numerical_results'] for x in (c, scaled)]
        np.testing.assert_allclose(a['time_history']['physical_node_displacements_m'], b['time_history']['physical_node_displacements_m'], rtol=1e-12, atol=1e-12)
        for result in (a, b):
            self.assertAlmostEqual(result['total_modal_work_j'], result['physical_work_j'], places=11)
            self.assertGreater(abs(result['physical_work_j']), .01)
            h = result['time_history']
            physical = np.sum(.5*(np.array(c['aerodynamics']['forces_N'])[1:]+np.array(c['aerodynamics']['forces_N'])[:-1])*np.diff(h['physical_node_displacements_m'], axis=0))
            self.assertAlmostEqual(result['physical_work_j'], physical, places=12)
        for key in ('modal_work_j', 'physical_work_j', 'damping_loss_j'):
            np.testing.assert_allclose(a[key], b[key], rtol=1e-12, atol=1e-12)

    def test_steady_metadata_cannot_execute(self):
        c = self.case
        c['aerodynamics'].update(history_kind='steady', times_s=[0.], forces_N=[c['aerodynamics']['forces_N'][0]])
        self.assertEqual(self.pc.validate_case(c), (True, ''))
        with self.assertRaisesRegex(ValueError, 'steady'):
            self.pc.run_case(c)

    def test_api_validates_and_rejects_bool_and_duplicate_modes(self):
        for mutate in (lambda c: c.update(schema_version=True),
                       lambda c: c['aerodynamics']['times_s'].__setitem__(0, False),
                       lambda c: c['structure']['modes'].append(copy.deepcopy(c['structure']['modes'][0])),
                       lambda c: c['configuration'].update(support_conditions=''),
                       lambda c: c['aerodynamics'].update(load_reference='moving')):
            c = copy.deepcopy(self.case)
            mutate(c)
            self.assertFalse(self.pc.validate_case(c)[0])
            with self.assertRaises(ValueError):
                self.pc.run_case(c)

    def test_measurement_metadata_roundtrip_and_rejections(self):
        channel = dict(id='tip', position_m=[0,1,0], direction=[0,0,1], quantity='acceleration', unit='m/s^2',
                       excitation=dict(known=False, description='not supplied'),
                       sample_axis=dict(kind='frequency_hz', values=[]), phase_convention=None,
                       uncertainty=dict(status='unknown', description='not supplied'),
                       provenance=dict(source='synthetic metadata test; no measurements', sha256=None))
        measurement = dict(id='test', configuration_id=self.case['configuration']['id'], kind='modal',
                           environment='ground', role='validation', data_status='metadata_only', channels=[channel])
        self.case['measurements'] = [measurement]
        self.assertEqual(self.pc.validate_case(self.case), (True, ''))
        self.assertEqual(self.pc.run_case(self.case)['measurements'], [measurement])
        for field, bad in (('direction', [0,0,2]), ('position_m', [[0],1,0]), ('unit', 'g'),
                           ('sample_axis', dict(kind='time_s', values=[False,1])),
                           ('provenance', dict(source='x', sha256='z'*64)),
                           ('provenance', dict(source='x', sha256='+'+'1'*63))):
            c = copy.deepcopy(self.case)
            c['measurements'][0]['channels'][0][field] = bad
            self.assertFalse(self.pc.validate_case(c)[0], field)
        for target in ('measurements', 'channels'):
            c = copy.deepcopy(self.case)
            items = c['measurements'] if target == 'measurements' else c['measurements'][0]['channels']
            items.append(copy.deepcopy(items[0]))
            self.assertFalse(self.pc.validate_case(c)[0])
        self.case['structure']['initial_q_m'] = [[.7]]
        self.assertFalse(self.pc.validate_case(self.case)[0])

    def test_bool_node_ids_cannot_alias_integer_nodes(self):
        for section in ('geometry', 'structure', 'aerodynamics'):
            c = copy.deepcopy(self.case)
            c[section]['node_ids'][0] = True
            self.assertFalse(self.pc.validate_case(c)[0], section)


if __name__ == '__main__':
    unittest.main()
