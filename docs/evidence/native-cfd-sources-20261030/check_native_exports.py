"""Primary native ordering/motion checks; run as a module beside pinned scripts."""
from pathlib import Path
import hashlib,json,re,math
import numpy as np
from scripts.cfd_interface_transfer import build_interface,point_forces,verify_interface
case=Path('/case');mesh=Path('/mesh');motion=Path('/motion')
serial=json.loads((case/'interface.json').read_text());m=build_interface(serial)
index={pid:i for i,pid in enumerate(m.point_ids)};findex={fid:i for i,fid in enumerate(m.face_ids)}
f=(1e-4*np.column_stack((1+np.sin(m.centers[:,0]+m.centers[:,1]),np.cos(m.centers[:,1]),.5+m.centers[:,2]))).tolist()
expected=np.array(point_forces(m,f));assembled=np.zeros_like(expected);seen_faces=set();seen_points=set();rows=[]
def cycle_key(values):
 start=values.index(min(values));return values[start:]+values[:start]
for rank in range(4):
 data=json.loads((case/f'processor{rank}/interface.json').read_text());local=build_interface(data)
 assert data['rank']==rank and data['time_s']==serial['time_s']
 ip=np.array([index[i] for i in local.point_ids]);jf=np.array([findex[i] for i in local.face_ids])
 assert not (seen_faces&set(local.face_ids));seen_faces.update(local.face_ids);seen_points.update(local.point_ids)
 ep=float(np.max(np.abs(local.points-m.points[ip])));ec=float(np.max(np.abs(local.centers-m.centers[jf])));ea=float(np.max(np.abs(local.areas-m.areas[jf])))
 assert max(ep,ec)<1e-12 and ea<1e-12,(rank,ep,ec,ea)
 for face in data['faces']:
  original=serial['faces'][findex[face['id']]]
  a=[data['point_ids'][i] for i in face['point_indices']];b=[serial['point_ids'][i] for i in original['point_indices']]
  assert cycle_key(a)==cycle_key(b)
 lf=[f[i] for i in jf];np.add.at(assembled,ip,np.array(point_forces(local,lf)))
 rows.append(dict(rank=rank,point_count=len(ip),face_count=len(jf),max_point_error_m=ep,max_center_error_m=ec,max_area_error_m2=ea))
assert len(seen_faces)==len(m.face_ids) and len(seen_points)==len(m.point_ids)
error=float(np.max(np.abs(assembled-expected)));assert error<1e-12,error
point_file=np.loadtxt(mesh/'wing-points.dat',skiprows=1)
assert point_file[:,0].astype(int).tolist()==list(m.point_ids)
point_error=float(np.max(abs(point_file[:,1:]-m.points)));assert point_error<1e-10,point_error

def vectors(path):
 s=path.read_text();s=re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
 match=re.search(r'(?:^|\n)\s*(\d+)\s*\n\s*\(',s)
 if not match:raise ValueError(str(path))
 n=int(match[1]);body=s[match.end():];end=body.rfind(')');body=body[:end]
 data=np.fromstring(body.replace('(',' ').replace(')',' ').replace(';',' '),sep=' ')
 assert data.size==n*3,(path,data.size,n);return data.reshape(n,3)
mode=vectors(mesh/'constant/wingMode');assert mode.shape==m.points.shape
mode_doc=dict(point_ids=list(m.point_ids),basis_units='dimensionless',coordinate_units='m',shapes=[(mode/.0001).tolist()],normalization='mean native tip z =1; q is prescribed mean tip displacement in m',frequency_hz=8.810675,source_native_sha256=json.loads((mesh/'motion-map-report.json').read_text())['native_sha256'])
(case/'native-mode.json').write_text(json.dumps(mode_doc))
native=verify_interface(serial,f,mode_doc['shapes']);assert native['passed'];(case/'native-modal-transfer.json').write_text(json.dumps(native,indent=2))
original=vectors(motion/'constant/polyMesh/points');ids=np.array(m.point_ids);times=[];returns=[]
for p in sorted((p for p in motion.iterdir() if p.is_dir() and re.fullmatch(r'[0-9.eE+-]+',p.name)),key=lambda p:float(p.name)):
 path=p/'polyMesh/points'
 if not path.exists():continue
 t=float(p.name);phase=8.810675*t;points=vectors(path);assert points.shape==original.shape
 expected_wall=original[ids]+math.sin(2*math.pi*phase)*mode
 error=float(np.max(np.linalg.norm(points[ids]-expected_wall,axis=1)));assert error<1e-9,(t,error)
 times.append(dict(time_s=t,phase_cycles=phase,max_wall_position_error_m=error,points_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 if abs(phase-round(phase))<1e-10:
  returns.append(dict(cycle=round(phase),max_interior_return_offset_m=float(np.max(np.linalg.norm(points-original,axis=1)))))
assert len(times)==32 and abs(times[-1]['phase_cycles']-2)<1e-10 and len(returns)==2
report=dict(scope='Actual native serial/4-rank geometry, point order, force transpose assembly and stored native-mode wall positions. Loads are synthetic; no fluid/damping inference.',ranks=rows,unique_points=len(seen_points),unique_faces=len(seen_faces),max_parallel_force_assembly_difference_N=float(np.max(np.abs(assembled-expected))),max_point_map_position_difference_m=point_error,observed_motion_samples=times,cycle_returns=returns,passed=True)
(case/'native-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='observed_motion_samples'},indent=2))
