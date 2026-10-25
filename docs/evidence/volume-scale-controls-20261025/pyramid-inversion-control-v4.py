from pathlib import Path
import subprocess,json,shutil,re,hashlib,time
root=Path('/home/connellwc83/projects/openfoam/runs/pyramid-volume-controls-v4-20261025');src=root/'fine-chord-floor';p=root/'inverted-chord-floor';p.mkdir()
for d in ['constant','system']:shutil.copytree(src/d,p/d)
f=p/'constant/polyMesh/points';s=f.read_text();m=re.search(r'\n(\d+)\s*\n\(',s);assert m and int(m[1])==64
end=s.rfind(')');rows=re.findall(r'\(([^()]*)\)',s[m.end():end]);pts=[list(map(float,r.split())) for r in rows];assert len(pts)==64
ids=[i for i,q in enumerate(pts) if all(abs(a-b)<1e-12 for a,b in zip(q,[.0001,.0001,.00002]))];assert len(ids)==1;i=ids[0];before=pts[i][:];pts[i][2]=-.0001
f.write_text(s[:m.end()]+'\n'+'\n'.join('('+' '.join(f'{v:.17g}' for v in q)+')' for q in pts)+'\n'+s[end:])
payload='source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\ncheckMesh -allTopology -meshQuality > log.topologyQuality 2>&1\ncheckMesh -allGeometry -allTopology > log.extended 2>&1\n';(p/'run.sh').write_text(payload)
cmd=['docker','run','--rm','--pull','never','--network','none','--memory','512m','--cpus','1','--user','1000:1000','--mount',f'type=bind,src={p},dst=/work','--workdir','/work','--entrypoint','/bin/bash','opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4','/work/run.sh']
t=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True,timeout=120);log=(p/'log.topologyQuality').read_text();report={'scope':'Deliberately inverted regular grid; checks must reject despite chord-scaled positive minVol floor','source':str(src),'point_index':i,'before_m':before,'after_m':pts[i],'minVol_m3':1e-13*.1016**3,'command':cmd,'exit_code':r.returncode,'elapsed_s':time.monotonic()-t,'mesh_quality_pass':'Mesh OK.' in log,'sha256':{str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file()}};(p/'execution.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['sha256','command']},indent=2));assert r.returncode==0 and 'Failed ' in log
