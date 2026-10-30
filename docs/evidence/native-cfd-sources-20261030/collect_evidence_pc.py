from pathlib import Path
import json,tarfile,hashlib
base=Path('/home/foam/projects/openfoam/runs');out=Path('/mnt/g/projects/openfoam/build/issue38-native-evidence.tar.gz')
cases=['issue38-snap-convergence-20261030','issue38-span32-20261030','issue38-native-motion-20261030','issue38-interface-20261030','issue38-interface-v2-20261030','issue38-interface-v3-20261030','issue38-interface-v4-20261030','issue38-rigid-flow-20261030','issue38-native-pilot-base-20261030','issue38-native-pilot-half-20261030']
manifest=[]
with tarfile.open(out,'w:gz') as t:
 for name in cases:
  case=base/name
  paths=[p for p in case.glob('*.json') if p.name not in ('interface.json','native-mode.json','final-loads.json','interface-reference.json')]
  paths += [p for pattern in ('log.*','*.log','system/controlDict.initial.reconstructed') for p in case.glob(pattern) if p.is_file()]
  if 'native-pilot' in name:
   paths += [case/'processor0/native-interface-work.csv']
   paths += list((case/'postProcessing/forces').glob('*/*.dat'))
   # Only the base pilot needs the complete native arrays for excerpt extraction.
   if 'base' in name:
    paths += [case/'interface.json',case/'constant/wingMode']
    paths += [case/f'processor{i}/final-face-loads.csv' for i in range(4)]
  for p in sorted(set(paths)):
   if not p.is_file():continue
   member=name+'/'+str(p.relative_to(case));t.add(p,arcname=member)
   manifest.append(dict(path=member,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
manifest_path=out.with_suffix('.manifest.json');manifest_path.write_text(json.dumps(manifest,indent=2));print(json.dumps(dict(archive=str(out),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),files=len(manifest))))
