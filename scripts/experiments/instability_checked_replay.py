"""Replay saved aerodynamic matrices and export actual modal histories for preview."""
from pathlib import Path
import os
import json
import hashlib
import numpy as np
from instability_demo import history, spectrum, tracked_branch


def replay(base, name):
    goland=name.startswith('goland')
    src=base/name/'model.npz' if goland else base/name/'flat-model.npz'
    d=np.load(src);mats=[d[k] for k in 'ABCD'];omega=d['omega'].copy();dt=float(d['dt']);n=len(omega)
    out=base/'checked'/name;out.mkdir(parents=True,exist_ok=False)
    if goland:
        # Display the actual aerodynamic lattice's positive semispan.
        N=(d['zeta'].shape[2]-1)//2
        z=d['zeta'][:,:,N:];H=d['H'][:,:,N:]
        xyz=z.transpose(1,2,0).reshape(-1,3)
        phi=H.transpose(3,1,2,0).reshape(n,-1,3)*np.sqrt(2)
        M=z.shape[1]-1
        quads=[[i*(N+1)+j,(i+1)*(N+1)+j,(i+1)*(N+1)+j+1,i*(N+1)+j+1] for i in range(M) for j in range(N)]
        description='Goland benchmark; aerodynamic lattice preview; two native modes, zero assumed structural damping.'
        speeds=[150.,175.];amplitude=1e-4;title='Goland: decaying versus growing oscillations'
    else:
        native=np.load(base/'native-modal.npz');xyz=native['xyz'];phi=native['phi'][:n];quads=native['quads'].tolist()
        omega[4]*=.1
        description='Hypothetical wing diagnostic: flat aerodynamic reference and 1% of original fifth modal stiffness. Original mode shapes/mass retained. Not the aluminum baseline or a physical redesign.'
        speeds=[20.,25.];amplitude=1e-5;title='Soft-torsion diagnostic: decaying versus growing oscillations'
    tip=np.isclose(xyz[:,1],xyz[:,1].max());kick=np.zeros(n)
    kick[0]=amplitude/(phi[0,tip,2].mean()/np.sqrt(2))
    h=phi.transpose(1,2,0).reshape(-1,n)/np.sqrt(2)
    branch=None if goland else tracked_branch(mats,omega,dt)
    model=dict(modes=phi.tolist(),description=description)
    if not goland:model.update(mass_kg=float(native['mass'].sum()),thickness_m=.00127)
    payload=dict(title=title,scope=description+' Motion is computed by coupled time integration. Geometry magnification does not change physical traces. Growth is linear small-perturbation growth, not a nonlinear limit cycle.',
        source='Pinned SHARPy 2.4 causal UVLM + native structural modal basis. Matrix SHA256 '+hashlib.sha256(src.read_bytes()).hexdigest(),
        mesh=dict(nodes=xyz.tolist(),quads=quads),models={'model':model},cases=[])
    reports=[]
    for speed in speeds:
        hist=history(mats,omega,dt,speed,h,kick)
        poles=spectrum(mats,omega,dt,speed)
        tracked=poles if goland else min(branch,key=lambda r:abs(r['speed_m_s']-speed))
        report={k:v for k,v in hist.items() if k!='frames_time_and_q'}
        report.update(poles=poles,tracked=tracked)
        report['growth_fit_error_per_s']=hist['fit']['growth_per_s']-tracked['growth_per_s'] if hist['fit'] else None
        reports.append(report)
        (out/f'V{speed:g}-full-history.json').write_text(json.dumps(hist,allow_nan=False))
        frames=hist['frames_time_and_q'];stride=max(1,len(frames)//1200)
        selected=frames[::stride]
        if selected[-1][0]!=frames[-1][0]:selected.append(frames[-1])
        name_label=('Decaying' if speed==speeds[0] else 'Growing')+f' — {speed:g} m/s'
        note=f'Initial mean tip bending displacement {amplitude*1000:g} mm; zero velocity. Tracked growth {tracked["growth_per_s"]:.4f}/s, frequency {tracked["frequency_hz"]:.3f} Hz. '+('Real poles remain decaying.' if (poles['max_real_growth_per_s'] or -1)<0 else 'Nonoscillatory growth also present.')
        payload['cases'].append(dict(name=name_label,model='model',reference_q=np.zeros(n).tolist(),
            frames=selected,note=note,stopped_at_50mm_guard=hist['stopped_at_50mm_guard']))
    summary=dict(matrix_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),cases=reports,tracked_branch=branch,
        replay_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        driver_script_sha256=hashlib.sha256(Path(__file__).with_name('instability_demo.py').read_bytes()).hexdigest())
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
    (out/'viewer-data.json').write_text(json.dumps(payload,allow_nan=False))
    print(name,[(r['speed_m_s'],r['growth_fit_error_per_s'],r['integrated_aero_work_J'],r['max_energy_work_defect_J']) for r in reports],flush=True)


if __name__=='__main__':
    base=Path('/results')
    for name in os.environ.get('CASES','goland-cfl025,flat-n10-cfl00625,flat-n20-cfl00625').split(','):replay(base,name)
