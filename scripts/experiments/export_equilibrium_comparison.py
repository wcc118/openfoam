"""Export actual native histories for the offline comparison and a static plot."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def export(base):
    payload=dict(title='Loaded shell comparison · 30 m/s',
        scope='Exploratory linear shell + UVLM. Clamped loaded shape, not free-flight trim; no prestress, structural damping, flutter qualification or flight claim. Every case begins with +1 mm tip displacement and zero physical velocity relative to its reference. Magnification affects only the picture.',
        source='wcc118/openfoam issue #36; runs/loaded-equilibrium-20261029; pinned SHARPy 2.4 and MYSTRAN 19',
        models={},cases=[],source_sha256={})
    notes={'frozen-load':'Equilibrium aerodynamic load held fixed; aerodynamic feedback disabled.',
        'loaded-perturbation':'Incremental aerodynamic feedback about solved clamped loaded equilibrium; zero initial incremental circulation.',
        'untrimmed':'Constant reference aerodynamic load switched on about undeformed geometry, with incremental feedback. Its reference is zero, not its final settling position.'}
    evidence={}
    for tag in ('baseline','thicker'):
        native=np.load(base/tag/'native-modal.npz'); xyz=native['xyz']
        mesh=dict(nodes=xyz.tolist(),quads=native['quads'].tolist())
        if 'mesh' in payload: assert payload['mesh']==mesh
        else: payload['mesh']=mesh
        report=json.loads((base/(tag+'-equilibrium')/'assessment.json').read_text())
        evidence[tag]=report
        payload['models'][tag]=dict(modes=native['phi'][:10].tolist(),mass_kg=report['half_wing_mass_kg'],thickness_m=.00127 if tag=='baseline' else .001524)
        cases=json.loads((base/(tag+'-equilibrium')/'motion.json').read_text())
        for name,case in cases.items():
            payload['cases'].append(dict(name=tag+' / '+name,model=tag,
                reference_q=case['equilibrium_q'],frames=case['frames_time_and_q'],
                note=notes[name]+' Experimental stop: 50 mm absolute native-node displacement component, not a physical allowable.',
                stopped_at_50mm_guard=case['stopped_at_50mm_guard']))
        for path in [base/tag/'native-modal.npz',base/tag/'camber-M8-N16.npz',base/(tag+'-equilibrium')/'motion.json',base/(tag+'-equilibrium')/'loaded-model.npz']:
            payload['source_sha256'][str(path.relative_to(base))]=hashlib.sha256(path.read_bytes()).hexdigest()
    (base/'comparison-data.json').write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n')
    evidence['checks']=json.loads((base/'checks.json').read_text())
    evidence['source_sha256']=payload['source_sha256']
    evidence['native_thicker_characterization']={k:v for k,v in json.loads((base/'thicker-characterization.json').read_text()).items() if k!='section_fits'}
    evidence['preparation_script_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.glob('*.py')}
    evidence['runtime']=dict(sharpy_commit='a4154d471c30f15db9af6524763ea250bb46c7b8',container_image='sha256:53f45db26c471d5d35b1aac8b77826f642f2b4dd74b8a1311838a3bb31e8de9a',mystran='19.0.0')
    (base/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return payload


def plot(base,payload):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xyz=np.array(payload['mesh']['nodes']); tip=np.isclose(xyz[:,1],xyz[:,1].max())
    fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True)
    for case in payload['cases']:
        f=np.array(case['frames']); model=payload['models'][case['model']]
        phi=np.array(model['modes']); tipmap=phi[:,tip,2].mean(axis=1)/np.sqrt(2)
        z=f[:,1:]@tipmap*1000; ref=np.array(case['reference_q'])@tipmap*1000
        col=0 if case['model']=='baseline' else 1
        label=case['name'].split(' / ')[1]
        axes[0,col].plot(f[:,0],z,label=label)
        if label!='untrimmed': axes[1,col].plot(f[:,0],z-ref,label=label)
    for col,tag in enumerate(('baseline','thicker')):
        axes[0,col].set_title(tag+' skin'); axes[0,col].set_ylabel('Total mean tip z (mm)')
        axes[1,col].set_ylabel('Perturbation tip z (mm)');axes[1,col].set_xlabel('Time (s)')
    for ax in axes.flat: ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.suptitle('30 m/s · matched +1 mm initial tip perturbation · zero structural damping\nExploratory clamped shell, 10 native modes, fixed M8/N16, CFL 0.5')
    fig.tight_layout();fig.savefig(base/'comparison.png',dpi=160);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('results',type=Path)
    args=parser.parse_args();plot(args.results,export(args.results))
