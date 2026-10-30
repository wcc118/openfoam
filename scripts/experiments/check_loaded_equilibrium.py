"""Independent finite-difference static slope and physical-history checks."""
from pathlib import Path
import json
import numpy as np
from scipy import linalg, signal
from shell_loaded_equilibrium import static_state, geometry, M,N,NM,V

base=Path('/results'); reports={}
for tag in ('baseline','thicker'):
    out=base/(tag+'-equilibrium')
    model=np.load(out/'loaded-model.npz'); q=model['qeq']
    zeta,H,omega,chord,_=geometry(base/tag,'shell',M,N,NM); h=H.reshape(-1,NM)
    dt=float(model['dt']); J=np.empty((NM,NM))
    for j in range(NM):
        # Each perturbation produces at most one micrometre of lattice motion.
        eps=1e-6/np.max(abs(h[:,j])); f=[]
        for sign in (1,-1):
            dq=np.zeros(NM); dq[j]=sign*eps
            ts=static_state(zeta+(h@(q+dq)).reshape(zeta.shape),chord,dt)
            f.append(h.T@ts.forces[0][:3].reshape(-1))
        J[:,j]=(f[0]-f[1])/(2*eps)
    A,B,C,D=(model[k] for k in ('A','B','C','D'))
    dc=(C@linalg.solve(np.eye(len(A))-A,B)+D)[:,:NM]
    err=float(linalg.norm(J-dc)/linalg.norm(J))
    native=np.load(base/tag/'native-modal.npz'); phi=native['phi'][:NM]; xyz=native['xyz']; tip=np.isclose(xyz[:,1],xyz[:,1].max())
    tipmap=phi[:,tip,2].mean(axis=1)/np.sqrt(2)
    cases=json.loads((out/'motion.json').read_text()); stats={}
    for name,case in cases.items():
        frames=np.array(case['frames_time_and_q']); z=frames[:,1:]@tipmap
        delta=z-np.array(case['equilibrium_q'])@tipmap
        peaks,_=signal.find_peaks(delta)
        peaks=peaks[(frames[peaks,0]>.2)&(delta[peaks]>0)]
        fit=None
        if name!='untrimmed' and len(peaks)>=4:
            fit=dict(growth_per_s=float(np.polyfit(frames[peaks,0],np.log(delta[peaks]),1)[0]),frequency_hz=float(1/np.diff(frames[peaks,0]).mean()),positive_peaks=len(peaks))
        stats[name]=dict(initial_delta_tip_z_m=float(delta[0]),min_total_tip_z_m=float(min(z)),max_total_tip_z_m=float(max(z)),final_delta_tip_z_m=float(delta[-1]),late_positive_tip_peak_fit=fit)
        assert abs(delta[0]-.001)<1e-12
    assert err < .01, err
    frozen=np.array(cases['frozen-load']['frames_time_and_q'])
    deltaq=frozen[:,1:]-q
    numerical_omega=2*np.arctan(omega*(dt/V)/2)/(dt/V)
    exact=deltaq[0]*np.cos(frozen[:,0,None]*numerical_omega)
    frozen_error=float(np.max(abs(deltaq-exact)))
    assert frozen_error < 1e-10, frozen_error
    reports[tag]=dict(frozen_newmark_cosine_max_q_error=frozen_error,static_fd_rom_relative_frobenius_error=err,static_fd_J=J.tolist(),rom_dc_J=dc.tolist(),histories=stats)
    print(tag,err,stats,flush=True)
(base/'checks.json').write_text(json.dumps(reports,indent=2)+'\n')
