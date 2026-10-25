from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
p=Path('/home/connellwc83/projects/openfoam/runs/mesh-trial3-20261025')
def read(name):
 t=(p/'postProcessing/slices/0'/f'{name}.vtk').read_text().split()
 i=t.index('POINTS'); n=int(t[i+1]); v=np.array(t[i+3:i+3+3*n],float).reshape(-1,3)
 i=t.index('POLYGONS'); n=int(t[i+1]); i+=3; faces=[]
 for _ in range(n):
  k=int(t[i]); faces.append(v[np.array(t[i+1:i+1+k],int)]);i+=k+1
 i=t.index('nSurfaceLayers'); values=np.array(t[i+4:i+4+n],float)
 assert len(values)==len(faces)
 return faces,values
f,l=read('wingSurface'); avec=np.array([np.cross(q,np.roll(q,-1,axis=0)).sum(axis=0)/2 for q in f]); area=np.linalg.norm(avec,axis=1)
r=dict(status='rejected: detailed checkMesh failed two checks',wall_area_m2=float(area.sum()),area_fraction_with_layers=float(area[l>0].sum()/area.sum()),area_fraction_full18_layers=float(area[l==18].sum()/area.sum()),area_weighted_layers=float((area*l).sum()/area.sum()),face_fraction_with_layers=float((l>0).mean()),minimum_layers=float(l.min()),maximum_layers=float(l.max()))
(p/'layer-summary.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
fig.suptitle('Rejected mesh trial 3 · inspect before solving',fontsize=17)
for ax,name,bounds,title in [(axes[0,0],'midspan',(-.01,.115,-.025,.035),'Midspan'),(axes[0,1],'midspan',(-.005,.015,-.008,.014),'Leading edge'),(axes[1,0],'midspan',(.088,.109,-.006,.01),'Trailing edge'),(axes[1,1],'tip',(-.01,.115,-.025,.035),'Near tip y = 0.605 m')]:
 faces,layers=read(name)
 coll=PolyCollection([q[:,[0,2]] for q in faces],array=layers,cmap='viridis',edgecolors='#45546a',linewidths=.25)
 coll.set_clim(0,18);ax.add_collection(coll);ax.set_xlim(bounds[:2]);ax.set_ylim(bounds[2:]);ax.set_aspect('equal');ax.set_title(title);ax.set_xlabel('x (m)');ax.set_ylabel('z (m)')
fig.colorbar(coll,ax=axes.ravel().tolist(),label='Layer count field (not a flow solution)',shrink=.7)
fig.savefig(p/'mesh-slices.png',dpi=150)
fig,axes=plt.subplots(2,1,figsize=(13,6),layout='constrained')
for ax,sgn,title in ((axes[0],-1,'Upper wing'),(axes[1],1,'Lower wing')):
 mask=sgn*avec[:,2]>1e-14
 coll=PolyCollection([q[:,[1,0]] for q,keep in zip(f,mask) if keep],array=l[mask],cmap='viridis',edgecolors='none')
 coll.set_clim(0,18); ax.add_collection(coll);ax.autoscale();ax.set_aspect('equal');ax.set_title(title);ax.set_xlabel('y (m)');ax.set_ylabel('x (m)')
fig.suptitle(f'Rejected trial 3 · wall area with layers {r["area_fraction_with_layers"]:.1%}')
fig.colorbar(coll,ax=axes.tolist(),label='Actual layer count',shrink=.7)
fig.savefig(p/'layer-coverage.png',dpi=150)
