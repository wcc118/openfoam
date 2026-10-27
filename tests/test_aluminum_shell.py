import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from collections import Counter

spec=importlib.util.spec_from_file_location('shell',Path(__file__).parents[1]/'scripts/generate_aluminum_shell.py')
shell=importlib.util.module_from_spec(spec)
spec.loader.exec_module(shell)

class ShellTests(unittest.TestCase):
    def test_surface_and_loads(self):
        v,q,loads,decks,m=shell.model()
        n=m['perimeter_nodes']
        self.assertEqual(min(p[1] for p in v),0)
        self.assertEqual(max(p[1] for p in v),1.2192)
        self.assertEqual(len(set(v)),len(v))
        edges=Counter(tuple(sorted((a,b))) for quad in q for a,b in zip(quad,quad[1:]+quad[:1]))
        self.assertEqual(sum(c==1 for c in edges.values()),2*n) # uncapped root and tip
        self.assertTrue(all(c in (1,2) for c in edges.values()))
        signed_area=sum(v[i][0]*v[(i+1)%n][2]-v[(i+1)%n][0]*v[i][2] for i in range(n))/2
        self.assertGreater(signed_area,0)
        area=0
        for a,b,c,d in q:
            a,b,c,d=[v[i-1] for i in (a,b,c,d)]
            self.assertEqual(a[1],b[1]); self.assertEqual(c[1],d[1])
            self.assertEqual((a[0],a[2]),(d[0],d[2]))
            area+=math.dist(a,b)*math.dist(b,c)
        self.assertAlmostEqual(m['mass_kg'],area*.00127*2810,12)
        for name,F,M in [('bending',(0,0,1),(1.2192,0,0)),('torsion',(0,0,0),(0,1,0))]:
            for a,b in zip(m['resultants'][name]['force_N'],F): self.assertAlmostEqual(a,b,12)
            for a,b in zip(m['resultants'][name]['moment_Nm'],M): self.assertAlmostEqual(a,b,12)
            self.assertEqual(decks[name].count('SPC1,'),n)
        self.assertNotIn('CHEXA',decks['modal'])
        self.assertIn('EIGRL,3,,,10',decks['modal'])

    def test_dimensions_and_no_overwrite(self):
        for key,value in [('span',float('nan')),('thickness',0),('points',3),('sections',1),('thickness',.01)]:
            with self.assertRaises(ValueError): shell.model(**{key:value})
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'case'; shell.generate(path)
            with self.assertRaises(FileExistsError): shell.generate(path)
        a=shell.model()[4]; b=shell.model(span=2*1.2192)[4]
        self.assertAlmostEqual(b['mass_kg'],2*a['mass_kg'])

if __name__=='__main__': unittest.main()
