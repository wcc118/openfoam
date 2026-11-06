import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('flow3d', Path(__file__).resolve().parents[1] / 'scripts/build_flow_3d.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    return {'schema_version': 1, 'kind': 'native-flow-3d',
            'metadata': {'title': 'Synthetic flow', 'alpha_deg': 4, 'steady_iteration': 100,
                         'provenance': {'source': 'synthetic'}, 'limitations': ['Synthetic test, no CFD claim.']},
            'wing': {'points': [0, 0, 0, .1, 0, 0, 0, 1, 0], 'polys': [3, 0, 1, 2]},
            'paths': {'points': [0, 0, .1, 1, 0, .2, 1, 1, .3], 'lines': [3, 0, 1, 2], 'speed': [10, 20, 30]},
            'vortex': {'points': [0, 0, .2, .1, 0, .2, 0, 1, .2], 'polys': [3, 0, 1, 2], 'speed': [15]},
            'volume': {'origin': [0, 0, 0], 'dimensions': [2, 2, 2], 'spacing': [.1, .1, .1], 'speed': [-1, 10, 20, 30, 10, 20, 30, 40]}}


class Flow3DTests(unittest.TestCase):
    def test_valid(self):
        self.assertIsNotNone(m.validate(fixture()))

    def test_bad_cells_and_scalars(self):
        for key, field, value in [('wing', 'polys', [3, 0, 1]), ('wing', 'polys', [3, 0, 1, 3]),
                                  ('paths', 'lines', [1, 0]), ('paths', 'lines', [2, 0, 1, 99]),
                                  ('vortex', 'polys', [3, 0, 1, 2.0]), ('paths', 'speed', [10]),
                                  ('vortex', 'speed', [1, 2]), ('volume', 'speed', [-2] * 8),
                                  ('volume', 'dimensions', [2, 2, 2.0]), ('volume', 'spacing', [0, 1, 1]),
                                  ('wing', 'points', [0, float('nan'), 0]), ('volume', 'speed', [float('inf')] * 8)]:
            with self.subTest(key=key, field=field, value=value):
                d = fixture(); d[key][field] = value
                with self.assertRaises(ValueError):
                    m.validate(d)

    def test_bad_metadata(self):
        for field, value in [('title', ''), ('limitations', []), ('provenance', {}), ('steady_iteration', True), ('alpha_deg', float('nan'))]:
            d = fixture(); d['metadata'][field] = value
            with self.assertRaises(ValueError):
                m.validate(d)
        d = fixture(); del d['paths']
        with self.assertRaises(ValueError):
            m.validate(d)

    def test_offline_safe_embedding(self):
        d = fixture(); attack = '</script><img src=x onerror="window.PWNED=1">'
        d['metadata']['title'] = attack
        html = m.build_html(d)
        self.assertNotIn(attack, html)
        self.assertNotIn('src="http', html)
        payload = html.split('<script id="flow-data" type="application/json">')[1].split('</script>')[0]
        self.assertEqual(json.loads(payload), d)
        self.assertNotIn('/*__', html)


if __name__ == '__main__':
    unittest.main()
