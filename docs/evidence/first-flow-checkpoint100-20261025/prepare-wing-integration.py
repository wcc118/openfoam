from pathlib import Path
import numpy as np,re,json,hashlib
p=Path('/home/connellwc83/projects/openfoam/runs/mesh-trial9-spacing-pc-20261025');mesh=p/'constant/polyMesh'
def body(path):
 s=path.read_text();m=re.search(r'\n(\d+)\s*\n\(',s);assert m;return int(m[1]),s[m.end():s.rfind(')')]
def polygon(q):
 ref=q.mean(axis=0);nxt=np.roll(q,-1,axis=0);cross=np.cross(nxt-q,ref-q);weights=np.linalg.norm(cross,axis=1)
 assert weights.sum()>0
 return .5*cross.sum(axis=0), np.sum(weights[:,None]*(q+nxt+ref),axis=0)/(3*weights.sum())
# Independent triangle and translated unit-square geometry oracles.
sf,c=polygon(np.array([[0.,0,0],[2,0,0],[0,3,0]]));assert np.allclose(sf,[0,0,3]) and np.allclose(c,[2/3,1,0])
sf,c=polygon(np.array([[10.,2,5],[11,2,5],[11,3,5],[10,3,5]]));assert np.allclose(sf,[0,0,1]) and np.allclose(c,[10.5,2.5,5])
n,s=body(mesh/'points');pts=np.fromstring(s.replace('(',' ').replace(')',' '),sep=' ').reshape(-1,3);assert len(pts)==n
n,s=body(mesh/'owner');owner=np.fromstring(s,sep=' ',dtype=np.int64);assert len(owner)==n
boundary=(mesh/'boundary').read_text();patch=re.search(r'\bwing\s*\{(.*?)\}',boundary,re.S)[1];start=int(re.search(r'startFace\s+(\d+)',patch)[1]);count=int(re.search(r'nFaces\s+(\d+)',patch)[1]);sf=np.empty((count,3));centres=np.empty((count,3))
n,s=body(mesh/'faces');j=0
for i,match in enumerate(re.finditer(r'(\d+)\(([^()]*)\)',s)):
 if i<start:continue
 if i>=start+count:break
 ids=np.fromstring(match[2],sep=' ',dtype=np.int64);assert len(ids)==int(match[1]);sf[j],centres[j]=polygon(pts[ids]);j+=1
assert j==count
area=np.linalg.norm(sf,axis=1);assert (area>0).all()
np.savez(p/'wing-integration-geometry.npz',sf=sf,centres=centres,area=area,owner=owner[start:start+count])
report={'scope':'native-order wing polygon area vectors and triangle-area-weighted centres; independent Python geometric integration preparation, not force validation','faces':count,'area_m2':float(area.sum()),'area_vector_closure_m2':sf.sum(axis=0).tolist(),'uniform_pressure_torque_closure_m3':np.cross(centres-np.array([.0254,0,0]),sf).sum(axis=0).tolist(),'input_sha256':{name:hashlib.sha256((mesh/name).read_bytes()).hexdigest() for name in ['points','faces','owner','boundary']}}
(p/'wing-integration-geometry.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
