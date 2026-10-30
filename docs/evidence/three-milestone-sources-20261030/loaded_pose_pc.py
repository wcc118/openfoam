from pathlib import Path
import shutil,subprocess,json,time,hashlib,re,sys
base=Path('/home/foam/projects/openfoam/runs');mesh=base/'issue38-estimate-mesh-20261030';template=base/'issue38-native-motion-20261030';q=float(sys.argv[1]);tag=sys.argv[2];out=base/('issue38-pose-'+tag+'-20261030');out.mkdir(exist_ok=False)
assert json.loads((mesh/'execution.json').read_text())['map_passed']
shutil.copytree(mesh/'constant/polyMesh',out/'constant/polyMesh');shutil.copytree(template/'system',out/'system');shutil.copytree(template/'0',out/'0');shutil.copy2(template/'constant/dynamicMeshDict',out/'constant/dynamicMeshDict');shutil.copy2(mesh/'constant/wingMode',out/'constant/wingMode')
p=out/'0/pointDisplacement';s=p.read_text();s=s.replace('Foam::sin(2.0*3.14159265358979323846*8.810675*this->db().time().value())',f'({q/.0001:.17g}*Foam::min(this->db().time().value(), Foam::scalar(1)))');p.write_text(s)
p=out/'system/controlDict';s=p.read_text()
for key,value in [('endTime','1'),('deltaT','.125'),('writePrecision','17'),('timePrecision','17')]:s,n=re.subn(r'\b'+key+r'\s+[^;]+;',key+' '+value+';',s);assert n==1
p.write_text(s)
(out/'manifest.json').write_text(json.dumps(dict(q_m=q,scope='geometry-only ramp to loaded pose; no flow',inputs={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and 'polyMesh' not in str(p)}),indent=2))
(out/'run.sh').write_text("source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\nmoveDynamicMesh > log.motion 2>&1\ncheckMesh -allTopology -meshQuality -time '0:' > log.quality 2>&1\n")
cmd=['docker','run','--rm','--name',out.name,'--network','none','--cpus','2','--memory','6g','--user','1000:1000','-v',str(out)+':/case','-w','/case','--entrypoint','/usr/bin/timeout','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','600','/bin/bash','/case/run.sh'];start=time.monotonic()
with (out/'launcher.log').open('w') as f:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=630).returncode
s=(out/'log.quality').read_text() if (out/'log.quality').exists() else ''
r=dict(exit_code=code,elapsed_s=time.monotonic()-start,q_m=q,command=cmd,mesh_ok_count=s.count('Mesh OK.'),failures=[x.strip() for x in s.splitlines() if 'Failed' in x]);r['passed']=code==0 and r['mesh_ok_count']==9 and not r['failures'];(out/'execution.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if r['passed'] else 2)
