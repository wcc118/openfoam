from pathlib import Path
import tarfile
p=Path('/home/foam/projects/openfoam/runs/extended-wing-cfd-offset-20261030')
with tarfile.open('/mnt/g/projects/openfoam/build/fine-wall-spacing-evidence.tar.gz','w:gz') as t:
 for pattern in ['wall-spacing-*.json*','wall-distance-*.json','log.wallDistance*','log.wallSpacingSummary*']:
  for f in p.glob(pattern):t.add(f,arcname=f.name)
