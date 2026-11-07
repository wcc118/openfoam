"""Serialization boundaries through the real builder; browser integration is separate."""
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from build_behavior_viewer import build


class BehaviorBuildTests(unittest.TestCase):
    def fixture(self):
        return {'native_sha256': 'a'*64, 'sources': {'hostile': '</script><script>alert(1)</script> & __BEHAVIOR_SCRIPT__ __BEHAVIOR_DATA__'}, 'limits': []}

    def test_payload_round_trip_and_script_boundary(self):
        data=self.fixture()
        with tempfile.TemporaryDirectory() as d, patch('build_behavior_viewer.load_evidence', return_value=data):
            out=Path(d)/'out'
            build(Path(d),Path(d),out)
            page=(out/'index.html').read_text()
            payload=re.search(r'<script id="behavior-data" type="application/json">(.*?)</script>', page,re.S)[1]
            self.assertEqual(json.loads(payload),data)
            self.assertNotIn('<script>alert',page)
            self.assertEqual(json.loads((out/'data.json').read_text()),data)
            self.assertEqual(json.loads((out/'provenance.json').read_text())['sources'],data['sources'])
            self.assertEqual(page.count('<script'),2)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as d, patch('build_behavior_viewer.load_evidence', return_value=self.fixture()):
            out=Path(d)/'out';out.mkdir();(out/'index.html').write_text('keep me')
            with self.assertRaises(FileExistsError):build(Path(d),Path(d),out)
            self.assertEqual((out/'index.html').read_text(),'keep me')

    def test_nonfinite_evidence_rejected(self):
        data=self.fixture();data['bad']=float('nan')
        with tempfile.TemporaryDirectory() as d, patch('build_behavior_viewer.load_evidence', return_value=data):
            with self.assertRaises(ValueError):build(Path(d),Path(d),Path(d)/'out')

if __name__=='__main__':unittest.main()
