"""UVLM model at the CFD release pose for a matched imposed-motion comparison.

Uses the same native first-mode coordinate (mean tip z in metres), cambered
surface and 30m/s speed. CFD is a viscous closed surface; UVLM is an inviscid
camber surface, linearized about this prescribed loaded geometry. No claim
that this reference is UVLM structural equilibrium.
"""
from pathlib import Path
import json,hashlib
import numpy as np
from scipy import linalg,sparse
from scipy.sparse.linalg import splu
import shell_loaded_equilibrium as eq
from modal_uvlm_explore import geometry,state_space
base=Path('/results');out=base/'prescribed-uvlm';out.mkdir(exist_ok=False)
eq.M,eq.N,eq.WAKE=8,16,8
speed=30.;physical_dt=.00005;dt=physical_dt*speed;qref=.01492455473113748;rho=1.2250532683653954
native=np.load(base/'native-modal.npz');tip=np.isclose(native['xyz'][:,1],native['xyz'][:,1].max());tipfactor=native['phi'][0,tip,2].mean()/np.sqrt(2)
eq.cout_utils.start_writer();eq.cout_utils.cout_wrap.initialise(False,True,str(out),'assembly.log')
try:
 zeta,H,omega,chord,source=geometry(base,'shell',8,16,1);h=H.reshape(-1,1)/tipfactor
 ts=eq.static_state(zeta+(h[:,0]*qref).reshape(zeta.shape),chord,dt)
 ts.forces[0]*=rho/ts.rho;ts.rho=rho
 Q0=float(speed**2*(h.T@ts.forces[0][:3].reshape(-1))[0])
 aero=eq.linuvlm.Dynamic(ts,dynamic_settings=dict(dt=dt,integr_order=2,density=rho,remove_predictor=False,use_sparse=False,cfl1=False));aero.assemble_ss(wake_prop_settings=dict(cfl1=False,dt=dt))
 a,b,c,d=aero.SS.get_mats();nv=len(h)
 b=np.hstack([b[:,:nv]@h,b[:,nv:2*nv]@h]);c=h.T@c;d=np.hstack([h.T@d[:,:nv]@h,h.T@d[:,nv:2*nv]@h])
 rom=eq.Krylov();rom.initialise(dict(algorithm='mimo_rational_arnoldi',r=12,single_side='observability',frequency=[0.0],print_info=False))
 ar,br,cr,dr=[np.real_if_close(x,tol=1000) for x in rom.run(state_space(a,b,c,d,dt)).get_mats()]
 checks=[]
 for hz in [0.,8.810675,20.,50.]:
  z=np.exp(2j*np.pi*hz*physical_dt);full=z*c@splu(z*sparse.eye(len(a),format='csc')-sparse.csc_matrix(a)).solve(b)+d;red=z*cr@linalg.solve(z*np.eye(len(ar))-ar,br)+dr
  checks.append(dict(frequency_hz=hz,relative_error=float(linalg.norm(full-red)/max(linalg.norm(full),1e-30))))
 assert all(np.isrealobj(x) for x in (ar,br,cr,dr))
 np.savez_compressed(out/'model.npz',A=ar,B=br,C=cr,D=dr,dt_s=physical_dt,speed_m_s=speed,Q0_N=Q0,qref_m=qref)
 report=dict(scope=__doc__,qref_m=qref,Q0_N=Q0,dt_s=physical_dt,speed_m_s=speed,rho_kg_m3=rho,full_states=len(a),reduced_states=len(ar),transfer_checks=checks,aero_rom_radius=float(max(abs(linalg.eigvals(ar)))),camber_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),native_sha256=hashlib.sha256((base/'native-modal.npz').read_bytes()).hexdigest())
 (out/'assessment.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
finally:eq.cout_utils.finish_writer()
