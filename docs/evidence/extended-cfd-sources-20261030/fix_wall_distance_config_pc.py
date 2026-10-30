from pathlib import Path
import shutil,json
p=Path('/home/foam/projects/openfoam/runs/extended-wing-cfd-offset-20261030')
for name in ['system/fvSchemes','log.wallDistance','log.wallSpacingSummary','wall-spacing-execution.json']:
 if (p/name).exists():shutil.copy2(p/name,p/(name+'.attempt1'))
f=p/'system/fvSchemes';s=f.read_text();assert 'wallDist' not in s;s+='\nwallDist { method meshWave; correctWalls true; }\n';f.write_text(s)
(p/'wall-distance-config-decision.json').write_text(json.dumps(dict(reason='Initial native checkMesh returned0 but did not produce wallDistance because mesh-only fvSchemes lacked wallDist. Pinned writeFields.C explicitly skips wallDistance unless that subdictionary exists. Added explicit meshWave/correctWalls true, matching prior checked wall-spacing method; first attempt and failed downstream parser retained.',scope='Geometric distance configuration only, no flow solve or mesh quality relaxation'),indent=2));print('Configured explicit native meshWave wall distance')
