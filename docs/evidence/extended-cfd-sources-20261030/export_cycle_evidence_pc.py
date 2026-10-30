from pathlib import Path
import tarfile,sys,json,time
name=sys.argv[1];p=Path('/home/foam/projects/openfoam/runs')/name;out=Path('/mnt/g/projects/openfoam/build')/(name+'-cycle-evidence.tar.gz')
with tarfile.open(out,'w:gz',compresslevel=1) as t:
 for f in p.iterdir():
  if f.is_file() and (f.name.startswith('log.') or '.json' in f.name or f.suffix=='.sh'):t.add(f,arcname=f.name)
 for folder in ['system','postProcessing/forces','postProcessing/forceCoeffs','postProcessing/solverInfo','postProcessing/yPlus']:
  if (p/folder).exists():t.add(p/folder,arcname=folder)
 for f in (p/'processor0').glob('wall-work-*.csv'):t.add(f,arcname='processor0/'+f.name)
print(json.dumps(dict(archive=str(out),export_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),scope='Complete saved text/evidence snapshot; execution manifest determines whether native process is terminal.')))
