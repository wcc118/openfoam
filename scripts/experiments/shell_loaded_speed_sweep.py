"""Loaded-equilibrium UVLM speed/mode experiment in the pinned SHARPy runtime.

No failed or guarded case is classified as stable. This is a fixed-CFL study,
not temporal convergence, and retains a linear, unprestressed shell basis.
"""
from pathlib import Path
import hashlib
import json
import time
import traceback
import numpy as np
from scipy import linalg, optimize, signal, sparse
from scipy.sparse.linalg import splu
import shell_loaded_equilibrium as eq
from modal_uvlm_explore import geometry, coupled_system, state_space

SPEEDS = [10., 20., 30., 40., 50., 55., 60., 80., 100.]
GUARD = .05


def assemble(ts, h, dt, omega, speed, check_frequencies=None):
    aero = eq.linuvlm.Dynamic(ts, dynamic_settings=dict(dt=dt, integr_order=2,
        density=ts.rho, remove_predictor=False, use_sparse=False, cfl1=False))
    aero.assemble_ss(wake_prop_settings=dict(cfl1=False, dt=dt))
    a,b,c,d = aero.SS.get_mats()
    nv = len(h)
    b = np.hstack([b[:, :nv]@h, b[:, nv:2*nv]@h])
    c = h.T@c
    d = np.hstack([h.T@d[:, :nv]@h, h.T@d[:, nv:2*nv]@h])
    rom = eq.Krylov()
    rom.initialise(dict(algorithm='mimo_rational_arnoldi', r=6,
        single_side='observability', frequency=[0.0], print_info=False))
    mats = [np.real_if_close(x, tol=1000) for x in rom.run(state_space(a,b,c,d,dt)).get_mats()]
    assert all(np.isrealobj(x) for x in mats)
    ar,br,cr,dr = mats
    checks = []
    frequencies = ([0., float(omega[0]), float(omega[9]), float(omega[-1])]
                   if check_frequencies is None else check_frequencies)
    for w in sorted(set(frequencies)):
        z = np.exp(1j*w*dt/speed)
        full = z*c@splu(z*sparse.eye(len(a),format='csc')-sparse.csc_matrix(a)).solve(b)+d
        reduced = z*cr@linalg.solve(z*np.eye(len(ar))-ar,br)+dr
        checks.append(dict(frequency_rad_s=w,relative_frobenius_error=float(linalg.norm(full-reduced)/max(linalg.norm(full),1e-30))))
    return mats,dict(full_states=len(a),reduced_states=len(ar),aero_rom_radius=float(max(abs(linalg.eigvals(ar)))),transfer_checks=checks)


def poles(mats, omega, dt, speed, previous):
    n=len(omega)
    cp,_,_=coupled_system(*mats,omega,dt,speed)
    values,vectors=linalg.eig(cp.A)
    keep=abs(values)>1e-10
    values=values[keep];vectors=vectors[:,keep]
    lam=np.log(values.astype(complex))/(dt/speed)
    physical=cp.C[n:]@vectors
    shapes=np.vstack([physical[:n],physical[n:]/omega[:,None]])
    norms=linalg.norm(shapes,axis=0)
    shapes/=np.maximum(norms,1e-30)
    resolved=np.flatnonzero((lam.imag>1e-5)&(np.angle(values)<.95*np.pi)&(norms>1e-12))
    assert len(resolved)
    first_fraction=abs(shapes[0])**2+abs(shapes[n])**2
    if previous is None:
        tracked=resolved[np.argmax(first_fraction[resolved])];mac=None
    else:
        correlations=abs(previous.conj()@shapes[:,resolved])**2
        tracked=resolved[np.argmax(correlations)];mac=float(max(correlations))
    dominant=resolved[np.argmax(lam[resolved].real)]
    real=lam[(abs(lam.imag)<1e-5)&(norms>1e-12)]
    def row(i):
        return dict(growth_per_s=float(lam[i].real),frequency_hz=float(lam[i].imag/(2*np.pi)),first_native_mode_fraction=float(first_fraction[i]))
    result=dict(tracked_bending=row(tracked),tracked_adjacent_mac=mac,dominant_resolved_oscillatory=row(dominant),
        largest_nonoscillatory_growth_per_s=float(max(real.real)) if len(real) else None,
        largest_all_pole_growth_per_s=float(max(lam.real)),
        unresolved_high_phase_growing_poles=int(np.count_nonzero((abs(np.angle(values))>=.95*np.pi)&(lam.real>1e-7))),
        resolved_oscillatory_growing_poles=int(np.count_nonzero(lam[resolved].real>1e-7)),
        all_resolved_oscillatory=[row(i) for i in resolved])
    return result,shapes[:,tracked]


def fit_history(history, phi, xyz):
    f=np.array(history['frames_time_and_q']);qref=np.array(history['equilibrium_q'])
    tip=np.isclose(xyz[:,1],xyz[:,1].max());tipmap=phi[:,tip,2].mean(axis=1)/np.sqrt(2)
    delta=(f[:,1:]-qref)@tipmap
    # Use the first structural coordinate, with its physical tip sign, to avoid
    # fitting a changing superposition of unrelated high-frequency modes.
    bend=(f[:,1]-qref[0])*tipmap[0]
    peaks,_=signal.find_peaks(bend)
    peaks=peaks[(f[peaks,0]>.15)&(bend[peaks]>abs(bend[0])*1e-4)]
    fit=None
    if len(peaks)>=4:
        coef=np.polyfit(f[peaks,0],np.log(bend[peaks]),1)
        fit=dict(growth_per_s=float(coef[0]),frequency_hz=float(1/np.diff(f[peaks,0]).mean()),positive_peaks=len(peaks),
            fit_start_s=float(f[peaks[0],0]),fit_end_s=float(f[peaks[-1],0]))
    return dict(initial_delta_tip_z_m=float(delta[0]),peak_abs_delta_tip_z_m=float(max(abs(delta))),
        final_delta_tip_z_m=float(delta[-1]),first_modal_tip_peak_fit=fit)


def case(base, out, n, speed, guess, previous):
    started=time.monotonic()
    report=dict(modes=n,speed_m_s=speed,status='running',M=8,N_per_half=16,wake_chords=8,cfl=.5,
        rho_kg_m3=1.225,assumed_structural_damping=0.,guard_native_node_component_m=GUARD)
    folder=out/f'n{n}-V{speed:g}';folder.mkdir(exist_ok=False)
    try:
        zeta,H,omega,chord,source=geometry(base,'shell',8,16,n)
        h=H.reshape(-1,n);dt=.5*chord/8
        native=np.load(base/'native-modal.npz');phi=native['phi'][:n];xyz=native['xyz']
        tip=np.isclose(xyz[:,1],xyz[:,1].max());r=xyz[tip]-xyz[tip].mean(axis=0)
        report.update(input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            native_sha256=hashlib.sha256((base/'native-modal.npz').read_bytes()).hexdigest(),
            dt_seconds=dt/speed,native_frequencies_hz=(omega/(2*np.pi)).tolist(),
            discrete_uncoupled_frequencies_hz=(2*np.arctan(omega*dt/speed/2)/(dt/speed)/(2*np.pi)).tolist())
        calls=[]
        def residual(q):
            ts=eq.static_state(zeta+(h@q).reshape(zeta.shape),chord,dt)
            force=speed**2*h.T@ts.forces[0][:3].reshape(-1)
            res=q-force/omega**2;calls.append(float(max(abs(res))))
            return res
        sol=optimize.root(residual,np.zeros(n) if guess is None else guess,tol=1e-9)
        qeq=sol.x;res=residual(qeq)
        report.update(equilibrium_solver_success=bool(sol.success),equilibrium_solver_message=str(sol.message),
            equilibrium_residual_history=calls,equilibrium_q=qeq.tolist())
        if not sol.success or not np.all(np.isfinite(qeq)) or max(abs(res))>=1e-9:
            report['status']='failed_equilibrium';return report,None,previous
        disp=np.einsum('m,mij->ij',qeq,phi)/np.sqrt(2)
        qkick=np.zeros(n);qkick[0]=.001/(phi[0,tip,2].mean()/np.sqrt(2))
        initial=disp+np.einsum('m,mij->ij',qkick,phi)/np.sqrt(2)
        report.update(equilibrium_tip_z_m=float(disp[tip,2].mean()),
            equilibrium_tip_twist_deg=float(np.sum(r[:,2]*disp[tip,0]-r[:,0]*disp[tip,2])/np.sum(r[:,0]**2+r[:,2]**2)*180/np.pi),
            equilibrium_max_node_component_m=float(np.max(abs(disp))),initial_max_node_component_m=float(np.max(abs(initial))),
            equilibrium_force_relative_residual=float(linalg.norm(omega**2*res)/linalg.norm(omega**2*qeq)))
        if max(np.max(abs(disp)),np.max(abs(initial)))>GUARD:
            report['status']='outside_displacement_experiment_guard';return report,qeq,previous
        loaded=eq.static_state(zeta+(h@qeq).reshape(zeta.shape),chord,dt)
        mats,aerocheck=assemble(loaded,h,dt,omega,speed);report['aero']=aerocheck
        if aerocheck['aero_rom_radius']>1.000001:
            report['status']='unstable_aero_rom';return report,qeq,previous
        report['poles'],shape=poles(mats,omega,dt,speed,previous)
        eq.V=speed
        hist=eq.history(mats,omega,dt,qeq,qkick,phi,tip)
        report['history']={k:v for k,v in hist.items() if k!='frames_time_and_q'}
        report['history_metrics']=fit_history(hist,phi,xyz)
        assert abs(report['history_metrics']['initial_delta_tip_z_m']-.001)<1e-12
        fit=report['history_metrics']['first_modal_tip_peak_fit'];tracked=report['poles']['tracked_bending']
        if fit:
            report['pole_transient_growth_difference_per_s']=fit['growth_per_s']-tracked['growth_per_s']
            report['pole_transient_frequency_relative_difference']=fit['frequency_hz']/tracked['frequency_hz']-1
        report['status']='transient_guard_stop' if hist['stopped_at_50mm_guard'] else 'executed_exploratory'
        (folder/'motion.json').write_text(json.dumps(hist,allow_nan=False)+'\n')
        np.savez(folder/'model.npz',A=mats[0],B=mats[1],C=mats[2],D=mats[3],omega=omega,dt=dt,qeq=qeq,H=H)
        return report,qeq,shape
    except Exception as e:
        report.update(status='failed_numerical',error=repr(e),traceback=traceback.format_exc())
        return report,None,previous
    finally:
        report['elapsed_seconds']=time.monotonic()-started
        (folder/'assessment.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(json.dumps({k:report[k] for k in ('modes','speed_m_s','status','elapsed_seconds')}),flush=True)


def main():
    base=Path('/results');out=base/'sweep';out.mkdir(exist_ok=False)
    eq.cout_utils.start_writer();eq.cout_utils.cout_wrap.initialise(False,True,str(out),'assembly.log')
    reports=[]
    try:
        for n in (10,20):
            guess=None;last_speed=None;previous=None
            for speed in SPEEDS:
                scaled=None if guess is None else guess*(speed/last_speed)**2
                report,qeq,previous=case(base,out,n,speed,scaled,previous)
                reports.append(report)
                if qeq is not None:guess=qeq;last_speed=speed
                (out/'summary.json').write_text(json.dumps(reports,indent=2,allow_nan=False)+'\n')
    finally:eq.cout_utils.finish_writer()


if __name__=='__main__':main()
