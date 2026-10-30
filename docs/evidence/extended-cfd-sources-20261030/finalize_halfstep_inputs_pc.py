from pathlib import Path
import json,hashlib
base=Path('/home/foam/projects/openfoam/runs');p=base/'extended-wing-analytic-halfstep-20261030';src=base/'extended-wing-analytic-motion-control-20261030'
f=p/'system/controlDict';f.write_text(f.read_text().replace('writeInterval 100','writeInterval 40'))
rows=[]
for f in sorted((p/'0.004').rglob('*')):
 if f.is_file():
  rel=f.relative_to(p);a=hashlib.sha256(f.read_bytes()).hexdigest();b=hashlib.sha256((src/rel).read_bytes()).hexdigest();assert a==b;rows.append(dict(path=str(rel),sha256=a))
for i in range(4):
 for name in ['constant/wingMode','0.004/U','0.004/p','0.004/phi','0.004/pointDisplacement','0.004/polyMesh/points']:
  f=p/f'processor{i}'/name;ref=src/f'processor{i}'/name;assert hashlib.sha256(f.read_bytes()).digest()==hashlib.sha256(ref.read_bytes()).digest()
(p/'identical-initial-state.json').write_text(json.dumps(dict(passed=True,root_files=rows,processor_fields_and_mode_maps_checked=True,scope='Exact same0.004s saved fluid and mesh state; half timestep is the changed physical parameter; output cadence differs.'),indent=2));print('Identical initial state verified; half-step output cadence40steps')
