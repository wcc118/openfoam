from pathlib import Path
import shutil,json,re
p=Path('/home/foam/projects/openfoam/runs/extended-wing-analytic-motion-control-20261030')
assert json.loads((p/'execution.json').read_text())['strict_moved_quality_passed']
for name in ['execution.json','log.pimpleFoam','log.movedQuality','log.reconstructPar','system/controlDict','position-verification.json']:
 if (p/name).exists():shutil.copy2(p/name,p/(name+'.initial-pilot'))
f=p/'system/controlDict';s=f.read_text().replace('startFrom startTime','startFrom latestTime');s=re.sub(r'endTime [^;]+;','endTime 0.004;',s);i=s.rfind('}');s=s[:i]+Path('/mnt/g/projects/openfoam/build/wall-work-function.dict').read_text()+s[i:];f.write_text(s)
assert not (p/'processor0/wall-work-pilot.csv').exists()
(p/'work-observer-manifest.json').write_text(json.dumps(dict(scope='Native per-face forces field dotted with actual movingWallVelocity boundary U, globally reduced. Compare summed force to native force.dat before interpreting work. Analytic prescribed motion only, no structural feedback.',columns=['time_s','Fx_N','Fy_N','Fz_N','power_W','wing_faces'],source='Pinned OpenCFD2412 forces.C force()/reset()/addToPatchFields()/execute(); force field includes pressure and viscous forces and is computed even when writeFields=false.',dt_s=.0001,start_s=.002,end_s=.004,quadrature='Raw endpoint power; cycle integration must document its quadrature and temporal limits.'),indent=2));print('prepared native-force/work observer pilot')
