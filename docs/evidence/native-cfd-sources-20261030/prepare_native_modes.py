from pathlib import Path
import json,re
import numpy as np
from scripts.cfd_interface_transfer import build_interface,face_displacements
case=Path('/case');source=Path('/mesh')
def vectors(path):
 s=path.read_text();m=re.search(r'(?:^|\n)\s*(\d+)\s*\n\s*\(',s);n=int(m[1]);body=s[m.end():];body=body[:body.rfind(')')]
 return np.fromstring(body.replace('(',' ').replace(')',' '),sep=' ').reshape(n,3)
def write(path,values):
 path.write_text(str(len(values))+'\n(\n'+'\n'.join('('+' '.join(f'{v:.17g}' for v in row)+')' for row in values)+'\n)\n')
a=np.loadtxt(source/'wing-points.dat',skiprows=1);modes=vectors(source/'constant/wingMode');lookup={int(g):i for i,g in enumerate(a[:,0])};reports=[]
for folder in [case]+[case/f'processor{i}' for i in range(4)]:
 e=json.loads((folder/'interface.json').read_text());m=build_interface(e);idx=[lookup[i] for i in m.point_ids]
 error=float(np.max(abs(m.points-a[idx,1:])));assert error<1e-10,error
 mode=modes[idx];write(folder/'constant/wingMode',mode);write(folder/'constant/faceMode',face_displacements(m,mode.tolist()))
 (folder/'interface.json').rename(folder/'interface-reference.json')
 reports.append(dict(folder=folder.name,points=len(idx),faces=len(m.face_ids),max_reference_position_error_m=error))
(case/'mode-preparation.json').write_text(json.dumps(reports,indent=2))
