"""Behavioral case-generation checks; native OpenFOAM validation is separate."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('flow_case', Path(__file__).parents[1]/'scripts/generate_flow_case.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def fixture(path):
    path.mkdir()
    # Native counted ASCII lists for a single cube with four boundary patches.
    contents = {
        'points': ('vectorField', '8\n((0 0 0)(1 0 0)(1 1 0)(0 1 0)(0 0 1)(1 0 1)(1 1 1)(0 1 1))'),
        'faces': ('faceList', '6\n(4(0 4 7 3) 4(1 2 6 5) 4(0 1 5 4) 4(3 7 6 2) 4(4 5 6 7) 4(0 3 2 1))'),
        'owner': ('labelList', '6\n(0 0 0 0 0 0)'),
        'neighbour': ('labelList', '0\n()'),
        'boundary': ('polyBoundaryMesh', '''4
(
 inlet { type patch; nFaces 1; startFace 0; }
 outlet { type patch; nFaces 1; startFace 1; }
 farfield { type patch; nFaces 3; startFace 2; }
 wing { type wall; inGroups 1(wall); nFaces 1; startFace 5; }
)''')}
    for name, (kind, body) in contents.items():
        (path/name).write_text(f'FoamFile {{ version 2.0; format ascii; class {kind}; object {name}; }}\n{body}\n')


def vec(text, key):
    match = re.search(r'\b'+key+r'\s+(?:uniform\s+)?\(([^()]*)\)', text)
    return tuple(map(float, match[1].split()))


class GeneratedCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.mesh = self.root/'mesh'; fixture(self.mesh)
        self.out = self.root/'case'

    def generate(self, **kwargs):
        return m.generate_case(self.mesh, self.out, **kwargs)

    def test_native_fixture_copies_unchanged_and_manifest_hashes_match_bytes(self):
        before = {p.name: p.read_bytes() for p in self.mesh.iterdir()}
        report = self.generate()
        self.assertEqual(report['status'], 'unqualified_setup')
        self.assertEqual(report['mesh']['boundary_patches'], ['inlet','outlet','farfield','wing'])
        for name, data in before.items():
            self.assertEqual((self.mesh/name).read_bytes(), data)
            self.assertEqual((self.out/'constant/polyMesh'/name).read_bytes(), data)
            expected = hashlib.sha256(data).hexdigest()
            self.assertEqual(report['mesh']['source_sha256'][name], expected)
            self.assertEqual(report['mesh']['copied_sha256'][name], expected)
        self.assertEqual(len(report['generated_sha256']), 10)
        for name, digest in report['generated_sha256'].items():
            self.assertEqual(hashlib.sha256((self.out/name).read_bytes()).hexdigest(), digest)
        self.assertEqual(json.loads((self.out/'manifest.json').read_text())['status'], 'unqualified_setup')

    def test_generated_force_axes_and_origin_at_four_degrees(self):
        self.generate()
        c = (self.out/'system/controlDict').read_text(); u = (self.out/'0/U').read_text()
        drag, lift = vec(c,'dragDir'), vec(c,'liftDir')
        for actual, expected in zip(drag, (.9975640502598242,0,.0697564737441253)):
            self.assertAlmostEqual(actual, expected, places=14)
        self.assertAlmostEqual(sum(a*b for a,b in zip(drag,lift)), 0, places=14)
        self.assertGreater(lift[2], .99); self.assertLess(lift[0], 0)
        for x,y in zip(vec(u,'internalField'), (29.9269215077947,0,2.09269421232376)):
            self.assertAlmostEqual(x,y,places=11)
        self.assertEqual(vec(c,'pitchAxis'), (0,1,0))
        self.assertEqual(re.findall(r'CofR\s+(\([^)]*\))',c), ['(0.0254 0 0)']*2)
        self.assertEqual(c.count('libs (forces)'),2)
        self.assertNotIn('libsensors',c)
        self.assertEqual(c.count('writeControl writeTime'),2)
        # A known force projects differently onto body x/z and wind lift/drag.
        self.assertAlmostEqual(100*drag[0]+50*drag[2], 103.2442287131887, places=10)
        self.assertAlmostEqual(100*lift[0]+50*lift[2], 42.90255513857868, places=10)

    def test_zero_alpha_and_reference_scaling(self):
        report = self.generate(alpha=0)
        c = (self.out/'system/controlDict').read_text()
        self.assertEqual(vec(c,'dragDir'),(1,0,0)); self.assertEqual(vec(c,'liftDir'),(0,0,1))
        self.assertAlmostEqual(report['flow']['dynamic_pressure_Pa'],551.273970764428)
        self.assertAlmostEqual(report['geometry']['reference_area_m2'],.12387072)
        self.assertAlmostEqual(report['flow']['k_m2_s2'],.00135)
        self.assertAlmostEqual(report['flow']['omega_per_s'],math.sqrt(.00135)/(math.sqrt(.3)*.007112))
        self.assertAlmostEqual(report['flow']['chord_Re'],208684.5740972537)

    def test_native_field_classes_dimensions_and_wall_conditions(self):
        self.generate()
        dimensions = {'U':'0 1 -1','p':'0 2 -2','k':'0 2 -2','omega':'0 0 -1','nut':'0 2 -1'}
        for name, dims in dimensions.items():
            text = (self.out/'0'/name).read_text()
            self.assertIn('class '+('volVectorField' if name=='U' else 'volScalarField')+';',text)
            self.assertIn('dimensions ['+dims+' 0 0 0 0]',text)
            self.assertNotIn('{{',text)
        k = (self.out/'0/k').read_text(); self.assertRegex(k,r'wing\s*\{ type fixedValue; value uniform 0;')
        omega = (self.out/'0/omega').read_text(); self.assertIn('blending binomial; n 2;',omega)
        self.assertIn('nutLowReWallFunction',(self.out/'0/nut').read_text())
        pressure = (self.out/'0/p').read_text()
        self.assertRegex(pressure,r'outlet\s*\{ type fixedValue; value uniform 0;')
        self.assertIn('type freestreamPressure;',pressure)
        for name in ('fvSchemes','fvSolution','controlDict'):
            text=(self.out/'system'/name).read_text(); self.assertNotIn('{{',text)
        schemes=(self.out/'system/fvSchemes').read_text()
        self.assertIn('ddtSchemes { default steadyState; }',schemes)
        self.assertIn('linearUpwindV grad(U)',schemes)
        self.assertNotIn('residualControl',(self.out/'system/fvSolution').read_text())

    def test_existing_empty_or_populated_output_preserved(self):
        self.out.mkdir()
        with self.assertRaises(ValueError): self.generate()
        marker=self.out/'marker';marker.write_text('keep')
        with self.assertRaises(ValueError): self.generate()
        self.assertEqual(marker.read_text(),'keep')

    def test_missing_or_nonregular_mesh_entry_fails_before_output(self):
        (self.mesh/'points').unlink()
        with self.assertRaises(ValueError): self.generate()
        self.assertFalse(self.out.exists())
        (self.mesh/'points').mkdir()
        with self.assertRaises(ValueError): self.generate()
        self.assertFalse(self.out.exists())

    def test_required_and_optional_symlinks_rejected(self):
        target=self.root/'target';target.write_text('untouched')
        for name in ('points','cellZones'):
            p=self.mesh/name
            if p.exists(): p.unlink()
            p.symlink_to(target)
            with self.assertRaises(ValueError): self.generate()
            self.assertFalse(self.out.exists());self.assertEqual(target.read_text(),'untouched')
            p.unlink();p.write_text('regular')

    def test_output_in_source_tree_rejected(self):
        with self.assertRaises(ValueError): m.generate_case(self.mesh,self.mesh/'new')
        self.assertFalse((self.mesh/'new').exists())

    def test_native_boundary_names_types_and_duplicates_rejected(self):
        p=self.mesh/'boundary';original=p.read_text()
        for text in (original.replace('wing {','wrong {'),original.replace('type wall','type patch'),
                     original.replace('outlet {','inlet {'),original.replace('4\n(', '5\n(')):
            with self.subTest(text=text):
                p.write_text(text)
                with self.assertRaises(ValueError): self.generate()
                self.assertFalse(self.out.exists())
        p.write_text(original)

    def test_invalid_numeric_inputs_fail_before_output(self):
        for alpha in (float('nan'),float('inf'),-16,16):
            with self.assertRaises(ValueError): self.generate(alpha=alpha)
        for iterations in (0,499,5001,500.5,True):
            with self.assertRaises(ValueError): self.generate(iterations=iterations)
        self.assertFalse(self.out.exists())

    def test_copy_corruption_retains_failed_manifest(self):
        def corrupt(src,dst,**kwargs): Path(dst).write_bytes(b'corrupted')
        with patch.object(m.shutil,'copyfile',side_effect=corrupt):
            with self.assertRaises(ValueError): self.generate()
        report=json.loads((self.out/'manifest.json').read_text())
        self.assertEqual(report['status'],'setup_failed')
        self.assertEqual(report['failure']['stage'],'copy_mesh')
        self.assertNotEqual(report['mesh']['source_sha256']['points'],report['mesh']['copied_sha256']['points'])

    def test_dictionary_failure_retains_artifacts_without_success(self):
        with patch.object(m,'dictionaries',side_effect=OSError('injected write failure')):
            with self.assertRaises(OSError): self.generate()
        report=json.loads((self.out/'manifest.json').read_text())
        self.assertEqual(report['status'],'setup_failed')
        self.assertEqual(report['failure']['stage'],'write_dictionaries')
        self.assertTrue((self.out/'constant/polyMesh/points').is_file())
        self.assertEqual(report['generated_sha256'],{})

    def test_manifest_write_failure_retains_failed_report_when_retry_possible(self):
        original = Path.write_text
        failed = False
        def write(path, data, *args, **kwargs):
            nonlocal failed
            if path.name == 'manifest.json' and not failed:
                failed = True
                raise OSError('transient manifest write failure')
            return original(path, data, *args, **kwargs)
        with patch.object(Path, 'write_text', write):
            with self.assertRaises(OSError): self.generate()
        report = json.loads((self.out/'manifest.json').read_text())
        self.assertEqual(report['status'], 'setup_failed')
        self.assertEqual(report['failure']['stage'], 'write_manifest')

    def test_cli_success_and_failure_exit_codes(self):
        self.assertEqual(m.main(['--mesh-dir',str(self.mesh),'--output',str(self.out)]),0)
        self.assertEqual(m.main(['--mesh-dir',str(self.mesh),'--output',str(self.out)]),1)


if __name__ == '__main__': unittest.main()
