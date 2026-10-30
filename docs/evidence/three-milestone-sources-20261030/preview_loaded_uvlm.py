"""Render measured loaded-reference histories, with explicit imperial labels."""
from pathlib import Path
import argparse, json, html
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('root',type=Path);args=p.parse_args();root=args.root
native=np.load(root/'native-modal.npz');xyz=native['xyz'];phi=native['phi'];tip=np.isclose(xyz[:,1],xyz[:,1].max())
# Geometric chord rotation, positive when the trailing edge moves upward.
tip_ids=np.where(tip)[0];le=tip_ids[np.argmin(xyz[tip,0])];te=tip_ids[np.argmax(xyz[tip,0])]
cases=['n10-V20-K0.01','n10-V25-K0.01','n10-V25-K1'];colors=['#009e73','#d55e00','#0072b2']
fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,layout='constrained');table=[]
for tag,color in zip(cases,colors):
 folder=root/'loaded-deltas'/tag;a=json.loads((folder/'assessment.json').read_text());m=json.loads((folder/'motion.json').read_text());frames=np.array(m['frames_time_and_q']);q=frames[:,1:];ref=np.array(m['reference_q']);nm=q.shape[1]
 basis=phi[:nm]/np.sqrt(2);tipz=basis[:,tip,2].mean(axis=1);dy=(q-ref)@tipz/.0254
 chord=xyz[te]-xyz[le];dchord=np.einsum('tm,mj->tj',q,basis[:,te]-basis[:,le]);refchord=chord+ref@(basis[:,te]-basis[:,le]);angle=np.rad2deg(np.arctan2(chord[2]+dchord[:,2],chord[0]+dchord[:,0])-np.arctan2(refchord[2],refchord[0]))
 label=f"{a['speed_m_s']*3600/1852:.1f} kn | torsional K factor {a['torsional_stiffness_factor']:g}"
 axes[0].plot(frames[:,0],dy,label=label,color=color,gid=tag+'-bending');axes[1].plot(frames[:,0],angle,label=label,color=color,gid=tag+'-rotation')
 fit=a['history']['fit'];table.append(f'<tr><td>{html.escape(label)}</td><td>{a["equilibrium_tip_z_m"]/.0254:.4f}</td><td>{fit["frequency_hz"]:.3f}</td><td>{fit["growth_per_s"]:+.3f}</td><td>{fit["peaks"]}</td></tr>')
axes[0].set_ylabel('Tip bending relative to loaded pose (in)');axes[1].set_ylabel('Tip chord rotation relative to loaded pose (deg)');axes[1].set_xlabel('Time after release (s)');axes[0].legend(loc='upper left',fontsize=9)
for ax in axes:ax.grid(alpha=.25);ax.axhline(0,color='gray',lw=.6)
fig.suptitle('Loaded cambered-wing UVLM: decay and growth\nHypothetical modal stiffness changes; zero assumed structural damping')
out=root/'preview';out.mkdir(exist_ok=True);fig.savefig(out/'loaded-uvlm-comparison.png',dpi=160);fig.savefig(out/'loaded-uvlm-comparison.svg')
svg=(out/'loaded-uvlm-comparison.svg').read_text();svg=svg[svg.index('<svg'):]
controls='<p>Toggle overlapping curves: '+ ' '.join('<label><input type="checkbox" checked data-case="'+tag+'">'+html.escape(tag)+'</label>' for tag in cases)+'</p>'
body='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Loaded wing comparison</title><style>body{font:17px system-ui;max-width:1100px;margin:30px auto;padding:0 20px;background:#f6f8fa;color:#142334}svg{width:100%;height:auto}td,th{padding:10px;text-align:left;border-bottom:1px solid #ccc}table{border-collapse:collapse}</style><h1>Loaded wing: decay and growth</h1><p>These are UVLM histories about separately solved, cambered loaded equilibria. All cases start with a 0.0197-inch first-bending-mode displacement and zero velocity. Curves show motion relative to each loaded pose, not absolute wing position.</p>'''+svg+'<table><tr><th>Case</th><th>Loaded tip (in)</th><th>Fitted Hz</th><th>Growth (1/s)</th><th>Peaks</th></tr>'+''.join(table)+'''</table><p>Negative growth means decay; positive growth means increasing amplitude over the fitted history. The torsional factor changes only the fifth generalized stiffness, moving its uncoupled frequency from 169.48 Hz to 16.95 Hz at factor 0.01. It is not a physical wing redesign. Rotation is calculated from the displaced tip chord; it is not a modal-energy fraction.</p><p>Halving the aerodynamic timestep preserved growth/decay for these softened cases and the original 58.3-knot control, with less than 0.2% change in fitted growth rate. This checks timestep sensitivity, not aerodynamic mesh convergence or physical validation. Native CFD multi-cycle results are still pending. These plots do not establish a flight flutter limit.</p><script>document.querySelectorAll('input[data-case]').forEach(input=>input.addEventListener('change',()=>{['bending','rotation'].forEach(kind=>document.getElementById(input.dataset.case+'-'+kind).style.display=input.checked?'':'none');}));</script></html>'''
(out/'loaded-uvlm-comparison.html').write_text(body)
print(out)
