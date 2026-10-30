"""Primary-owned loaded cambered-wing design deltas; pinned native/UVLM inputs."""
from pathlib import Path
import json,time,traceback,hashlib,os
import numpy as np
from scipy import optimize,linalg
import shell_loaded_equilibrium as eq
from shell_loaded_speed_sweep import assemble
from modal_uvlm_explore import geometry
from instability_demo import spectrum,history
base=Path('/results');out=base/'loaded-deltas-half-dt';out.mkdir(exist_ok=False)
eq.M,eq.N,eq.WAKE=8,16,8
cases=[(10,30.,1.),(10,20.,.01),(10,25.,.01)]
native=np.load(base/'native-modal.npz');xyz=native['xyz'];tip=np.isclose(xyz[:,1],xyz[:,1].max());reports=[]
eq.cout_utils.start_writer();eq.cout_utils.cout_wrap.initialise(False,True,str(out),'assembly.log')
try:
 for nm,speed,factor in cases:
  tag=f'n{nm}-V{speed:g}-K{factor:g}';folder=out/tag;folder.mkdir();start=time.monotonic();report=dict(tag=tag,speed_m_s=speed,modes=nm,torsional_stiffness_factor=factor,scope='Clamped cambered loaded reference, linear native stiffness; fifth modal stiffness varied only. Not a physical redesign or flight flutter limit.',assumed_damping_ratio=0.,cfl=.0625,M=8,N_per_half=16,wake_chords=8)
  try:
   zeta,H,omega,chord,source=geometry(base,'shell',8,16,nm);h=H.reshape(-1,nm);dt=.0625*chord/8;phi=native['phi'][:nm]
   if nm>4:omega[4]*=np.sqrt(factor)
   report['frequencies_hz']=(omega/(2*np.pi)).tolist();report['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
   iterations=[]
   def residual(q):
    ts=eq.static_state(zeta+(h@q).reshape(zeta.shape),chord,dt)
    Q=speed**2*h.T@ts.forces[0][:3].reshape(-1)
    r=q-Q/omega**2;iterations.append(float(np.max(abs(r))));return r
   sol=optimize.root(residual,np.zeros(nm),tol=1e-9);residual(sol.x);qeq=sol.x
   if not sol.success or iterations[-1]>1e-8:raise RuntimeError('loaded equilibrium did not converge: '+str(sol.message))
   disp=np.einsum('m,mij->ij',qeq,phi)/np.sqrt(2);maxdisp=float(np.max(abs(disp)))
   report.update(equilibrium_q=qeq.tolist(),equilibrium_tip_z_m=float(disp[tip,2].mean()),equilibrium_max_displacement_m=maxdisp,static_residual_max=iterations[-1],static_iterations=len(iterations))
   if maxdisp>.05:raise RuntimeError('loaded pose exceeds50mm diagnostic bound')
   ts=eq.static_state(zeta+(h@qeq).reshape(zeta.shape),chord,dt)
   mats,checks=assemble(ts,h,dt,omega,speed,check_frequencies=[0.,omega[0],omega[4],omega[-1]])
   report['aero_checks']=checks;report['poles']=spectrum(mats,omega,dt,speed)
   kick=np.zeros(nm);kick[0]=.0005/(phi[0,tip,2].mean()/np.sqrt(2))
   hist=history(mats,omega,dt,speed,phi.transpose(1,2,0).reshape(-1,nm)/np.sqrt(2),kick,seconds=1.2,guard=max(.001,.05-maxdisp))
   report['history']={k:v for k,v in hist.items() if k!='frames_time_and_q'}
   report['status']='guarded_growth' if hist['stopped_at_50mm_guard'] else 'completed'
   frames=np.array(hist['frames_time_and_q']);frames[:,1:]+=qeq
   np.savez_compressed(folder/'model.npz',A=mats[0],B=mats[1],C=mats[2],D=mats[3],omega=omega,dt=dt,H=H,qeq=qeq,zeta=zeta)
   (folder/'motion.json').write_text(json.dumps(dict(frames_time_and_q=frames.tolist(),reference_q=qeq.tolist(),speed_m_s=speed,mode_count=nm)))
  except Exception as ex:report.update(status='failed',error=str(ex),traceback=traceback.format_exc())
  report['elapsed_s']=time.monotonic()-start;(folder/'assessment.json').write_text(json.dumps(report,indent=2,allow_nan=False));reports.append(report);(out/'summary.json').write_text(json.dumps(reports,indent=2,allow_nan=False));print('CASE',json.dumps(report),flush=True)
finally:eq.cout_utils.finish_writer()
