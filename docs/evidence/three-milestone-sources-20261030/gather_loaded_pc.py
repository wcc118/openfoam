from pathlib import Path
import json,csv,re,hashlib
root=Path('/home/foam/projects/openfoam/runs');result={}
for pattern in ('issue38-pose-*-20261030','issue38-static-*-20261030','issue38-loaded-*-20261030','issue38-estimate-mesh-20261030'):
 for folder in sorted(root.glob(pattern)):
  item={}
  for name in ('execution.json','manifest.json','mode-preparation.json'):
   p=folder/name
   if p.exists():item[name]=json.loads(p.read_text())
  p=folder/'processor0/native-interface-work.csv'
  if p.exists():
   rows=list(csv.reader(p.open()));a=[[float(v) for v in row] for row in rows[-50:] if len(row)==11];q=[r[7] for r in a]
   item['load_last50']={'rows':len(a),'first_iteration':a[0][0],'last':a[-1],'Q_range_N':max(q)-min(q),'Q_relative_range':(max(q)-min(q))/abs(a[-1][7])}
  p=folder/'log.quality'
  if p.exists():
   s=p.read_text();item['quality_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();item['quality_details']=[x.strip() for x in s.splitlines() if any(k in x for k in ('Time =','Mesh OK','Failed','tet quality','cells:'))]
  result[folder.name]=item
print(json.dumps(result,indent=2))
