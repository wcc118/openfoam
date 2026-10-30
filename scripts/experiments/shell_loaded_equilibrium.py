"""Clamped loaded-shape experiment; fixed linear native shell, nonlinear static UVLM.

Run in the pinned SHARPy container with native modal/camber inputs under /results.
The loaded reference is not free-flight trim or a prestressed structural solution.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy import linalg, optimize
from modal_uvlm_explore import (geometry, state_space, structural, coupled_system,
    AeroTimeStepInfo, StaticUvlm, uvlmlib, linuvlm, Krylov, cout_utils)

M, N, NM, WAKE, V = 8, 16, 10, 8, 30.0


def static_state(zeta, chord, dt):
    ts = AeroTimeStepInfo(np.array([[M, 2*N]]), np.array([[M*WAKE, 2*N]]))
    ts.rho = 1.225
    ts.zeta[0][:] = zeta
    ts.u_ext[0][0] = ts.u_ext_star[0][0] = 1.0
    for i in range(M*WAKE+1):
        ts.zeta_star[0][:, i] = zeta[:, -1] + np.array([chord/M*i, 0, 0])[:, None]
    opts = dict(StaticUvlm.settings_default)
    opts.update(rho=ts.rho, rollup_dt=dt, num_cores=2, n_rollup=0,
                rbm_vel_g=np.zeros(6), centre_rot_g=np.zeros(3))
    uvlmlib.vlm_solver(ts, opts)
    return ts


def reduce(ts, h, dt):
    aero = linuvlm.Dynamic(ts, dynamic_settings=dict(dt=dt, integr_order=2,
        density=ts.rho, remove_predictor=False, use_sparse=False, cfl1=False))
    aero.assemble_ss(wake_prop_settings=dict(cfl1=False, dt=dt))
    a,b,c,d = aero.SS.get_mats()
    nv = len(h)
    b = np.hstack([b[:, :nv]@h, b[:, nv:2*nv]@h])
    c = h.T@c
    d = np.hstack([h.T@d[:, :nv]@h, h.T@d[:, nv:2*nv]@h])
    rom = Krylov()
    rom.initialise(dict(algorithm='mimo_rational_arnoldi', r=6,
        single_side='observability', frequency=[0.0], print_info=False))
    mats = [np.real_if_close(x, tol=1000) for x in rom.run(state_space(a,b,c,d,dt)).get_mats()]
    assert all(np.isrealobj(x) for x in mats)
    return mats


def history(mats, omega, dt, qref, qkick, phi, tip, frozen=False, force=None):
    n = len(omega)
    step = dt/V
    force = np.zeros(n) if force is None else force
    u0 = np.r_[qkick, np.zeros(n)]
    if frozen:
        a,b,c,d = structural(omega, step)
        state = linalg.solve(c, u0)
        advance, output = lambda x: a@x, lambda x: c@x
    else:
        a,b,c,d = mats
        cp,(bs,cs,ds),(ad,bd,cd,dd) = coupled_system(a,b,c,d,omega,dt,V)
        # Initialize PHYSICAL displacement and velocity, including Newmark feedthrough.
        s = linalg.solve(cd, u0-dd@(ds@u0+force))
        state = np.r_[-bs@u0, s]  # zero raw incremental circulation
        inp = np.r_[np.zeros(2*n), force]
        advance = lambda x: cp.A@x+cp.B@inp
        output = lambda x: (cp.C@x+cp.D@inp)[n:]
    initial_error = float(np.max(abs(output(state)-u0)))
    assert initial_error < 1e-10
    rows=[]; peak=0.; stopped=False
    count=int(np.ceil(1.0/step)); stride=max(1,count//800)
    for k in range(count+1):
        q = qref+output(state)[:n]
        disp = np.einsum('m,mij->ij', q, phi)/np.sqrt(2)
        magnitude=float(np.max(abs(disp)))
        assert np.all(np.isfinite(q))
        peak=max(peak,magnitude)
        stopped=magnitude>0.05
        if k%stride==0 or k==count or stopped:
            rows.append([k*step,*q.tolist()])
        if stopped: break
        state=advance(state)
    return dict(frames_time_and_q=rows, equilibrium_q=qref.tolist(),
        initial_physical_state_error=initial_error, peak_node_component_m=peak,
        stopped_at_50mm_guard=stopped, recorded_seconds=rows[-1][0])


def run(base, tag):
    folder=base/tag
    out=base/(tag+'-equilibrium'); out.mkdir(exist_ok=False)
    zeta,H,omega,chord,source=geometry(folder,'shell',M,N,NM)
    h=H.reshape(-1,NM); dt=.5*chord/M
    native=np.load(folder/'native-modal.npz')
    phi=native['phi'][:NM]; xyz=native['xyz']; tip=np.isclose(xyz[:,1],xyz[:,1].max())
    iterations=[]
    def residual(q):
        ts=static_state(zeta+(h@q).reshape(zeta.shape),chord,dt)
        force=V**2*h.T@ts.forces[0][:3].reshape(-1)
        r=q-force/omega**2
        iterations.append(float(np.max(abs(r))))
        return r
    sol=optimize.root(residual,np.zeros(NM),tol=1e-9)
    qeq=sol.x; residual(qeq)
    assert sol.success and iterations[-1]<1e-9, (sol.message,iterations[-1])
    qkick=np.zeros(NM); qkick[0]=.001/(phi[0,tip,2].mean()/np.sqrt(2))
    loaded=static_state(zeta+(h@qeq).reshape(zeta.shape),chord,dt)
    force=V**2*h.T@loaded.forces[0][:3].reshape(-1)
    eqdisp=np.einsum('m,mij->ij',qeq,phi)/np.sqrt(2)
    report=dict(tag=tag, scope='Exploratory clamped loaded shape; linear structural stiffness, no prestress or free-flight trim',
        speed_m_s=V,M=M,N_per_half=N,wake_chords=WAKE,cfl=.5,modes=NM,
        dt_seconds=dt/V,assumed_modal_damping_ratio=0.,
        input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        native_sha256=hashlib.sha256((folder/'native-modal.npz').read_bytes()).hexdigest(),
        half_wing_mass_kg=float(native['mass'].sum()),frequencies_hz=(omega/(2*np.pi)).tolist(),
        equilibrium_q=qeq.tolist(),equilibrium_tip_z_m=float(eqdisp[tip,2].mean()),
        equilibrium_force_relative_residual=float(linalg.norm(omega**2*qeq-force)/linalg.norm(force)),
        root_iterations_max_displacement_residual=iterations,matched_initial_tip_perturbation_m=.001,
        guard='50 mm maximum absolute native-node displacement component; exploratory stop, not a physical allowable')
    print(json.dumps(report),flush=True)
    mats=reduce(loaded,h,dt)
    cases={}
    cases['frozen-load']=history(mats,omega,dt,qeq,qkick,phi,tip,frozen=True)
    cases['loaded-perturbation']=history(mats,omega,dt,qeq,qkick,phi,tip)
    hold=history(mats,omega,dt,qeq,np.zeros(NM),phi,tip)
    report['equilibrium_hold_max_q_error']=float(np.max(abs(np.array(hold['frames_time_and_q'])[:,1:]-qeq)))
    assert report['equilibrium_hold_max_q_error']==0.
    np.savez(out/'loaded-model.npz',A=mats[0],B=mats[1],C=mats[2],D=mats[3],omega=omega,dt=dt,qeq=qeq,H=H)
    unloaded=static_state(zeta,chord,dt)
    force0=V**2*h.T@unloaded.forces[0][:3].reshape(-1)
    mats0=reduce(unloaded,h,dt)
    cases['untrimmed']=history(mats0,omega,dt,np.zeros(NM),qkick,phi,tip,force=force0)
    report['cases']={key:{k:v for k,v in val.items() if k!='frames_time_and_q'} for key,val in cases.items()}
    (out/'assessment.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'motion.json').write_text(json.dumps(cases)+'\n')
    print(tag,'COMPLETE',report['equilibrium_tip_z_m'],flush=True)


if __name__=='__main__':
    base=Path('/results')
    cout_utils.start_writer()
    cout_utils.cout_wrap.initialise(False,True,str(base),'assembly.log')
    try:
        for tag in ('baseline','thicker'): run(base,tag)
    finally: cout_utils.finish_writer()
