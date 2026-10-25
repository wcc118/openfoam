import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runtime', ROOT/'scripts/qualify_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
FIX = ROOT/'tests/fixtures/cavity'


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self):
        out = self.root/'recorded'
        out.mkdir()
        (out/'version.txt').write_text('v2412\n')
        (out/'exit-codes.txt').write_text(''.join(f'{case} {cmd} 0\n' for case in ('cavity-a','cavity-b') for cmd in ('blockMesh','checkMesh','icoFoam')))
        for name in ('cavity-a','cavity-b'):
            case=out/name
            (case/'0.5').mkdir(parents=True)
            for field in ('U','p'): shutil.copyfile(FIX/field,case/'0.5'/field)
            for log in ('log.checkMesh','log.icoFoam'): shutil.copyfile(FIX/log,case/log)
        return out

    def test_recorded_tutorial(self):
        result = runtime.verify_acceptance(self.fixture())
        self.assertAlmostEqual(result['cavity-a']['max_courant'], .852134)
        self.assertAlmostEqual(result['cavity-b']['final_local_continuity'], 9.66354e-9)
        self.assertEqual(result['byte_identical_fields'], ['U','p'])

    def test_second_run_is_actually_checked(self):
        out=self.fixture()
        (out/'cavity-b/log.checkMesh').write_text('Mesh failed\n')
        with self.assertRaisesRegex(ValueError,'cavity-b'): runtime.verify_acceptance(out)

    def test_different_repeat_rejected(self):
        out=self.fixture()
        with (out/'cavity-b/0.5/p').open('a') as f: f.write('\n')
        with self.assertRaisesRegex(ValueError,'repeated fields differ'): runtime.verify_acceptance(out)

    def test_nan_field_rejected(self):
        out=self.fixture(); p=out/'cavity-b/0.5/U'
        p.write_text(p.read_text().replace('0.000253405','nan',1))
        with self.assertRaisesRegex(ValueError,'nonfinite'): runtime.verify_acceptance(out)

    def test_missing_scalar_rejected(self):
        out=self.fixture(); p=out/'cavity-b/0.5/p'
        p.write_text(p.read_text().replace('400\n(','399\n(',1))
        with self.assertRaisesRegex(ValueError,'400 values'): runtime.verify_acceptance(out)

    def test_missing_courant_is_not_zero(self):
        text=(FIX/'log.icoFoam').read_text().replace('Courant Number','Hidden')
        with self.assertRaisesRegex(ValueError,'missing'): runtime.parse_solver_log(text)

    def test_high_early_courant_rejected(self):
        text='Courant Number mean: 0.5 max: 1.5\n'+(FIX/'log.icoFoam').read_text()
        with self.assertRaisesRegex(ValueError,'Courant out'): runtime.parse_solver_log(text)

    def test_nonfinite_log_rejected(self):
        text=(FIX/'log.icoFoam').read_text().replace('max: 0.852134','max: nan')
        with self.assertRaisesRegex(ValueError,'nonfinite'): runtime.parse_solver_log(text)

    def test_failed_ledger_rejected(self):
        out=self.fixture(); p=out/'exit-codes.txt'
        p.write_text(p.read_text().replace('cavity-b icoFoam 0','cavity-b icoFoam 1'))
        with self.assertRaisesRegex(ValueError,'ledger'): runtime.verify_acceptance(out)

    def test_existing_empty_output_refused(self):
        with self.assertRaises(FileExistsError): runtime.qualify(self.root)

    def test_failed_container_preserves_report(self):
        image=[dict(Architecture='arm64',Os='linux',Id='fixture',Size=1,RepoDigests=[runtime.get_openfoam_image()])]
        returns=[subprocess.CompletedProcess([],0,'test-revision',''),subprocess.CompletedProcess([],0,'',''),
                 subprocess.CompletedProcess([],0,json.dumps(image),''),subprocess.CompletedProcess([],42,'started','failure')]
        with patch.object(runtime.platform,'machine',return_value='aarch64'), patch.object(runtime.platform,'platform',return_value='test-linux'), patch.object(runtime.subprocess,'run',side_effect=returns):
            report=runtime.qualify(self.root/'failed')
        self.assertEqual(report['status'],'failed')
        self.assertEqual(report['commands'][-1]['exit_code'],42)
        self.assertEqual((self.root/'failed/container_stderr.log').read_text(),'failure')
        self.assertEqual(json.loads((self.root/'failed/qualify_report.json').read_text())['status'],'failed')

    def test_limited_container_arguments(self):
        cmd=runtime.container_command(self.root/'with space')
        self.assertIn('--pull',cmd)
        self.assertEqual(cmd[cmd.index('--pull')+1],'never')
        self.assertIn('--entrypoint',cmd)
        self.assertNotIn('--privileged',cmd)
        self.assertEqual(cmd.count('--mount'),1)

    def test_unsupported_host_architecture_rejected(self):
        # Temporarily clear the mapping to simulate unsupported architecture
        original_map = runtime.ARCH_IMAGE_MAP.copy()
        runtime.ARCH_IMAGE_MAP.clear()
        try:
            with self.assertRaisesRegex(ValueError, 'unsupported host architecture'):
                runtime.qualify(self.root/'unsupported-arch')
        finally:
            runtime.ARCH_IMAGE_MAP.update(original_map)

    def test_platform_match_reported(self):
        # Verify platform_match is reported in the output
        image=[dict(Architecture='arm64',Os='linux',Id='fixture',Size=1,RepoDigests=[runtime.get_openfoam_image()])]
        returns=[subprocess.CompletedProcess([],0,'test-revision',''),subprocess.CompletedProcess([],0,'',''),
                 subprocess.CompletedProcess([],0,json.dumps(image),''),subprocess.CompletedProcess([],42,'started','failure')]
        with patch.object(runtime.platform,'machine',return_value='aarch64'), patch.object(runtime.platform,'platform',return_value='test-linux'), patch.object(runtime.subprocess,'run',side_effect=returns):
            report=runtime.qualify(self.root/'platform-check')
        self.assertIn('platform_match', report)
        self.assertEqual(report['platform_match']['host'], 'aarch64')
        self.assertEqual(report['platform_match']['image'], 'arm64')
        self.assertEqual(report['platform_match']['os'], 'linux')

    def test_arm64_host_uses_pinned_digest(self):
        # Verify the mapping contains the expected ARM64 digest
        self.assertIn('aarch64', runtime.ARCH_IMAGE_MAP)
        self.assertEqual(runtime.ARCH_IMAGE_MAP['aarch64'], 'b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4')
        # Verify the function returns the correct image for current host
        self.assertIn('b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4', runtime.get_openfoam_image())

    def test_amd64_host_uses_pinned_digest(self):
        # Verify the mapping contains the expected AMD64 digest
        self.assertIn('amd64', runtime.ARCH_IMAGE_MAP)
        self.assertEqual(runtime.ARCH_IMAGE_MAP['amd64'], 'adbf625ac47ed81b34018602a6caeb4076bfacc2046b2f8cd36f82adb376946b')


if __name__=='__main__': unittest.main()
