from pathlib import Path
import json,hashlib,tarfile
root=Path('/home/foam/projects/openfoam/runs');build=Path('/mnt/g/projects/openfoam/build');files=[]
for variant in ('explicit','half','implicit'):
 case=root/('issue38-coupled-'+variant+'-20261030')
 for pattern in ('execution.json','manifest.json','assessment.json','run.sh','precice-config.xml','launcher.log','solid/settings.json','solid/interface.npz','solid/log.solid','solid/result/*','fluid/system/*','fluid/0/pointDisplacement','fluid/interface.json','fluid/log.*','fluid/processor0/native-interface-work.csv','fluid/processor*/final-face-loads.csv','fluid/postProcessing/forces/*/*'):
  files += [p for p in case.glob(pattern) if p.is_file()]
files=sorted(set(files));manifest={str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
out=build/'issue38-coupled-evidence.tar.gz'
with tarfile.open(out,'w:gz') as archive:
 for p in files:archive.add(p,arcname=str(p.relative_to(root)))
result=dict(archive_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),archive_bytes=out.stat().st_size,files=manifest)
(build/'issue38-coupled-evidence-manifest.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='files'}));print('files',len(files))
