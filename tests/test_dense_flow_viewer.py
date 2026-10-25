import copy,json,math,subprocess,sys,tempfile,unittest
from pathlib import Path
from scripts import build_dense_flow_viewer as m

def fixture():
 points=[];slices=[]
 for axis,pos,ua,va in [(1,0,0,2),(0,.2,1,2)]:
  values=[-.03+i*.0025 for i in range(25)];indices=[]
  for v in values:
   for u in values:
    p=[0,0,0];p[axis]=pos;p[ua]=u;p[va]=v;indices.append(len(points));points.append(p)
  slices.append(dict(id=str(axis),label=f'Plane {axis}',normal_axis=axis,position_m=pos,u_axis=ua,v_axis=va,u_values=values,v_values=values,indices=indices))
 cases=[]
 for alpha in [0,4]:
  inf=[30*math.cos(math.radians(alpha)),0,30*math.sin(math.radians(alpha))]
  cases.append(dict(id=str(alpha),alpha_deg=alpha,freestream_velocity_m_s=inf,steady_iteration=100,solver='synthetic',source_revision='test',mesh_sha256='a'*64,field_sha256='b'*64,status='diagnostic_only',limitations=['Synthetic fixture, no CFD result'],U=[[inf[0],p[2]*60,inf[2]+p[1]*40+alpha*.2] for p in points],p=[p[0]*100+alpha*10 for p in points]))
 return dict(schema_version=1,kind='steady_angle_cases',reference=dict(speed_m_s=30,chord_m=.1,reference_pressure_kinematic=0,dynamic_pressure_kinematic=450),wing=dict(points=[[.16,-.04,0],[.24,-.04,0],[.20,.04,0]],triangles=[[0,1,2]]),samples=dict(points=points,groups=['midspan']*625+['wake']*625),cases=cases,slices=slices)

class DenseTests(unittest.TestCase):
 def test_valid_and_ranges(self):
  d=fixture();m.validate(d);r=m.derived_ranges(d);self.assertEqual(r['crossflow'][0],0);self.assertAlmostEqual(r['crossflow'][1],math.hypot(1.8,2))
 def test_mask_and_arbitrary_axes(self):
  d=fixture();d['slices'][0]['indices'][0]=-1;m.validate(d)
  s=d['slices'][0];s['normal_axis'],s['v_axis']=s['v_axis'],s['normal_axis']
  for p in d['samples']['points'][:625]:p[1],p[2]=p[2],p[1]
  m.validate(d)
 def test_invalid_slice_contract(self):
  mutations=[lambda d:d.pop('slices'),lambda d:d.update(slices=[]),lambda d:d['slices'][0].update(label=' '),lambda d:d['slices'][1].update(id='1'),lambda d:d['slices'][0].update(normal_axis=True),lambda d:d['slices'][0].update(u_axis=1),lambda d:d['slices'][0].update(position_m=float('nan')),lambda d:d['slices'][0].update(u_values=[0,0]),lambda d:d['slices'][0]['u_values'].__setitem__(0,True),lambda d:d['slices'][0]['indices'].__setitem__(0,True),lambda d:d['slices'][0]['indices'].__setitem__(0,-2),lambda d:d['slices'][0]['indices'].__setitem__(0,999),lambda d:d['slices'][0]['indices'].__setitem__(1,0),lambda d:d['slices'][0]['indices'].pop(),lambda d:d['samples']['points'][0].__setitem__(0,.5)]
  for mutate in mutations:
   with self.subTest(mutate=mutate):
    d=fixture();mutate(d)
    with self.assertRaises(ValueError):m.validate(d)
 def test_base_contract_reused(self):
  for mutate in [lambda d:d['cases'][0].update(U=[]),lambda d:d['cases'][0].update(p=[]),lambda d:d['cases'][1].update(alpha_deg=0),lambda d:d['samples']['points'][0].__setitem__(0,True),lambda d:d['reference'].update(dynamic_pressure_kinematic=-1)]:
   d=fixture();mutate(d)
   with self.assertRaises(ValueError):m.validate(d)
 def test_injection_and_no_overwrite(self):
  d=fixture();d['slices'][0]['label']='</script><script>window.PWNED=1</script>';html=m.build_html(d);self.assertNotIn(d['slices'][0]['label'],html)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'in.json').write_text(json.dumps(d));args=[sys.executable,str(Path(m.__file__)), '--input',str(p/'in.json'),'--output',str(p/'out.html')]
   a=subprocess.run(args,capture_output=True);self.assertEqual(a.returncode,0,a.stderr);before=(p/'out.html').read_bytes();b=subprocess.run(args,capture_output=True);self.assertNotEqual(b.returncode,0);self.assertEqual(before,(p/'out.html').read_bytes())
