from pathlib import Path
import json,sys,numpy as np,hashlib
base=Path(__file__).parent;d=np.load(base/'native-modal.npz');xyz=d['xyz'].reshape(49,64,3);phi=d['phi'][0].reshape(49,64,3)
poly=xyz[0][:,[0,2]];n=len(poly);edge=np.roll(poly,-1,axis=0)-poly;den=np.sum(edge**2,axis=1)
mode=phi*(.0001/phi[-1,:,2].mean());L=xyz[-1,0,1]
def mapping(points):
 chunks=[];dist=[]
 for chunk in np.array_split(points,max(1,len(points)//2000)):
  delta=chunk[:,None,[0,2]]-poly[None,:,:]
  t=np.clip(np.sum(delta*edge,axis=2)/den,0.,1.)
  dd=np.sum((delta-t[:,:,None]*edge)**2,axis=2);seg=np.argmin(dd,axis=1);a=np.arange(len(chunk));s=t[a,seg]
  span=np.clip(abs(chunk[:,1])/L*48,0,48);j=np.minimum(span.astype(int),47);v=span-j
  u=(1-v[:,None])*((1-s[:,None])*mode[j,seg]+s[:,None]*mode[j,(seg+1)%n])+v[:,None]*((1-s[:,None])*mode[j+1,seg]+s[:,None]*mode[j+1,(seg+1)%n])
  u[:,1]*=np.where(chunk[:,1]<0,-1.,1.);chunks.append(u);dist.extend(np.sqrt(dd[a,seg]))
 result=np.vstack(chunks);dist=np.hypot(np.array(dist),np.maximum(abs(points[:,1])-L,0.))
 # The CFD's closed tip cap includes interior points absent from the open shell.
 # Use the exact cap-strip triangles and native perimeter translations there.
 cap=np.flatnonzero(abs(abs(points[:,1])-L)<dist)
 remaining=set(cap.tolist())
 def upper(i):return n-i if i not in (0,32) else i
 for k in range(32):
  for tri in [(k,k+1,upper(k)),(k+1,upper(k+1),upper(k))]:
   if len(set(tri))<3 or not remaining:continue
   a,b,c=poly[list(tri)];matrix=np.column_stack([b-a,c-a])
   ids=np.array(sorted(remaining));uv=np.linalg.solve(matrix,(points[ids][:,[0,2]]-a).T).T
   weights=np.column_stack([1-uv.sum(axis=1),uv]);inside=np.min(weights,axis=1)>=-1e-10
   chosen=ids[inside];mapped=weights[inside]@mode[-1,list(tri)]
   mapped[:,1]*=np.where(points[chosen,1]<0,-1.,1.)
   result[chosen]=mapped;dist[chosen]=abs(abs(points[chosen,1])-L)
   remaining.difference_update(chosen.tolist())
 return result,dist
# Identity test at all native surface nodes, including root and endpoints.
u,distance=mapping(xyz.reshape(-1,3));identity=float(np.max(abs(u-mode.reshape(-1,3))))
assert identity<1e-12,identity
if len(sys.argv)==1:print('native identity',identity);raise SystemExit(0)
case=Path(sys.argv[1]);points=np.loadtxt(case/'wing-points.dat',skiprows=1);u,distance=mapping(points[:,1:])
assert max(distance)<.001,('surface mismatch exceeds1mm',max(distance))
assert np.max(abs(points[:,2]))<=L+.001
f=case/'constant/wingMode';f.parent.mkdir(exist_ok=True)
with f.open('w') as out:
 out.write(str(len(u))+'\n(\n')
 for row in u:out.write('('+' '.join(f'{x:.17g}' for x in row)+')\n')
 out.write(')\n')
report=dict(scope='Prescribed first native bending mode;0.1mm mean tip amplitude. Nearest closed reference surface: span/perimeter or tip-cap triangle interpolation; not coupled FSI.',native_identity_max_error_m=identity,patch_points=len(u),surface_projection_max_distance_m=float(max(distance)),surface_projection_p99_m=float(np.quantile(distance,.99)),maximum_displacement_component_m=float(np.max(abs(u))),root_max_displacement_m=float(np.max(abs(u[np.isclose(points[:,2],0)]))) if np.any(np.isclose(points[:,2],0)) else None,native_sha256=hashlib.sha256((base/'native-modal.npz').read_bytes()).hexdigest(),point_map_sha256=hashlib.sha256((case/'wing-points.dat').read_bytes()).hexdigest())
(case/'motion-map-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
