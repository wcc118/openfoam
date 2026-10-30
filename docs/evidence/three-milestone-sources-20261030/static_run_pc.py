from pathlib import Path
import json,re,shutil,subprocess,time,sys,hashlib
base=Path('/home/foam/projects/openfoam/runs');build=Path('/mnt/g/projects/openfoam/build');mesh=base/'issue38-estimate-mesh-20261030';old=base/'issue38-rigid-flow-20261030';tag=sys.argv[1];q=float(sys.argv[2]);out=base/('issue38-static-'+tag+'-20261030');out.mkdir(exist_ok=False)
for folder in ('0','system'):shutil.copytree(old/folder,out/folder)
shutil.copytree(old/'constant',out/'constant',ignore=shutil.ignore_patterns('polyMesh'))
shutil.copytree(mesh/'constant/polyMesh',out/'constant/polyMesh')
if q:
 pose=base/('issue38-pose-'+tag+'-20261030');assert json.loads((pose/'execution.json').read_text())['passed'];shutil.copy2(pose/'1/polyMesh/points',out/'constant/polyMesh/points')
p=out/'system/controlDict';s=p.read_text();s=s.replace('type forces;','type forces; writeFields true;')
assert 'writeFields true' in s
observer=(build/'issue38-native-work-function.dict').read_text().replace('Foam::scalar actualPower=Foam::sum(f & u), referencePower=Foam::sum(f & faceMode)*rate;','Foam::scalar actualPower=Foam::sum(f & u), referencePower=0;').replace('<< rate*.0001','<< 0')
s=s[:s.rfind('}')]+observer+'\n}\n';p.write_text(s)
exporter=base/'issue38-interface-v4-20261030/source'
(out/'manifest.json').write_text(json.dumps(dict(q_m=q,scope='steady clamped pose, native modal force audit; no dynamic damping',baseline_native_sha256='8f5870bafb5f77b48f423102b5ab4451d710054e4f89bb15da76317da6cb0236',inputs={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and 'polyMesh' not in str(p)}),indent=2))
(out/'run.sh').write_text('''source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1
set -eu
export PYTHONPATH=/exporter
/exporter/bin/wingInterfaceExport > log.export.serial 2>&1
decomposePar > log.decompose 2>&1
mpirun -np 4 /exporter/bin/wingInterfaceExport -parallel > log.export.parallel 2>&1
/opt/precice-python/bin/python /build/issue38-static-prepare.py > log.prepare 2>&1
mpirun -np 4 simpleFoam -parallel > log.simpleFoam 2>&1
reconstructPar -latestTime > log.reconstruct 2>&1
''')
cmd=['docker','run','--rm','--name',out.name,'--network','none','--cpus','4','--memory','8g','--user','1000:1000','-v',str(out)+':/case','-v',str(mesh)+':/mesh:ro','-v',str(exporter)+':/exporter:ro','-v',str(build)+':/build:ro','-w','/case','--entrypoint','/usr/bin/timeout','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','1200','/bin/bash','/case/run.sh'];start=time.monotonic()
with (out/'launcher.log').open('w') as f:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=1230).returncode
r=dict(exit_code=code,elapsed_s=time.monotonic()-start,command=cmd,q_m=q);(out/'execution.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
for name in ('log.prepare','log.simpleFoam'):
 p=out/name
 if p.exists():print(name,p.read_text()[-1300:])
raise SystemExit(code)
