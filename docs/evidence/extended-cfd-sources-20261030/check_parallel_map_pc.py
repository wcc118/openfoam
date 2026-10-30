from pathlib import Path
import numpy as np,json,re
root=Path('/case');reference=Path('/reference')
def body(path):
 s=path.read_text();s=re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S);m=re.search(r'(?:^|\n)\s*(\d+)\s*\n\s*\(',s);assert m,path
 a=np.fromstring(s[m.end():].replace('(',' ').replace(')',' ').replace(';',' '),sep=' ');return int(m[1]),a
original=np.loadtxt(reference/'wing-points.dat',skiprows=1);n,mode=body(reference/'constant/wingMode');mode=mode.reshape(n,3);lookup={int(i):k for k,i in enumerate(original[:,0])};seen=set();rows=[]
for rank in range(4):
 p=root/f'processor{rank}';local=np.loadtxt(p/'wing-points.dat',skiprows=1);_,addr=body(p/'constant/polyMesh/pointProcAddressing');addr=addr.astype(int);globalids=addr[local[:,0].astype(int)];indices=np.array([lookup[int(i)] for i in globalids]);n,u=body(p/'constant/wingMode');u=u.reshape(n,3)
 error=float(np.max(abs(u-mode[indices])));positionerror=float(np.max(abs(local[:,1:]-original[indices,1:])))
 assert error<1e-12 and positionerror<1e-10,(rank,error,positionerror)
 seen.update(globalids.tolist());rows.append(dict(rank=rank,patch_points=n,maximum_mode_error_m=error,maximum_reference_position_error_m=positionerror))
assert len(seen)==len(original),(len(seen),len(original))
r=dict(scope='Native pointProcAddressing cross-check of every parallel prescribed wing-mode value against serial mapping, including duplicate shared points.',ranks=rows,unique_wing_points=len(seen),passed=True);(root/'parallel-map-check.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
