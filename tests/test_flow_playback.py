"""Synthetic fixtures test viewer contracts; these are not CFD results."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/build_flow_playback.py'
spec = importlib.util.spec_from_file_location('playback', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    return {'schema_version': 1, 'time_kind': 'physical_seconds',
            'run': {'id': 'SYNTHETIC TEST ONLY', 'solver': 'fixture', 'status': 'diagnostic_only',
                    'limitations': ['Synthetic test, not CFD'], 'source_revision': 'fixture',
                    'speed_m_s': 30, 'chord_m': .1, 'reference_pressure_kinematic': 10,
                    'dynamic_pressure_kinematic': 100},
            'wing': {'points': [[0,-.5,0],[0,.5,0],[.1,0,0]], 'triangles': [[0,1,2]]},
            'samples': {'points': [[0,0,.02],[.2,.6,0],[.3,0,0]], 'groups': ['midspan','tip','wake']},
            'frames': [{'time_s': t, 'U': [[3,4,0],[0,0,v],[0,0,0]], 'p': [110,-90,10]}
                       for t,v in [(1e-6,2),(3e-6,6),(9e-6,8)]],
            'loads': [{'time_s': t, 'CL': a, 'CD': .03, 'Cm': -.05}
                      for t,a in [(1e-6,.4),(2e-6,.5),(9e-6,.6)]]}


class PlaybackTests(unittest.TestCase):
    def test_physical_values_and_irregular_times_preserved(self):
        data = fixture()
        self.assertEqual(module.derived_ranges(data), {'speed': [0,8], 'cp': [-1,1]})
        page = module.build_html(data)
        text = re.search(r'<script id="flow-data" type="application/json">(.*?)</script>', page, re.S)[1]
        embedded = json.loads(text)
        self.assertEqual([f['time_s'] for f in embedded['frames']], [1e-6,3e-6,9e-6])
        self.assertEqual(embedded['frames'], data['frames'])

    def test_metadata_cannot_end_data_script(self):
        data = fixture()
        bad = '</script><script>window.PWNED=true</script>&\u2028'
        data['run']['id'] = bad
        page = module.build_html(data)
        self.assertNotIn(bad, page)
        text = re.search(r'<script id="flow-data" type="application/json">(.*?)</script>', page, re.S)[1]
        self.assertNotIn('<', text)
        self.assertEqual(json.loads(text)['run']['id'], bad)

    def test_invalid_contracts(self):
        mutations = [lambda d: d.update(time_kind='steady_iterations'),
                     lambda d: d['frames'][1].update(time_s=1e-6),
                     lambda d: d['frames'][0].update(time_s=-1),
                     lambda d: d['frames'][0]['p'].__setitem__(0,float('nan')),
                     lambda d: d['frames'][0]['U'][0].__setitem__(0,float('inf')),
                     lambda d: d['frames'][0].update(U=[[1,2,3]]),
                     lambda d: d['wing']['triangles'].__setitem__(0,[True,1,2]),
                     lambda d: d['wing']['triangles'].__setitem__(0,[0,1,99]),
                     lambda d: d['run'].update(dynamic_pressure_kinematic=0),
                     lambda d: d['run'].update(chord_m=True),
                     lambda d: d['run'].update(limitations=[]),
                     lambda d: d['samples']['groups'].pop(),
                     lambda d: d['loads'][1].update(time_s=1e-6)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data=fixture();mutate(data)
                with self.assertRaises(ValueError):module.validate(data)

    def test_empty_loads_explicitly_supported(self):
        data=fixture();data['loads']=[];module.validate(data)

    def test_cli_refuses_overwrite_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'data.json';out=root/'viewer.html'
            source.write_text(json.dumps(fixture()));out.write_text('preserve')
            cmd=[sys.executable,str(SCRIPT),'--input',str(source),'--output',str(out)]
            self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            self.assertEqual(out.read_text(),'preserve')
            out.unlink();data=fixture();data['frames'][0]['p'][0]=float('nan');source.write_text(json.dumps(data))
            self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
