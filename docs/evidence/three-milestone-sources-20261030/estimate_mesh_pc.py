from pathlib import Path
import shutil,subprocess,json,time,hashlib
base=Path('/home/foam/projects/openfoam/runs');source=base/'issue38-span32-20261030';out=base/'issue38-estimate-mesh-20261030';out.mkdir(exist_ok=False)
shutil.copytree(source/'system',out/'system');(out/'constant').mkdir();shutil.copytree(source/'constant/triSurface',out/'constant/triSurface');(out/'0').mkdir()
p=out/'system/snappyHexMeshDict';s=p.read_text().replace('level 6;','level 4;').replace('level (4 5)','level (3 4)');p.write_text(s)
(out/'manifest.json').write_text(json.dumps(dict(scope='Cheaper no-layer diagnostic mesh: surface levels3/4, features4; existing geometry, span32 basegrid and quality/projection checks unchanged',inputs={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}),indent=2))
(out/'run.sh').write_text('source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\nblockMesh > log.blockMesh 2>&1\nsurfaceFeatureExtract > log.surfaceFeatureExtract 2>&1\nsnappyHexMesh -overwrite > log.snappy 2>&1\ncheckMesh -allTopology -meshQuality > log.quality 2>&1\n/assets/bin/wingPointMap > log.pointMap 2>&1\n/opt/precice-python/bin/python /assets/map_motion_nearest_caps.py /case > log.map 2>&1\n')
cmd=['docker','run','--rm','--name',out.name,'--network','none','--cpus','4','--memory','8g','--user','1000:1000','-v',str(out)+':/case','-v',str(base/'extended-motion-assets-20261030')+':/assets:ro','-w','/case','--entrypoint','/usr/bin/timeout','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','600','/bin/bash','/case/run.sh'];start=time.monotonic()
with (out/'launcher.log').open('w') as f:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=630).returncode
quality=(out/'log.quality').read_text() if (out/'log.quality').exists() else ''
r=dict(exit_code=code,elapsed_s=time.monotonic()-start,command=cmd,quality_passed='Mesh OK.' in quality and 'Failed' not in quality,map_passed=(out/'motion-map-report.json').exists());(out/'execution.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
for name in ('log.quality','log.map'):
 p=out/name
 if p.exists():print(name,p.read_text()[-1800:])
raise SystemExit(code)
