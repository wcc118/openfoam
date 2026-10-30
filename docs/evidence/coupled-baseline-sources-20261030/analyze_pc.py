from pathlib import Path
import json,numpy as np,re,hashlib
root=Path('/home/foam/projects/openfoam/runs')
results=[]
for variant in ('explicit','half','implicit'):
 case=root/('issue38-coupled-'+variant+'-20261030')
 if not (case/'execution.json').exists():continue
 execution=json.loads((case/'execution.json').read_text())
 if execution.get('exit_code')!=0:print(variant,execution);continue
 h=json.loads((case/'solid/result/modal-history.json').read_text());rows=h['rows'];assets=np.load(case/'solid/interface.npz')
 raw=np.loadtxt(case/'fluid/processor0/native-interface-work.csv',delimiter=',');q=np.array([r['q_m'] for r in rows]);times=np.array([r['time_s'] for r in rows]);forces=np.array([r['force_N'] for r in rows]);Q=np.array([r['Q_N'] for r in rows]);lookup={round(float(row[0]),12):row for row in raw};matched=np.array([lookup[round(t,12)] for t in times])
 e=json.loads((case/'fluid/interface.json').read_text());assert tuple(e['point_ids'])==tuple(assets['point_ids'])
 u=np.array(e['points_m'])-assets['points'];hp=assets['point_mode'];fit=float(np.sum(hp*u)/np.sum(hp*hp));resid=float(np.max(abs(u-hp*fit)))
 log=(case/'fluid/log.quality').read_text();fluidlog=(case/'fluid/log.pimpleFoam').read_text();co=[float(x) for x in re.findall(r'Courant Number mean: .*? max: ([^\n]+)',fluidlog)]
 result=dict(variant=variant,execution=execution,completed=h['completed'],windows=len(rows),rollbacks=h['rollbacks'],final_q_m=q[-1],final_v_m_s=rows[-1]['v_m_s'],final_Q_N=Q[-1],final_native_force_N=matched[-1,1:4].tolist(),max_native_force_difference_N=float(np.max(abs(forces-matched[:,1:4]))),max_native_modal_force_difference_N=float(np.max(abs(Q-matched[:,7]))),final_saved_wall_fitted_q_m=fit,final_saved_wall_shape_residual_m=resid,wall_vs_last_solid_q_m=float(fit-q[-1]),wall_vs_previous_solid_q_m=float(fit-q[-2]),max_structural_energy_defect_J=max(abs(r['structural_energy_defect_J']) for r in rows),structural_work_J=sum(r['structural_load_work_J'] for r in rows),right_endpoint_wall_work_J=float(sum(matched[:,8]*np.array([r['dt_s'] for r in rows]))),max_Courant=max(co),max_coupling_iterations=max(r['iteration'] for r in rows),all_converged_count=(case/'solid/log.solid').read_text().count('All converged'),mesh_ok_count=log.count('Mesh OK.'),mesh_failed='Failed' in log,initial_manifest=json.loads((case/'manifest.json').read_text()),rows=rows,native_work_rows=matched.tolist())
 (case/'assessment.json').write_text(json.dumps(result,indent=2));results.append(result)
if len(results)>=2:
 a,b=results[:2];tb={round(r['time_s'],12):r for r in b['rows']};delta=[(r,tb[round(r['time_s'],12)]) for r in a['rows']];comparison=dict(initial_fields_identical=a['initial_manifest']['initial_fields']==b['initial_manifest']['initial_fields'],max_common_q_difference_m=max(abs(x['q_m']-y['q_m']) for x,y in delta),final_q_relative_difference=abs(a['final_q_m']-b['final_q_m'])/abs(b['final_q_m']),max_common_Q_difference_N=max(abs(x['Q_N']-y['Q_N']) for x,y in delta),scope='Short startup sensitivity only, not periodic damping convergence')
else:comparison={}
out=dict(runs=results,comparison=comparison)
p=Path('/mnt/g/projects/openfoam/build/issue38-coupled-assessment.json');p.write_text(json.dumps(out,indent=2));print(json.dumps({**out,'runs':[{k:v for k,v in r.items() if k not in ('rows','native_work_rows','initial_manifest','execution')} for r in results]},indent=2))
