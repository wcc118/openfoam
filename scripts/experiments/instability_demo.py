"""Primary-owned exploratory instability experiment in the pinned SHARPy image.

Goland reuses verified projected matrices. The shell diagnostic deliberately
flattens its aerodynamic reference and changes only modal torsional stiffness;
it is not a physical redesign or the original loaded aluminum configuration.
"""
from pathlib import Path
import json
import os
import hashlib
import numpy as np
from scipy import linalg, optimize, signal
import shell_loaded_equilibrium as eq
from shell_loaded_speed_sweep import assemble
from modal_uvlm_explore import geometry, coupled_system


def spectrum(mats, omega, dt, speed):
    cp, _, _ = coupled_system(*mats, omega, dt, speed)
    values, vectors = linalg.eig(cp.A)
    keep = abs(values) > 1e-12
    values, vectors = values[keep], vectors[:, keep]
    lam = np.log(values.astype(complex)) / (dt / speed)
    n = len(omega)
    physical = cp.C[n:] @ vectors
    shapes = np.vstack([physical[:n], physical[n:] / omega[:, None]])
    weight = abs(shapes[:n])**2 + abs(shapes[n:])**2
    weight /= np.maximum(weight.sum(axis=0), 1e-300)
    ix = np.flatnonzero((lam.imag > 1e-6) & (np.angle(values) < .95*np.pi))
    i = ix[np.argmax(lam[ix].real)]
    real = lam[abs(lam.imag) < 1e-6]
    return dict(speed_m_s=float(speed), growth_per_s=float(lam[i].real),
        frequency_hz=float(lam[i].imag/(2*np.pi)), modal_fraction=weight[:, i].tolist(),
        max_real_growth_per_s=float(max(real.real)) if len(real) else None,
        max_all_growth_per_s=float(max(lam.real)),
        high_phase_growing_poles=int(np.count_nonzero((abs(np.angle(values))>=.95*np.pi)&(lam.real>1e-7))))


def tracked_branch(mats, omega, dt):
    """Follow the unstable 25 m/s mode backwards using modal state correlation."""
    n=len(omega);previous=None;rows=[]
    for speed in np.arange(25.,19.99,-.25):
        cp,_,_=coupled_system(*mats,omega,dt,speed)
        ev,vec=linalg.eig(cp.A)
        keep=(abs(ev)>1e-12)&(np.angle(ev)>1e-8)&(np.angle(ev)<.95*np.pi)
        ev,vec=ev[keep],vec[:,keep];lam=np.log(ev)/(dt/speed)
        u=cp.C[n:]@vec;shape=np.vstack([u[:n],u[n:]/omega[:,None]])
        shape/=np.maximum(linalg.norm(shape,axis=0),1e-300)
        macs=None if previous is None else abs(previous.conj()@shape)**2
        i=np.argmax(lam.real) if previous is None else np.argmax(macs)
        previous=shape[:,i]
        rows.append(dict(speed_m_s=float(speed),growth_per_s=float(lam[i].real),
            frequency_hz=float(lam[i].imag/(2*np.pi)),adjacent_mac=None if macs is None else float(macs[i]),
            modal_fraction=(abs(shape[:n,i])**2+abs(shape[n:,i])**2).tolist()))
    return rows[::-1]


def history(mats, omega, dt, speed, h, kick, seconds=2., guard=.05):
    n=len(omega)
    cp,(bs,cs,ds),(ad,bd,cd,dd)=coupled_system(*mats,omega,dt,speed)
    u0=np.r_[kick,np.zeros(n)]
    s=linalg.solve(cd,u0-dd@(ds@u0))
    x=np.r_[-bs@u0,s]
    assert np.max(abs((cp.C@x)[n:]-u0))<1e-10
    # Independently advance the original predictor descriptor equations.
    na=len(mats[0]); raw=np.r_[np.zeros(na),s]
    yx=linalg.solve(np.eye(n)-ds@dd,cs)
    ys=linalg.solve(np.eye(n)-ds@dd,ds@cd)
    ux=dd@yx;us=cd+dd@ys
    E=np.block([[np.eye(na)-bs@ux,-bs@us],[np.zeros((2*n,na)),np.eye(2*n)]])
    F=np.block([[mats[0],np.zeros((na,2*n))],[bd@yx,ad+bd@ys]])
    lu=linalg.lu_factor(E)
    rows=[];error=0.;stopped=False;step=dt/speed
    initial_energy=float(.5*np.sum((omega*kick)**2));work=0.;last_power=None;energy_defect=0.
    for k in range(int(np.ceil(seconds/step))+1):
        u=(cp.C@x)[n:];q=u[:n]
        force=(cp.C@x)[:n];power=float(force@u[n:])
        energy=float(.5*(u[n:]@u[n:]+np.sum((omega*q)**2)))
        if last_power is not None:work+=.5*step*(last_power+power)
        last_power=power;energy_defect=max(energy_defect,abs(energy-initial_energy-work))
        uraw=ux@raw[:na]+us@raw[na:]
        error=max(error,float(np.max(abs(u-uraw))))
        assert np.all(np.isfinite(u))
        rows.append([k*step,*q.tolist()])
        if np.max(abs(h@q))>guard:
            stopped=True;break
        x=cp.A@x;raw=linalg.lu_solve(lu,F@raw)
    frames=np.array(rows)
    peaks,_=signal.find_peaks(frames[:,1]*np.sign(kick[0]))
    peaks=peaks[(frames[peaks,0]>.35*frames[-1,0])&(frames[peaks,1]*np.sign(kick[0])>0)]
    fit=None
    if len(peaks)>=4:
        fit=dict(growth_per_s=float(np.polyfit(frames[peaks,0],np.log(abs(frames[peaks,1])),1)[0]),
            frequency_hz=float(1/np.diff(frames[peaks,0]).mean()),peaks=len(peaks))
    return dict(frames_time_and_q=rows,reference_q=np.zeros(n).tolist(),
        initial_physical_state_error=float(np.max(abs((cp.C@np.r_[-bs@u0,s])[n:]-u0))),
        descriptor_causal_max_error=error,stopped_at_50mm_guard=stopped,
        physical_guard_m=guard,fit=fit,speed_m_s=speed,dt_seconds=step,
        initial_structural_energy_J=initial_energy,final_structural_energy_J=energy,
        integrated_aero_work_J=work,max_energy_work_defect_J=energy_defect)


def benchmark(base,out):
    reports=[]
    for name in ['goland-cfl1-v2','goland-cfl05','goland-cfl025']:
        path=base/name/'model.npz';d=np.load(path)
        mats=[d[k] for k in 'ABCD'];omega=d['omega'];dt=float(d['dt'])
        h=d['H'].reshape(-1,len(omega))
        # Positive-tip mean z at the full-span surface end, 0.1 mm kick.
        tipmap=d['H'][2,:,-1,:].mean(axis=0)
        kick=np.zeros(len(omega));kick[0]=1e-4/tipmap[0]
        rows=[spectrum(mats,omega,dt,v) for v in np.arange(150.,176.,1.)]
        brackets=[(a['speed_m_s'],b['speed_m_s']) for a,b in zip(rows,rows[1:]) if a['growth_per_s']<0<=b['growth_per_s']]
        roots=[float(optimize.brentq(lambda v:spectrum(mats,omega,dt,v)['growth_per_s'],a,b)) for a,b in brackets]
        report=dict(model='Goland benchmark',source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            rows=rows,crossings_m_s=roots,frequencies_hz=(omega/(2*np.pi)).tolist(),cases=[])
        for v in [150.,175.]:
            hist=history(mats,omega,dt,v,h,kick)
            hist['poles']=spectrum(mats,omega,dt,v)
            report['cases'].append({k:value for k,value in hist.items() if k!='frames_time_and_q'})
            (out/f'{name}-V{v:g}.json').write_text(json.dumps(hist,allow_nan=False))
        np.savez(out/f'{name}-geometry.npz',xyz=d['zeta'].transpose(1,2,0).reshape(-1,3),
            phi=d['H'].transpose(3,1,2,0).reshape(len(omega),-1,3)*np.sqrt(2),grid_shape=d['zeta'].shape[1:])
        reports.append(report)
    (out/'benchmark.json').write_text(json.dumps(reports,indent=2,allow_nan=False))
    print(json.dumps(reports),flush=True)


def diagnostic(base,out):
    n=int(os.environ.get('MODES','10'));cfl=float(os.environ.get('CFL','.125'))
    M=int(os.environ.get('PANELS_M','8'));N=int(os.environ.get('PANELS_N','16'))
    wake=int(os.environ.get('WAKE_FACTOR','8'))
    eq.M,eq.N,eq.WAKE=M,N,wake
    zeta,H,omega,chord,source=geometry(base,'shell',M,N,n)
    # Explicit diagnostic change: flat lifting surface, retaining original modal map.
    zeta[2]=0.;h=H.reshape(-1,n);dt=cfl*chord/M
    ts=eq.static_state(zeta,chord,dt)
    assert np.max(abs(ts.forces[0][:3]))<1e-9
    mats,checks=assemble(ts,h,dt,omega,25.,check_frequencies=[0.,omega[0],2*np.pi*11.5,omega[4]*.1,omega[-1]])
    np.savez(out/'flat-model.npz',A=mats[0],B=mats[1],C=mats[2],D=mats[3],omega=omega,dt=dt,H=H,zeta=zeta)
    reports=[]
    for factor in [1.,.1,.03,.01,.003]:
        w=omega.copy();w[4]*=np.sqrt(factor)
        rows=[spectrum(mats,w,dt,v) for v in np.arange(5.,101.,5.)]
        brackets=[(a['speed_m_s'],b['speed_m_s']) for a,b in zip(rows,rows[1:]) if a['growth_per_s']<0<=b['growth_per_s']]
        roots=[float(optimize.brentq(lambda v:spectrum(mats,w,dt,v)['growth_per_s'],a,b)) for a,b in brackets]
        reports.append(dict(torsional_modal_stiffness_factor=factor,frequencies_hz=(w/(2*np.pi)).tolist(),rows=rows,crossings_m_s=roots))
    result=dict(scope='Hypothetical flat-aero reference; unchanged native mode shapes/mass; only fifth generalized stiffness scaled. Not native aluminum redesign.',
        checks=checks,cfl=cfl,M=M,N_per_half=N,wake_chords=wake,modes=n,reports=reports,
        input_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    soft=omega.copy();soft[4]*=.1
    result['tracked_soft_branch']=tracked_branch(mats,soft,dt)
    (out/'diagnostic.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    native=np.load(base/'native-modal.npz')
    phi=native['phi'][:n];xyz=native['xyz'];tip=np.isclose(xyz[:,1],xyz[:,1].max())
    kick=np.zeros(n);kick[0]=1e-5/(phi[0,tip,2].mean()/np.sqrt(2))
    w=omega.copy();w[4]*=.1
    for v in [20.,25.]:
        hist=history(mats,w,dt,v,phi.transpose(1,2,0).reshape(-1,n)/np.sqrt(2),kick)
        hist['poles']=spectrum(mats,w,dt,v)
        hist['torsional_modal_stiffness_factor']=.01
        (out/f'soft-torsion-V{v:g}.json').write_text(json.dumps(hist,allow_nan=False))
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    base=Path('/results');out=base/os.environ.get('OUTPUT_CASE','demo');out.mkdir(exist_ok=False)
    eq.cout_utils.start_writer();eq.cout_utils.cout_wrap.initialise(False,True,str(out),'assembly.log')
    try:
        if os.environ.get('MODEL','goland')=='goland':benchmark(base,out)
        else:diagnostic(base,out)
    finally:eq.cout_utils.finish_writer()
