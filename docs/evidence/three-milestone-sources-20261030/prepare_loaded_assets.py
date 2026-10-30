from pathlib import Path
import hashlib,json,re
import numpy as np
from scripts.cfd_interface_transfer import build_interface,face_displacements
case=Path('/case');fluid=case/'fluid';mesh=Path('/mesh')
e=json.loads((fluid/'interface.json').read_text());m=build_interface(e)
a=np.loadtxt(mesh/'wing-points.dat',skiprows=1)
s=(mesh/'constant/wingMode').read_text();match=re.search(r'(?:^|\n)\s*(\d+)\s*\n\s*\(',s);n=int(match[1]);body=s[match.end():];body=body[:body.rfind(')')]
mode=np.fromstring(body.replace('(',' ').replace(')',' '),sep=' ').reshape(n,3)/.0001
lookup={int(g):i for i,g in enumerate(a[:,0])};idx=[lookup[i] for i in m.point_ids]
settings=json.loads((case/'solid/settings.json').read_text())
assert np.max(abs(m.points-a[idx,1:]-mode[idx]*settings['reference_q_m']))<1e-10
hp=mode[idx];hf=np.array(face_displacements(m,hp.tolist()))
np.savez_compressed(case/'solid/interface.npz',points=m.points,centers=m.centers,point_mode=hp,face_mode=hf,point_ids=m.point_ids,face_ids=m.face_ids)
settings=json.loads((case/'solid/settings.json').read_text());settings['assets_sha256']=hashlib.sha256((case/'solid/interface.npz').read_bytes()).hexdigest();(case/'solid/settings.json').write_text(json.dumps(settings,indent=2))
for folder in [fluid]+[fluid/f'processor{i}' for i in range(4)]:
 ex=json.loads((folder/'interface.json').read_text());mp=build_interface(ex);ids=[lookup[i] for i in mp.point_ids]
 values=face_displacements(mp,(mode[ids]*.0001).tolist())
 (folder/'constant/faceMode').write_text(str(len(values))+'\n(\n'+'\n'.join('('+' '.join(f'{v:.17g}' for v in row)+')' for row in values)+'\n)\n')
