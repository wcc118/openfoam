from pathlib import Path
import json,re,math,hashlib
import numpy as np
from scripts.cfd_interface_transfer import build_interface,face_displacements,verify_interface,point_forces
from scripts.modal_surface import generalized_forces
case=Path('/case');manifest=json.loads((case/'manifest.json').read_text());execution=json.loads((case/'execution.json').read_text())
assert execution['exit_code']==0 and execution['strict_sampled_quality_passed']
current=json.loads((case/'interface.json').read_text());reference=json.loads((case/'interface-reference.json').read_text());m=build_interface(current);r=build_interface(reference)
assert m.point_ids==r.point_ids and m.face_ids==r.face_ids
rows=np.vstack([np.loadtxt(case/f'processor{i}/final-face-loads.csv',delimiter=',') for i in range(4)])
lookup={int(row[0]):row for row in rows};assert len(lookup)==len(rows)==len(m.face_ids)
rows=np.array([lookup[i] for i in m.face_ids]);position_error=float(np.max(abs(rows[:,1:4]-m.centers)));assert position_error<1e-10,position_error
loads=rows[:,4:7];velocity=rows[:,7:10]
text=(case/'constant/wingMode').read_text();match=re.search(r'(?:^|\n)\s*(\d+)\s*\n\s*\(',text);body=text[match.end():];body=body[:body.rfind(')')];mode=np.fromstring(body.replace('(',' ').replace(')',' '),sep=' ').reshape(-1,3)
assert len(mode)==len(m.point_ids)
H=[(mode/.0001).tolist()]
report=verify_interface(current,loads.tolist(),H);assert report['passed'];(case/'actual-load-transfer.json').write_text(json.dumps(report,indent=2))
loadfile=dict(quantity='integrated_point_force',force_unit='N',face_ids=list(m.face_ids),forces_N=loads.tolist())
(case/'final-loads.json').write_text(json.dumps(loadfile))
work=np.loadtxt(case/'processor0/native-interface-work.csv',delimiter=',');assert len(work)==manifest['steps'] and work.shape[1]==11
assert np.isfinite(work).all() and np.all(np.diff(work[:,0])>0) and abs(work[-1,0]-.0005)<1e-12

def history(kind):
 files=sorted((case/'postProcessing/forces').glob('*/'+kind+'.dat'))
 assert files,kind
 result={}
 for file in files:
  for line in file.read_text().splitlines():
   if not line.strip() or line.lstrip().startswith('#'):continue
   a=np.fromstring(line.replace('(',' ').replace(')',' '),sep=' ')
   assert len(a)>=4 and np.isfinite(a).all()
   result[round(a[0],12)]=a[1:4]
 return result
forces=history('force');moments=history('moment')
force_error=max(float(np.max(abs(row[1:4]-forces[round(row[0],12)]))) for row in work)
moment_error=max(float(np.max(abs(row[4:7]-moments[round(row[0],12)]))) for row in work)
assert force_error<1e-9 and moment_error<1e-9,(force_error,moment_error)
assert np.max(abs(loads.sum(axis=0)-work[-1,1:4]))<1e-9
actual_power=float(np.sum(loads*velocity));assert abs(actual_power-work[-1,8])<1e-10
fd_velocity=np.array(face_displacements(r,mode.tolist()))*work[-1,10]/.0001
current_fd_velocity=np.array(face_displacements(m,mode.tolist()))*work[-1,10]/.0001
reference_power=float(np.sum(loads*fd_velocity));assert abs(reference_power-work[-1,9])<1e-10
qref=float(np.sum(loads*np.array(face_displacements(r,(mode/.0001).tolist()))));assert abs(qref-work[-1,7])<1e-9
assert np.max(abs(work[:,7]*work[:,10]-work[:,9]))<1e-10
expected_points=r.points+math.sin(2*math.pi*8.810675*float(current['time_s']))*mode
wall_error=float(np.max(np.linalg.norm(m.points-expected_points,axis=1)));assert wall_error<1e-9,wall_error
log=(case/'log.pimpleFoam').read_text()
courant=[float(x) for x in re.findall(r'^Courant Number mean: \S+ max: (\S+)',log,re.M)]
# Recover initial controlDict after the documented startFrom-only postprocessing edit.
initial=(case/'system/controlDict').read_text().replace('startFrom latestTime','startFrom startTime')
assert hashlib.sha256(initial.encode()).hexdigest()==manifest['inputs']['system/controlDict']
(case/'system/controlDict.initial.reconstructed').write_text(initial)
result=dict(scope='Short prescribed native-mode startup CFD diagnostic. Integrated forces are native dimensional fluid-on-wall forces. Partial non-closed path work is NOT aerodynamic damping.',dt_s=manifest['dt_s'],samples=len(work),end_time_s=float(work[-1,0]),cycle_fraction=float(work[-1,0]*8.810675),flow_initial_hashes=manifest['flow_initial_hashes'],native_force_history_max_error_N=force_error,native_moment_history_max_error_N_m=moment_error,final_face_center_max_error_m=position_error,final_wall_position_max_error_m=wall_error,maximum_fluid_Courant=max(courant) if courant else None,
 final_actual_wall_power_W=actual_power,final_reference_operator_power_W=reference_power,final_current_operator_power_W=float(np.sum(loads*current_fd_velocity)),max_wall_vs_reference_velocity_difference_m_s=float(np.max(np.linalg.norm(velocity-fd_velocity,axis=1))),max_current_vs_reference_operator_velocity_difference_m_s=float(np.max(np.linalg.norm(current_fd_velocity-fd_velocity,axis=1))),
 max_actual_vs_reference_power_difference_W=float(np.max(abs(work[:,8]-work[:,9]))),actual_wall_work_right_endpoint_J=float(np.sum(work[:,8])*manifest['dt_s']),reference_modal_work_right_endpoint_J=float(np.sum(work[:,9])*manifest['dt_s']),work_quadrature='right endpoint power*dt from0 to0.0005s; imposed sine starts with nonzero velocity; no cycle closure',
 final_modal_force_current_operator_N=report['generalized_forces_N'][0],final_modal_force_reference_operator_N=qref,
 transfer_passed=report['passed'],strict_sampled_quality_passed=execution['strict_sampled_quality_passed'],mesh_samples=execution['mesh_ok_count'],native_force_field_lines=[line.strip() for line in log.splitlines() if 'nativeInterfaceWork forceField=' in line][:2],implicit_feedback_ready=False,remaining=['native shell interpolation full transpose/resultant-moment audit','movingWallVelocity flux correction versus chosen structural work operator','periodic startup removal','time/coupling sensitivity beyond this short pilot','viscous mesh qualification','checkpoint rollback coupled pilot'])
# Audit the existing native shell projection separately from the passing face/point stage.
projection_source=Path('/mapping/map_motion_nearest_caps.py')
assert hashlib.sha256(projection_source.read_bytes()).hexdigest()=='c84ea5efb30d3e7ccf43c474f3d81c1e0093a34dd4af2dd5be75c03eb3f5ce4a'
ns={'__file__':str(projection_source)}
exec(compile(projection_source.read_text().split('# Identity test')[0],str(projection_source),'exec'),ns)
ns['mode']=ns['xyz'].copy()
projected,distance=ns['mapping'](r.points)
error=projected-r.points
fp=np.array(point_forces(m,loads.tolist()))
synthetic=np.column_stack((1+r.points[:,1]**2, r.points[:,0]+.2, .3+r.points[:,2]))*1e-4
result['native_shell_projection_audit']=dict(scope='Linear-coordinate reproduction of retained translation-only shell projection. Implied resultant-moment defect for its transpose; no offset couples are included.',source_sha256=hashlib.sha256(projection_source.read_bytes()).hexdigest(),max_reference_coordinate_error_m=float(np.max(np.linalg.norm(error,axis=1))),coordinate_reproduction_tolerance_m=1e-10,linear_coordinate_reproduction_passed=bool(np.max(np.linalg.norm(error,axis=1))<1e-10),actual_load_implied_moment_defect_N_m=np.sum(np.cross(error,fp),axis=0).tolist(),synthetic_point_force_implied_moment_defect_N_m=np.sum(np.cross(error,synthetic),axis=0).tolist(),distance_guard_m=.001,distance_guard_passed=bool(max(distance)<.001),interpretation='Distance acceptance does not imply exact rigid-rotation/moment reproduction; require an explicit offset treatment before claiming a conservative full shell interface.')
(case/'pilot-analysis.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
