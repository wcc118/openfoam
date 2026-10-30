from pathlib import Path
import shutil,json,re
base=Path('/home/foam/projects/openfoam/runs');src=base/'extended-wing-analytic-motion-control-20261030';out=base/'extended-wing-analytic-halfstep-20261030';out.mkdir(exist_ok=False)
for name in ['constant','system','0','0.004']:shutil.copytree(src/name,out/name)
for name in ['wing-points.dat','parallel-map-check.json','analytic-map-report.json','cycle-manifest.json','manifest.json']:
 shutil.copy2(src/name,out/name)
for rank in range(4):
 d=out/f'processor{rank}';d.mkdir()
 for name in ['constant','0','0.004']:shutil.copytree(src/f'processor{rank}'/name,d/name)
 for name in ['wing-points.dat','analytic-map-report.json']:shutil.copy2(src/f'processor{rank}'/name,d/name)
f=out/'system/controlDict';s=f.read_text();s=re.sub(r'deltaT [^;]+;','deltaT 0.00005;',s);s=s.replace('writeInterval 50','writeInterval 40');f.write_text(s)
d=json.loads((out/'cycle-manifest.json').read_text());d.update(scope='Half-timestep analytic prescribed-motion control from the identical saved0.004s fluid/mesh state. Compare force and wall-work histories; coarse no-layer model remains unvalidated, no native structural feedback.',dt_s=.00005,source_state=str(src/'0.004'),walltime_limit_s=5400);(out/'cycle-manifest.json').write_text(json.dumps(d,indent=2));print(str(out))
