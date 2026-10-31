"""Apply the recorded CFD wall motion to a UVLM model at the same initial pose.

CFD explicit Fluid-first coupling uses the previous accepted structural q.
Replay that wall path with linear interpolation and interval-constant velocity;
this is a prescribed aerodynamic comparison, not another free response.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
p=argparse.ArgumentParser();p.add_argument('model',type=Path);p.add_argument('history',type=Path);p.add_argument('output',type=Path);p.add_argument('--end-time',type=float);args=p.parse_args()
h=json.loads(args.history.read_text());assert h['completed'];s=h['settings'];rows=h['rows'];d=np.load(args.model)
recorded_end=rows[-1]['time_s']
if args.end_time is not None:
 assert np.isfinite(args.end_time) and 0<args.end_time<=recorded_end+1e-9
 rows=[r for r in rows if r['time_s']<=args.end_time+1e-10]
 assert rows and abs(rows[-1]['time_s']-args.end_time)<1e-9
assert s['coupling']=='explicit','Only exact explicit one-window lag is supported.'
assert abs(s['reference_q_m']-float(d['qref_m']))<1e-12
initial=s['initial_q_m'];assert abs(initial-float(d['qref_m']))<1e-12 and s.get('initial_v_m_s',0.)==0.,'Replay requires release from rest at the model reference pose.'
t=np.r_[0.,[r['time_s'] for r in rows]];q=np.r_[initial,initial,[r['q_m'] for r in rows[:-1]]]
assert len(t)==len(q) and np.all(np.diff(t)>0)
Q_cfd=np.r_[s['initial_force_N'],[r['Q_N'] for r in rows]]
step=float(d['dt_s']);speed=float(d['speed_m_s']);qref=float(d['qref_m']);Q0=float(d['Q0_N']);a,b,c,dm=[d[k] for k in 'ABCD']
assert np.max(abs(t/step-np.round(t/step)))<1e-8
query=np.arange(round(t[-1]/step)+1)*step
qp=np.interp(query,t,q);interval=np.clip(np.searchsorted(t,query,side='left')-1,0,len(t)-2)
velocity=(np.diff(q)/np.diff(t))[interval];velocity[0]=0.
u=np.column_stack([qp-qref,velocity/speed]);state=np.zeros(len(a));loads=[]
for k in range(len(query)):
 if k:state=a@state+b@u[k]
 loads.append(Q0+speed**2*float((c@state+dm@u[k])[0]))
loads=np.array(loads);assert np.isfinite(loads).all()
indices=np.round(t/step).astype(int);matched=loads[indices];delta_cfd=Q_cfd-Q_cfd[0];delta_uvlm=matched-Q0;mask=t>=.05
if np.count_nonzero(mask)<4:mask=t>0
metrics=dict(scope=__doc__,recorded_end_time_s=recorded_end,requested_end_time_s=args.end_time,analysis_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),CFD_initial_Q_N=float(Q_cfd[0]),UVLM_initial_Q_N=Q0,steady_relative_difference=Q0/Q_cfd[0]-1.,CFD_wall_motion_range_m=[float(q.min()),float(q.max())],comparison_start_s=float(t[mask][0]),comparison_end_s=float(t[-1]),delta_load_rms_difference_N=float(np.sqrt(np.mean((delta_cfd[mask]-delta_uvlm[mask])**2))),CFD_delta_Q_range_N=[float(delta_cfd.min()),float(delta_cfd.max())],UVLM_delta_Q_range_N=[float(delta_uvlm.min()),float(delta_uvlm.max())],CFD_incremental_trapezoid_work_J=float(np.sum(.5*(delta_cfd[1:]+delta_cfd[:-1])*np.diff(q))),UVLM_incremental_trapezoid_work_J=float(np.sum(.5*(delta_uvlm[1:]+delta_uvlm[:-1])*np.diff(q))),model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),history_sha256=hashlib.sha256(args.history.read_bytes()).hexdigest(),model_states=len(a),limitations=f'Different viscous/closed-surface versus inviscid/camber-surface physics and spatial discretizations. Both use the CFD initial pose and replayed wall motion. UVLM is linearized, fixed wake, {len(a)}-state ROM; see frequency-domain reduction checks. A nonperiodic release work integral is not a periodic damping coefficient.')
args.output.mkdir(exist_ok=False)
(args.output/'summary.json').write_text(json.dumps(metrics,indent=2));np.savez_compressed(args.output/'history.npz',time_s=t,wall_q_m=q,CFD_Q_N=Q_cfd,UVLM_Q_N=matched)
print(json.dumps(metrics,indent=2))
