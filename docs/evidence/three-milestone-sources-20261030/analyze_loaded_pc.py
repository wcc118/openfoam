from pathlib import Path
import json,numpy as np,re,hashlib
root=Path('/home/foam/projects/openfoam/runs')
results=[]
for variant in ('pilot2','explicit','half','implicit'):
 case=root/('issue38-loaded-'+variant+'-20261030')
 if not (case/'execution.json').exists():continue
 execution=json.loads((case/'execution.json').read_text())
 original_execution=execution;recovery=None
 if execution.get('exit_code')!=0:
  rp=case/'postprocess-recovery.json'
  if not rp.exists():print(variant,execution);continue
  recovery=json.loads(rp.read_text())
  if not (recovery.get('passed') is True and recovery.get('exit_code')==0 and recovery.get('solver_return_codes')=={'solid':0,'fluid':0}):continue
  assert recovery['history_sha256']==hashlib.sha256((case/'solid/result/modal-history.json').read_bytes()).hexdigest()
  execution=recovery
 h=json.loads((case/'solid/result/modal-history.json').read_text());rows=h['rows'];reference_q=h['settings'].get('reference_q_m',0.);assets=np.load(case/'solid/interface.npz')
 full_rows=rows;analysis_end=float(recovery['analysis_end_time_s']) if recovery else rows[-1]['time_s']
 rows=[r for r in rows if r['time_s']<=analysis_end+1e-10]
 assert rows and abs(rows[-1]['time_s']-analysis_end)<1e-9
 raw=np.loadtxt(case/'fluid/processor0/native-interface-work.csv',delimiter=',');q=np.array([r['q_m'] for r in rows]);times=np.array([r['time_s'] for r in rows]);forces=np.array([r['force_N'] for r in rows]);Q=np.array([r['Q_N'] for r in rows]);lookup={round(float(row[0]),12):row for row in raw};matched=np.array([lookup[round(t,12)] for t in times])
 e=json.loads((case/'fluid/interface.json').read_text());assert tuple(e['point_ids'])==tuple(assets['point_ids'])
 u=np.array(e['points_m'])-assets['points'];hp=assets['point_mode'];increment=float(np.sum(hp*u)/np.sum(hp*hp));fit=increment+reference_q;resid=float(np.max(abs(u-hp*increment)))
 log=(case/('fluid/log.quality.recovery' if recovery else 'fluid/log.quality')).read_text();fluidlog=(case/'fluid/log.pimpleFoam').read_text();co=[float(x) for x in re.findall(r'Courant Number mean: .*? max: ([^\n]+)',fluidlog)]
 result=dict(variant=variant,execution=execution,original_execution=original_execution,postprocessing_recovered=bool(recovery),analysis_end_time_s=analysis_end,full_history_end_time_s=full_rows[-1]['time_s'],full_history_windows=len(full_rows),saved_field_time_s=analysis_end,completed=h['completed'],windows=len(rows),rollbacks=h['rollbacks'],final_q_m=q[-1],final_v_m_s=rows[-1]['v_m_s'],final_Q_N=Q[-1],final_native_force_N=matched[-1,1:4].tolist(),max_native_force_difference_N=float(np.max(abs(forces-matched[:,1:4]))),max_native_modal_force_difference_N=float(np.max(abs(Q-matched[:,7]))),final_saved_wall_fitted_q_m=fit,final_saved_wall_shape_residual_m=resid,wall_vs_last_solid_q_m=float(fit-q[-1]),wall_vs_previous_solid_q_m=float(fit-q[-2]),max_structural_energy_defect_J=max(abs(r['structural_energy_defect_J']) for r in rows),structural_work_J=sum(r['structural_load_work_J'] for r in rows),right_endpoint_wall_work_J=float(sum(matched[:,8]*np.array([r['dt_s'] for r in rows]))),max_Courant=max(co),max_coupling_iterations=max(r['iteration'] for r in rows),all_converged_count=(case/'solid/log.solid').read_text().count('All converged'),mesh_ok_count=log.count('Mesh OK.'),mesh_failed='Failed' in log,initial_manifest=json.loads((case/'manifest.json').read_text()),rows=rows,native_work_rows=matched.tolist())
 (case/'assessment.json').write_text(json.dumps(result,indent=2));results.append(result)
comparable=[r for r in results if r['variant'] in ('explicit','half')]
if len(comparable)==2:
 a,b=comparable;tb={round(r['time_s'],12):r for r in b['rows']};delta=[(r,tb[round(r['time_s'],12)]) for r in a['rows'] if round(r['time_s'],12) in tb];comparison=dict(initial_fields_identical=a['initial_manifest']['initial_fields']==b['initial_manifest']['initial_fields'],max_common_q_difference_m=max(abs(x['q_m']-y['q_m']) for x,y in delta),common_end_time_s=delta[-1][0]['time_s'],final_q_relative_difference=abs(delta[-1][0]['q_m']-delta[-1][1]['q_m'])/abs(delta[-1][1]['q_m']),max_common_Q_difference_N=max(abs(x['Q_N']-y['Q_N']) for x,y in delta),scope='Loaded release timestep sensitivity; inspect oscillations and fitting before classifying damping')
else:comparison={}
out=dict(runs=results,comparison=comparison)
p=Path('/mnt/g/projects/openfoam/build/issue38-loaded-assessment.json');p.write_text(json.dumps(out,indent=2));print(json.dumps({**out,'runs':[{k:v for k,v in r.items() if k not in ('rows','native_work_rows','initial_manifest','execution')} for r in results]},indent=2))
