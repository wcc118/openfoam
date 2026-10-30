from pathlib import Path
import re,json
import numpy as np
p=Path('/case')
def read_list(path):
 s=re.sub(r'/\*.*?\*/|//[^\n]*','',path.read_text(),flags=re.S);m=re.search(r'(?:^|\n)\s*(\d+)\s*\(',s);assert m,path
 return int(m[1]),s[m.end():s.rfind(')')]
n,s=read_list(p/'0.025/polyMesh/sets/meshQualityFaces');ids=np.fromstring(s,sep=' ',dtype=int);assert len(ids)==n
n,s=read_list(p/'0.025/polyMesh/points');points=np.fromstring(s.replace('(',' ').replace(')',' '),sep=' ').reshape(-1,3);assert len(points)==n
n,s=read_list(p/'constant/polyMesh/faces');face_rows=re.findall(r'(\d+)\(([^()]*)\)',s);assert len(face_rows)==n
bound=(p/'constant/polyMesh/boundary').read_text();patches=[]
for name,body in re.findall(r'(\w+)\s*\{([^{}]*)\}',bound):
 count=re.search(r'nFaces\s+(\d+)',body);start=re.search(r'startFace\s+(\d+)',body)
 if count and start:patches.append((name,int(start[1]),int(count[1])))
rows=[]
for face_id in ids:
 count,text=face_rows[int(face_id)];v=np.fromstring(text,sep=' ',dtype=int);assert len(v)==int(count);xyz=points[v];center=xyz.mean(axis=0)
 patch=next((name for name,start,count in patches if start<=face_id<start+count),'internal')
 rows.append(dict(face_id=int(face_id),point_ids=v.tolist(),vertices_m=xyz.tolist(),arithmetic_center_m=center.tolist(),patch=patch))
r=dict(scope='Location of four native face-twist failures at saved t=0.025 s; native meshQualityFaces IDs, actual saved points and native topology. This does not diagnose a physical instability.',time_s=.025,faces=rows)
(p/'mesh-failure-locations.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
