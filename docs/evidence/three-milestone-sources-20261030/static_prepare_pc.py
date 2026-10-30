from pathlib import Path
import json,re,numpy as np
from scripts.cfd_interface_transfer import build_interface,face_displacements
case=Path('/case');mesh=Path('/mesh');q=json.loads((case/'manifest.json').read_text())['q_m'];a=np.loadtxt(mesh/'wing-points.dat',skiprows=1)
s=(mesh/'constant/wingMode').read_text();m=re.search(r'(?:^|\n)\s*(\d+)\s*\n\s*\(',s);n=int(m[1]);b=s[m.end():];b=b[:b.rfind(')')];hp=np.fromstring(b.replace('(',' ').replace(')',' '),sep=' ').reshape(n,3)/.0001;lookup={int(g):i for i,g in enumerate(a[:,0])};reports=[]
for folder in [case]+[case/f'processor{i}' for i in range(4)]:
 e=json.loads((folder/'interface.json').read_text());mapping=build_interface(e);idx=[lookup[i] for i in mapping.point_ids];err=float(np.max(abs(mapping.points-a[idx,1:]-hp[idx]*q)));assert err<1e-10,err
 f=face_displacements(mapping,(hp[idx]*.0001).tolist());(folder/'constant/faceMode').write_text(str(len(f))+'\n(\n'+'\n'.join('('+' '.join(f'{v:.17g}' for v in row)+')' for row in f)+'\n)\n');reports.append(dict(folder=folder.name,point_error_m=err,points=len(idx)))
(case/'mode-preparation.json').write_text(json.dumps(reports,indent=2))
