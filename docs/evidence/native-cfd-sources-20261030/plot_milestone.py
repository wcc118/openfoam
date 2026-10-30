from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent;e=root/'evidence';report=json.loads((e/'issue38-interface-v4-20261030/native-verification.json').read_text())
a,b=[np.loadtxt(e/f'issue38-native-pilot-{tag}-20261030/processor0/native-interface-work.csv',delimiter=',') for tag in ('base','half')]
fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained');fig.suptitle('Native CFD pipeline: verified components and remaining feedback gate',fontsize=16)
ax=axes[0,0];ax.bar(['Original\nspan16','More snap\niterations','Span32\nbase grid'],[1.027259,1.017709,.087077],color=['#c15b3d','#d38d35','#218475']);ax.axhline(1,color='#942d2d',ls='--',label='Unchanged 1 mm guard');ax.set(ylabel='Maximum native surface distance (mm)',title='Projection: span resolution resolves the failed guard');ax.legend(fontsize=9)
ax=axes[0,1]
for data,label,color in [(a,'25 μs','#b46325'),(b,'12.5 μs','#17828c')]:ax.plot(data[:,0]*1000,data[:,3],'.-',label=label,color=color)
ax.set(xlabel='Time (ms)',ylabel='Native fluid lift (N)',title='Short startup pilots — only 0.44% of a cycle');ax.legend();ax.grid(alpha=.2)
ax=axes[1,0];t=np.linspace(0,2/8.810675,401);ax.plot(t,.1*np.sin(2*np.pi*8.810675*t),color='#425b86',label='Prescribed mean tip motion')
times=np.array([r['time_s'] for r in report['observed_motion_samples']]);ax.plot(times,.1*np.sin(2*np.pi*8.810675*times),'o',ms=4,color='#218475',label='Stored positions independently checked')
ax.set(xlabel='Time (s)',ylabel='Imposed mean tip z (mm)',title='Geometry-only: 33/33 sampled mesh checks pass');ax.legend(fontsize=8,loc='upper right');ax.grid(alpha=.2)
ax=axes[1,1];ax.axis('off');ax.text(0,.97,'What passed',weight='bold',fontsize=13,va='top');ax.text(0,.86,'• Native serial / four-rank geometry and ordering\n• Face ↔ point force, moment and virtual work\n• Native-mode wall motion and short CFD force histories\n• Wall / modal power agreement < 8.7 × 10⁻¹¹ W',fontsize=11,va='top',linespacing=1.7)
ax.text(0,.43,'Implicit structural feedback: NO-GO yet',weight='bold',fontsize=13,va='top',color='#942d2d');ax.text(0,.32,'Resolve shell projection offsets / moment conservation.\nThen establish periodic response and timestep sensitivity.\nNo-layer diagnostic mesh; no flutter or flight-limit claim.\nPositive partial work is NOT a damping estimate.',fontsize=11,va='top',linespacing=1.7)
fig.savefig(root/'native-cfd-milestone.png',dpi=160)
