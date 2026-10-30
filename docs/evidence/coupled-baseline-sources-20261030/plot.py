import json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(sys.argv[1]);d=json.loads((root/'assessment.json').read_text())
fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained');fig.suptitle('Native wing: live CFD–modal feedback, short startup controls',fontsize=16)
colors={'explicit':'#b66528','half':'#188c9c','implicit':'#6c4b96'};labels={'explicit':'Explicit 25 μs','half':'Explicit 12.5 μs','implicit':'Implicit 25 μs'}
for r in d['runs']:
 rows=r['rows'];t=np.array([x['time_s'] for x in rows])*1000;q=np.array([x['q_m'] for x in rows])*1e6
 axes[0,0].plot(t,q,'.-',label=labels[r['variant']],color=colors[r['variant']]);axes[0,1].plot(t,[x['force_N'][2] for x in rows],'.-',color=colors[r['variant']],label=labels[r['variant']])
axes[0,0].set(title='Forces now determine structural motion',xlabel='Time (ms)',ylabel='Mean tip modal coordinate (μm)');axes[0,0].legend();axes[0,0].grid(alpha=.2)
axes[0,1].set(title='Native CFD loads exchanged with structure',xlabel='Time (ms)',ylabel='Lift (N)');axes[0,1].legend();axes[0,1].grid(alpha=.2)
rs=d['runs'];ax=axes[1,0];x=np.arange(len(rs));ax.bar(x-.18,[r['final_q_m']*1e6 for r in rs],.36,label='Accepted structural coordinate',color='#405e80');ax.bar(x+.18,[r['final_saved_wall_fitted_q_m']*1e6 for r in rs],.36,label='Coordinate fitted to saved CFD wall',color='#25877a');ax.set(xticks=x,xticklabels=[labels[r['variant']] for r in rs],ylabel='Final mean tip displacement (μm)',title='Explicit wall lags one step; implicit iterates');ax.legend(fontsize=9)
ax=axes[1,1];ax.axis('off');implicit=next((r for r in rs if r['variant']=='implicit'),None)
text='Actual two-way exchange executed\nNative force / modal-load sums checked\nSaved wall shape checked independently\nSame initial fluid fields in all controls\n'
if implicit:text+=f"Implicit: {implicit['windows']} accepted windows,\n{implicit['rollbacks']} rejected trials restored\n"
ax.text(0,.98,text,va='top',fontsize=12,linespacing=1.7)
ax.text(0,.42,'Startup only — 0.44% of one cycle',fontsize=13,weight='bold',color='#9b433a')
ax.text(0,.34,'No damping or flutter conclusion.\nOne bending mode; zero assumed damping.\nNearest-shell offsets retained as an approximation.\nNext: initialization and affordable full-cycle response.',va='top',fontsize=11,linespacing=1.7)
fig.savefig(root/'coupled-baseline.png',dpi=160)
