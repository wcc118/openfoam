from pathlib import Path
import re,json,importlib.util
import numpy as np
root=Path('/');case=Path('/case')
spec=importlib.util.spec_from_file_location('mesh',Path('/analysis/summarize_mesh.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def body(path):
 text=path.read_text();found=re.search(r'\n(\d+)\s*\n\(',text);assert found
 return int(found[1]),text[found.end():text.rfind(')')]
n,s=body(case/'constant/polyMesh/points');points=np.fromstring(s.replace('(',' ').replace(')',' '),sep=' ').reshape(-1,3);assert len(points)==n
n,s=body(case/'constant/polyMesh/owner');owner=np.fromstring(s,sep=' ',dtype=np.int64);assert len(owner)==n
boundary=(case/'constant/polyMesh/boundary').read_text();patch=re.search(r'\bwing\s*\{(.*?)\}',boundary,re.S)[1];start=int(re.search(r'startFace\s+(\d+)',patch)[1]);count=int(re.search(r'nFaces\s+(\d+)',patch)[1])
text=(case/'0/wallDistance').read_text();field=re.search(r'internalField\s+nonuniform List<scalar>\s+(\d+)\s*\((.*?)\)\s*;',text,re.S);dist=np.fromstring(field[2],sep=' ');assert len(dist)==int(field[1]);wall=dist[owner[start:start+count]];assert np.isfinite(wall).all() and (wall>0).all()
vtk=m.parse_vtk_polydata((case/'postProcessing/slices/0/wingSurface.vtk').read_bytes());assert len(vtk['polygons'])==count
n,s=body(case/'constant/polyMesh/faces');areas=[];max_centre_error=0
for i,match in enumerate(re.finditer(r'(\d+)\(([^()]*)\)',s)):
 if i<start:continue
 if i>=start+count:break
 ids=np.fromstring(match[2],sep=' ',dtype=np.int64);assert len(ids)==int(match[1]);pts=points[ids]
 area=m.polygon_area_3d(pts.tolist(),tuple(range(len(pts))));areas.append(area)
 vp=np.array([vtk['points'][j] for j in vtk['polygons'][i-start]])
 error=float(np.linalg.norm(pts.mean(axis=0)-vp.mean(axis=0)));max_centre_error=max(max_centre_error,error)
 # VTK POINTS are float32; require exact vertex-set equality at that precision.
 assert set(map(tuple,np.float32(pts))) == set(map(tuple,np.float32(vp)))
areas=np.array(areas);assert len(areas)==count
layers=np.array(vtk['nSurfaceLayers'])
def stats(mask):
 x=wall[mask];a=areas[mask];order=np.argsort(x);x=x[order];a=a[order];cdf=np.cumsum(a)/a.sum()
 return {'faces':len(x),'area_m2':float(a.sum()),'min_m':float(x.min()),'area_weighted_mean_m':float(np.sum(x*a)/a.sum()),'p50_m':float(x[np.searchsorted(cdf,.5)]),'p95_m':float(x[np.searchsorted(cdf,.95)]),'max_m':float(x.max())}
r={'scope':'meshWave nearest-wall distance at each wing-face owner cell, not yPlus or geometric layer thickness','vtk_native_face_centroid_max_difference_m':max_centre_error,'all_wall_faces':stats(np.ones(count,dtype=bool)),'with_layers':stats(layers>0),'without_layers':stats(layers==0)}
(case/'wall-spacing-summary.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
