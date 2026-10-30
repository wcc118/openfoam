from pathlib import Path
import numpy as np, runpy, sys, json, hashlib
root=Path(__file__).resolve().parents[1]
source=root/'instability-20261030/motion-assets/map_motion_nearest_caps.py'
ns={'__file__': str(source)}
exec(compile(source.read_text().split('# Identity test')[0],str(source),'exec'),ns)
points=Path('/tmp/issue38-v3-wing-points.dat');a=np.loadtxt(points,skiprows=1);u,d=ns['mapping'](a[:,1:]);bad=np.flatnonzero(d>=.001)
report=dict(scope='Read-only reproduction of retained native closed-surface projection; no distance-guard relaxation or mesh modification.',source_map_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),native_sha256=hashlib.sha256((source.parent/'native-modal.npz').read_bytes()).hexdigest(),point_map_sha256=hashlib.sha256(points.read_bytes()).hexdigest(),point_count=len(a),guard_m=.001,maximum_distance_m=float(max(d)),p99_m=float(np.quantile(d,.99)),failed_points=[dict(point_id=int(a[i,0]),xyz_m=a[i,1:].tolist(),distance_m=float(d[i]),distance_to_tip_plane_m=float(abs(abs(a[i,2])-ns['L']))) for i in bad],passed=len(bad)==0)
Path(__file__).with_name('baseline-projection.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
