from pathlib import Path
import shutil,subprocess,json,time,hashlib,re
base=Path('/home/foam/projects/openfoam/runs');mesh=base/'issue38-span32-20261030';template=base/'extended-wing-motion-extension-20261030';out=base/'issue38-native-motion-20261030'
verification=json.loads((mesh/'execution.json').read_text());assert verification['strict_quality_passed'] and verification['map_passed'], verification
out.mkdir(exist_ok=False);shutil.copytree(mesh/'constant/polyMesh',out/'constant/polyMesh');shutil.copytree(template/'system',out/'system');shutil.copytree(template/'0',out/'0')
shutil.copy2(template/'constant/dynamicMeshDict',out/'constant/dynamicMeshDict');shutil.copy2(mesh/'constant/wingMode',out/'constant/wingMode');shutil.copy2(mesh/'wing-points.dat',out/'wing-points.dat');shutil.copy2(mesh/'motion-map-report.json',out/'motion-map-report.json')
freq=8.810675;period=1/freq
p=out/'system/controlDict';s=p.read_text()
for key,value in [('startFrom','startTime'),('startTime','0'),('endTime',f'{2*period:.16g}'),('deltaT',f'{period/16:.16g}'),('writeControl','timeStep'),('writeInterval','1'),('purgeWrite','0')]:
 s,n=re.subn(r'\b'+key+r'\s+[^;]+;',key+' '+value+';',s);assert n==1,(key,n)
p.write_text(s)
manifest=dict(scope='Geometry-only two-cycle native first-bending motion on no-layer span32 diagnostic mesh. No flow, damping or coupled FSI. Unchanged strict mesh-quality limits.',source_mesh=str(mesh),motion_template=str(template),frequency_hz=freq,mean_tip_amplitude_m=.0001,cycles=2,steps_per_cycle=16,quality_expected_samples=33,inputs={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and 'polyMesh' not in str(p)})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
(out/'run.sh').write_text("source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\nmoveDynamicMesh > log.moveDynamicMesh 2>&1\ncheckMesh -allTopology -meshQuality -time '0:' > log.movedQuality 2>&1\n")
name='issue38-native-motion-20261030';cmd=['docker','run','--rm','--name',name,'--network','none','--cpus','2','--memory','8g','--user','1000:1000','-v',str(out)+':/case','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','/case/run.sh'];start=time.monotonic()
with (out/'launcher.log').open('w') as f:
 try:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=900).returncode
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5',name],stdout=f,stderr=subprocess.STDOUT,timeout=30);code=124
quality=(out/'log.movedQuality').read_text() if (out/'log.movedQuality').exists() else ''
r=dict(exit_code=code,elapsed_s=time.monotonic()-start,command=cmd,mesh_ok_count=quality.count('Mesh OK.'),failed_check_lines=[s.strip() for s in quality.splitlines() if 'Failed' in s],strict_quality_passed=quality.count('Mesh OK.')==33 and 'Failed' not in quality)
(out/'execution.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(code or (0 if r['strict_quality_passed'] else 2))
