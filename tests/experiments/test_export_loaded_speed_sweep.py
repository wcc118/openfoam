"""Tests for loaded speed sweep exporter."""
import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

import numpy as np

# Import the exporter module - use absolute path from checkout root
SCRIPT_PATH = Path(__file__).resolve().parents[1].parent / 'scripts' / 'experiments' / 'export_loaded_speed_sweep.py'
spec = importlib.util.spec_from_file_location('export_speed_sweep', SCRIPT_PATH)
export_speed_sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_speed_sweep)


class TestLoadNative(unittest.TestCase):
    def test_missing_native_file_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with self.assertRaises(FileNotFoundError):
                export_speed_sweep.load_native(base)

    def test_loads_native_data_correctly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            xyz = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
            quads = np.array([[0, 1, 2, 0]])
            phi = np.random.rand(10, 3, 3)
            mass = np.array([1.0, 1.0, 1.0])
            frequencies = np.array([1.0, 2.0, 3.0])
            gen_mass = np.array([1.0, 1.0, 1.0])

            np.savez(base / 'native-modal.npz',
                     xyz=xyz, quads=quads, phi=phi, mass=mass,
                     frequencies_Hz=frequencies, generalized_mass=gen_mass)

            data, sha256 = export_speed_sweep.load_native(base)

            # Verify SHA256 is non-empty and consistent
            self.assertIsNotNone(sha256)
            self.assertEqual(len(sha256), 64)  # SHA256 hex length
            self.assertTrue(np.array_equal(data['xyz'], xyz))
            self.assertTrue(np.array_equal(data['quads'], quads))
            self.assertTrue(np.array_equal(data['phi'], phi))
            self.assertTrue(np.array_equal(data['mass'], mass))
            self.assertTrue(np.array_equal(data['frequencies_Hz'], frequencies))
            self.assertTrue(np.array_equal(data['generalized_mass'], gen_mass))


class TestLoadSummary(unittest.TestCase):
    def test_missing_summary_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / 'sweep').mkdir()
            with self.assertRaises(FileNotFoundError):
                export_speed_sweep.load_summary(base)

    def test_loads_summary_correctly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            sweep_dir = base / 'sweep'
            sweep_dir.mkdir()

            reports = [
                {'modes': 10, 'speed_m_s': 30.0, 'status': 'executed_exploratory'},
                {'modes': 20, 'speed_m_s': 30.0, 'status': 'executed_exploratory'}
            ]
            (sweep_dir / 'summary.json').write_text(json.dumps(reports))

            loaded = export_speed_sweep.load_summary(base)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0]['modes'], 10)


class TestLoadMotion(unittest.TestCase):
    def test_missing_motion_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            sweep_dir = base / 'sweep'
            sweep_dir.mkdir()

            result, sha = export_speed_sweep.load_motion(base, 10, 30.0)
            self.assertIsNone(result)
            self.assertIsNone(sha)

    def test_motion_with_insufficient_frames_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            sweep_dir = base / 'sweep'
            sweep_dir.mkdir()
            folder = sweep_dir / 'n10-V30'
            folder.mkdir()

            # Only 1 frame
            history = {
                'frames_time_and_q': [[0.0, 0.0, 0.0]],
                'equilibrium_q': [0.0, 0.0],
                'stopped_at_50mm_guard': False
            }
            (folder / 'motion.json').write_text(json.dumps(history))

            result, sha = export_speed_sweep.load_motion(base, 10, 30.0)
            self.assertIsNone(result)
            self.assertIsNone(sha)

    def test_valid_motion_returns_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            sweep_dir = base / 'sweep'
            sweep_dir.mkdir()
            folder = sweep_dir / 'n10-V30'
            folder.mkdir()

            history = {
                'frames_time_and_q': [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.5, 0.3]
                ],
                'equilibrium_q': [0.0, 0.0],
                'stopped_at_50mm_guard': False
            }
            (folder / 'motion.json').write_text(json.dumps(history))

            result, sha = export_speed_sweep.load_motion(base, 10, 30.0)
            self.assertIsNotNone(result)
            self.assertIsNotNone(sha)
            self.assertEqual(len(result['frames_time_and_q']), 2)


class TestIsEligible(unittest.TestCase):
    def test_executed_exploratory_is_eligible(self):
        report = {'status': 'executed_exploratory'}
        history = {'frames_time_and_q': [[0, 0], [0.1, 0.1]]}
        self.assertTrue(export_speed_sweep.is_eligible(report, history))

    def test_transient_guard_stop_with_valid_motion_is_eligible(self):
        report = {'status': 'transient_guard_stop'}
        history = {
            'frames_time_and_q': [[0, 0], [0.1, 0.1]],
            'stopped_at_50mm_guard': True
        }
        self.assertTrue(export_speed_sweep.is_eligible(report, history))

    def test_transient_guard_stop_without_stopped_flag_not_eligible(self):
        report = {'status': 'transient_guard_stop'}
        history = {
            'frames_time_and_q': [[0, 0], [0.1, 0.1]],
            'stopped_at_50mm_guard': False
        }
        self.assertFalse(export_speed_sweep.is_eligible(report, history))

    def test_failed_equilibrium_not_eligible(self):
        report = {'status': 'failed_equilibrium'}
        self.assertFalse(export_speed_sweep.is_eligible(report, None))

    def test_outside_guard_not_eligible(self):
        report = {'status': 'outside_displacement_experiment_guard'}
        self.assertFalse(export_speed_sweep.is_eligible(report, None))

    def test_unstable_aero_rom_not_eligible(self):
        report = {'status': 'unstable_aero_rom'}
        self.assertFalse(export_speed_sweep.is_eligible(report, None))

    def test_failed_numerical_not_eligible(self):
        report = {'status': 'failed_numerical'}
        self.assertFalse(export_speed_sweep.is_eligible(report, None))


class TestBuildPayload(unittest.TestCase):
    def test_excludes_invalid_statuses(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create native data
            xyz = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
            quads = np.array([[0, 1, 2, 0]])
            phi = np.random.rand(20, 3, 3)
            mass = np.array([1.0, 1.0, 1.0])
            frequencies = np.array([1.0, 2.0, 3.0])
            gen_mass = np.array([1.0, 1.0, 1.0])

            np.savez(base / 'native-modal.npz',
                     xyz=xyz, quads=quads, phi=phi, mass=mass,
                     frequencies_Hz=frequencies, generalized_mass=gen_mass)

            # Create sweep folder with summary
            sweep_dir = base / 'sweep'
            sweep_dir.mkdir()

            # Create motion folders for all modes/speed combinations we'll test
            for modes, speed in [(10, 30.0), (20, 30.0), (10, 40.0), (20, 40.0)]:
                folder = sweep_dir / f'n{modes}-V{speed:g}'
                folder.mkdir()
                history = {
                    'frames_time_and_q': [[0] + [0.0] * 10, [0.1] + [0.5] * 10],
                    'equilibrium_q': [0.0] * 10,
                    'stopped_at_50mm_guard': False
                }
                (folder / 'motion.json').write_text(json.dumps(history))

            # 20 modes @ 30 m/s is failed_equilibrium
            # 20 modes @ 40 m/s is transient_guard_stop (but has motion)
            summary = [
                {'modes': 10, 'speed_m_s': 30.0, 'status': 'executed_exploratory'},
                {'modes': 20, 'speed_m_s': 30.0, 'status': 'failed_equilibrium'},
                {'modes': 10, 'speed_m_s': 40.0, 'status': 'transient_guard_stop'},
                {'modes': 20, 'speed_m_s': 40.0, 'status': 'transient_guard_stop'}
            ]
            (sweep_dir / 'summary.json').write_text(json.dumps(summary))

            # Update the two guard-stop motion files to have stopped_at_50mm_guard
            (sweep_dir / 'n10-V40' / 'motion.json').write_text(json.dumps({
                'frames_time_and_q': [[0] + [0.0] * 10, [0.1] + [0.5] * 10],
                'equilibrium_q': [0.0] * 10,
                'stopped_at_50mm_guard': True
            }))
            (sweep_dir / 'n20-V40' / 'motion.json').write_text(json.dumps({
                'frames_time_and_q': [[0] + [0.0] * 10, [0.1] + [0.5] * 10],
                'equilibrium_q': [0.0] * 10,
                'stopped_at_50mm_guard': True
            }))

            native_data, native_sha = export_speed_sweep.load_native(base)
            payload = export_speed_sweep.build_payload(base, native_data, native_sha, summary)

            # Should have 3 cases (10 modes @ 30 m/s, 10 modes @ 40 m/s, 20 modes @ 40 m/s)
            self.assertEqual(len(payload['cases']), 3)

            # Should have 1 omitted (20 modes @ 30 m/s failed)
            self.assertEqual(len(payload['omitted_cases']), 1)
            self.assertEqual(payload['omitted_cases'][0]['status'], 'failed_equilibrium')

            # Check models have correct dimensions
            self.assertEqual(len(payload['models']['modes10']['modes']), 10)
            self.assertEqual(len(payload['models']['modes20']['modes']), 20)

            # Check physical properties are shared
            self.assertEqual(payload['models']['modes10']['mass_kg'], payload['models']['modes20']['mass_kg'])
            self.assertEqual(payload['models']['modes10']['thickness_m'], payload['models']['modes20']['thickness_m'])

    def test_cases_sorted_by_speed_then_modes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            xyz = np.array([[0, 0, 0]])
            quads = np.array([[0, 0, 0, 0]])
            phi = np.random.rand(20, 1, 3)
            mass = np.array([1.0])
            frequencies = np.array([1.0])
            gen_mass = np.array([1.0])

            np.savez(base / 'native-modal.npz',
                     xyz=xyz, quads=quads, phi=phi, mass=mass,
                     frequencies_Hz=frequencies, generalized_mass=gen_mass)

            sweep_dir = base / 'sweep'
            sweep_dir.mkdir()

            # Create motion folders for multiple cases - use :g format to match exporter
            for modes, speed in [(20, 30.0), (10, 30.0), (10, 40.0)]:
                folder = sweep_dir / f'n{modes}-V{speed:g}'
                folder.mkdir()
                # frames_time_and_q format: [time, q0, q1, ..., q{modes-1}]
                history = {
                    'frames_time_and_q': [
                        [0] + [0.0] * modes,
                        [0.1] + [0.5] * modes
                    ],
                    'equilibrium_q': [0.0] * modes,
                    'stopped_at_50mm_guard': False
                }
                (folder / 'motion.json').write_text(json.dumps(history))

            summary = [
                {'modes': 20, 'speed_m_s': 30.0, 'status': 'executed_exploratory'},
                {'modes': 10, 'speed_m_s': 30.0, 'status': 'executed_exploratory'},
                {'modes': 10, 'speed_m_s': 40.0, 'status': 'executed_exploratory'}
            ]
            (sweep_dir / 'summary.json').write_text(json.dumps(summary))

            native_data, native_sha = export_speed_sweep.load_native(base)
            payload = export_speed_sweep.build_payload(base, native_data, native_sha, summary)

            # Should be sorted: (10, 30), (20, 30), (10, 40)
            names = [c['name'] for c in payload['cases']]
            self.assertEqual(names[0], '10 modes / 30 m/s / loaded perturbation')
            self.assertEqual(names[1], '20 modes / 30 m/s / loaded perturbation')
            self.assertEqual(names[2], '10 modes / 40 m/s / loaded perturbation')


class TestExport(unittest.TestCase):
    def test_exports_valid_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            xyz = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
            quads = np.array([[0, 1, 2, 0]])
            phi = np.random.rand(20, 3, 3)
            mass = np.array([1.0, 1.0, 1.0])
            frequencies = np.array([1.0, 2.0, 3.0])
            gen_mass = np.array([1.0, 1.0, 1.0])

            np.savez(base / 'native-modal.npz',
                     xyz=xyz, quads=quads, phi=phi, mass=mass,
                     frequencies_Hz=frequencies, generalized_mass=gen_mass)

            sweep_dir = base / 'sweep'
            sweep_dir.mkdir()

            folder = sweep_dir / 'n10-V30'
            folder.mkdir()
            history = {
                'frames_time_and_q': [[0] + [0.0] * 10, [0.1] + [0.5] * 10],
                'equilibrium_q': [0.0] * 10,
                'stopped_at_50mm_guard': False,
                'poles': {
                    'tracked_bending': {'growth_per_s': 0.1, 'frequency_hz': 2.0},
                    'dominant_resolved_oscillatory': {'growth_per_s': 0.15}
                }
            }
            (folder / 'motion.json').write_text(json.dumps(history))

            summary = [
                {'modes': 10, 'speed_m_s': 30.0, 'status': 'executed_exploratory'}
            ]
            (sweep_dir / 'summary.json').write_text(json.dumps(summary))

            output = base / 'speed-comparison-data.json'
            payload = export_speed_sweep.export(base, output)

            self.assertTrue(output.exists())
            self.assertEqual(len(payload['cases']), 1)
            self.assertIn('modes10', payload['models'])
            self.assertIn('modes20', payload['models'])
            self.assertIn('source_sha256', payload)

    def test_excludes_missing_required_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # No native-modal.npz
            sweep_dir = base / 'sweep'
            sweep_dir.mkdir()
            (sweep_dir / 'summary.json').write_text('[]')

            output = base / 'speed-comparison-data.json'
            with self.assertRaises(FileNotFoundError):
                export_speed_sweep.export(base, output)


class TestPlot(unittest.TestCase):
    def test_creates_plot_with_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            xyz = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
            quads = np.array([[0, 1, 2, 0]])
            phi = np.random.rand(20, 3, 3)
            mass = np.array([1.0, 1.0, 1.0])
            frequencies = np.array([1.0, 2.0, 3.0])
            gen_mass = np.array([1.0, 1.0, 1.0])

            np.savez(base / 'native-modal.npz',
                     xyz=xyz, quads=quads, phi=phi, mass=mass,
                     frequencies_Hz=frequencies, generalized_mass=gen_mass)

            sweep_dir = base / 'sweep'
            sweep_dir.mkdir()

            folder = sweep_dir / 'n10-V30'
            folder.mkdir()
            history = {
                'frames_time_and_q': [[0] + [0.0] * 20, [0.1] + [0.5] * 20],
                'equilibrium_q': [0.0] * 10,
                'stopped_at_50mm_guard': False,
                'poles': {
                    'tracked_bending': {'growth_per_s': 0.1, 'frequency_hz': 2.0},
                    'dominant_resolved_oscillatory': {'growth_per_s': 0.15}
                }
            }
            (folder / 'motion.json').write_text(json.dumps(history))

            summary = [
                {'modes': 10, 'speed_m_s': 30.0, 'status': 'executed_exploratory'}
            ]
            (sweep_dir / 'summary.json').write_text(json.dumps(summary))

            output = base / 'speed-comparison-data.json'
            payload = export_speed_sweep.export(base, output)

            fig = export_speed_sweep.plot(base, payload)
            self.assertIsNotNone(fig)

            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            plt.close(fig)


class TestValidation(unittest.TestCase):
    def test_validates_required_fields(self):
        payload = {}
        with self.assertRaises(ValueError):
            export_speed_sweep.validate_payload(payload)

    def test_validates_mesh(self):
        payload = {
            'title': 'Test',
            'scope': 'Test',
            'source': 'Test',
            'mesh': {'nodes': [], 'quads': []},
            'models': {},
            'cases': [],
            'source_sha256': {}
        }
        with self.assertRaises(ValueError):
            export_speed_sweep.validate_payload(payload)


class TestCLI(unittest.TestCase):
    def test_cli_exits_on_missing_files(self):
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            result = subprocess.run(
                [sys.executable, '-m', 'scripts.experiments.export_loaded_speed_sweep', str(base)],
                capture_output=True,
                text=True
            )
            self.assertNotEqual(result.returncode, 0)

    def test_cli_creates_output_files(self):
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create native-modal.npz with 10 modes
            xyz = np.array([[0, 0, 0]])
            quads = np.array([[0, 0, 0, 0]])
            phi = np.random.rand(10, 1, 3)
            mass = np.array([1.0])
            frequencies = np.array([1.0])
            gen_mass = np.array([1.0])

            np.savez(base / 'native-modal.npz',
                     xyz=xyz, quads=quads, phi=phi, mass=mass,
                     frequencies_Hz=frequencies, generalized_mass=gen_mass)

            # Create sweep folder
            sweep_dir = base / 'sweep'
            sweep_dir.mkdir()

            folder = sweep_dir / 'n10-V30'
            folder.mkdir()
            history = {
                'frames_time_and_q': [[0] + [0.0] * 10, [0.1] + [0.5] * 10],
                'equilibrium_q': [0.0] * 10,
                'stopped_at_50mm_guard': False
            }
            (folder / 'motion.json').write_text(json.dumps(history))

            summary = [{'modes': 10, 'speed_m_s': 30.0, 'status': 'executed_exploratory'}]
            (sweep_dir / 'summary.json').write_text(json.dumps(summary))

            result = subprocess.run(
                [sys.executable, '-m', 'scripts.experiments.export_loaded_speed_sweep', str(base), '--no-plot'],
                capture_output=True,
                text=True
            )
            self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")
            self.assertTrue((base / 'speed-comparison-data.json').exists())


if __name__ == '__main__':
    unittest.main()
