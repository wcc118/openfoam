from pathlib import Path
import shutil, subprocess, json, time, hashlib
base=Path('/home/foam/projects/openfoam/runs'); source=base/'extended-wing-plumbing-mesh-v3-20261030'; out=base/'issue38-snap-convergence-20261030'
out.mkdir(exist_ok=False)
shutil.copytree(source/'system',out/'system');(out/'constant').mkdir();shutil.copytree(source/'constant/triSurface',out/'constant/triSurface');(out/'0').mkdir()
p=out/'system/snappyHexMeshDict';s=p.read_text();assert 'nSolveIter 50' in s and 'nRelaxIter 8' in s
s=s.replace('nSolveIter 50','nSolveIter 200').replace('nRelaxIter 8','nRelaxIter 40');p.write_text(s)
manifest=dict(scope='No-layer geometry-only snap-iteration sensitivity; unchanged surface/refinement/quality limits and1mm projection guard. No flow or coupled FSI.',source=str(source),changed_parameters={'snapControls.nSolveIter':[50,200],'snapControls.nRelaxIter':[8,40]},inputs={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
(out/'run.sh').write_text('source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\nblockMesh > log.blockMesh 2>&1\nsurfaceFeatureExtract > log.surfaceFeatureExtract 2>&1\nsnappyHexMesh -overwrite > log.snappyHexMesh 2>&1\ncheckMesh -allTopology -meshQuality > log.scaledQuality 2>&1\n/assets/bin/wingPointMap > log.pointMap 2>&1\n/opt/precice-python/bin/python /assets/map_motion_nearest_caps.py /case > log.mapMotion 2>&1\n')
name='issue38-snap-convergence-20261030';image='sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853'
cmd=['docker','run','--rm','--name',name,'--network','none','--cpus','2','--memory','6g','--user','1000:1000','-v',str(out)+':/case','-v',str(base/'extended-motion-assets-20261030')+':/assets:ro','-w','/case','--entrypoint','/bin/bash',image,'/case/run.sh']
start=time.monotonic()
with (out/'launcher.log').open('w') as f:
 try:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=600).returncode
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5',name],stdout=f,stderr=subprocess.STDOUT,timeout=30);code=124
quality=(out/'log.scaledQuality').read_text() if (out/'log.scaledQuality').exists() else ''
r=dict(exit_code=code,elapsed_s=time.monotonic()-start,command=cmd,strict_quality_passed='Mesh OK.' in quality and 'Failed' not in quality,map_passed=(out/'motion-map-report.json').exists())
(out/'execution.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(code or (0 if r['strict_quality_passed'] and r['map_passed'] else 2))
