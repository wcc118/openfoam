from pathlib import Path
import re,json,hashlib,numpy as np
root=Path('/home/connellwc83/projects/openfoam/runs'); case=root/'wing-flow-alpha4-checkpoint100-pc-20261025'; mesh=root/'mesh-trial9-spacing-pc-20261025'
m=json.loads((case/'source-manifest.json').read_text()); geo=json.loads((mesh/'wing-integration-geometry.json').read_text())
for key,h in geo['input_sha256'].items(): assert m['mesh']['copied_sha256'][key]==h
G=np.load(mesh/'wing-integration-geometry.npz'); A=G['area']; sf=G['sf']; centres=G['centres']; owner=G['owner']; n=len(A)
def field(text,key,count,vector=False):
 match=re.search(r'\b'+key+r'\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;',text,re.S)
 if match:
  assert int(match[2])==count
  out=np.fromstring(match[3].replace('(',' ').replace(')',' '),sep=' ')
  assert out.size==count*(3 if vector else 1)
  out=out.reshape(count,3) if vector else out
 else:
  match=re.search(r'\b'+key+r'\s+uniform\s+([^;]+);',text); assert match,(key,text[:200])
  v=np.fromstring(match[1].replace('(',' ').replace(')',' '),sep=' '); assert len(v)==(3 if vector else 1)
  out=np.broadcast_to(v,(count,3)).copy() if vector else np.full(count,v[0])
 assert np.isfinite(out).all(); return out
def patch(text,name):
 b=text.split('boundaryField',1)[1]; match=re.search(r'\b'+name+r'\s*\{([^{}]*)\}',b,re.S);assert match;return match[1]
ptext=(case/'100/p').read_text(); assert 'zeroGradient' in patch(ptext,'wing')
cells=int(re.search(r'internalField\s+nonuniform\s+List<scalar>\s+(\d+)',ptext)[1]); p=field(ptext,'internalField',cells)[owner]
y=field(patch((case/'100/yPlus').read_text(),'wing'),'value',n)
tau=field(patch((case/'100/wallShearStress').read_text(),'wing'),'value',n,True)
rho=m['flow']['density_kg_m3']; fp=rho*p[:,None]*sf; fv=-rho*tau*A[:,None]; arm=centres-np.array(m['geometry']['moment_origin_m'])
F=np.concatenate([(fp+fv).sum(0),fp.sum(0),fv.sum(0)]); M=np.concatenate([np.cross(arm,fp+fv).sum(0),np.cross(arm,fp).sum(0),np.cross(arm,fv).sum(0)])
def row(path):
 rows=np.loadtxt(case/'postProcessing-history-copy'/path); x=rows[rows[:,0]==100]; assert len(x)==1;return x[0,1:]
Fn=row('forces/0/force.dat'); Mn=row('forces/0/moment.dat'); co=row('forceCoeffs/0/coefficient.dat')
qS=m['flow']['dynamic_pressure_Pa']*m['geometry']['reference_area_m2']; c=m['geometry']['chord_m']; coeff=np.array([F[:3]@m['flow']['drag_direction']/qS,F[:3]@m['flow']['lift_direction']/qS,M[1]/qS/c]); native=co[[0,3,6]]
ix=np.argsort(y); cum=np.cumsum(A[ix])/A.sum(); quant=[float(y[ix[np.searchsorted(cum,v)]]) for v in [.5,.95,.99]]
phi=(case/'100/phi').read_text(); boundary=(mesh/'constant/polyMesh/boundary').read_text(); flux={}; values=[]
for name in m['mesh']['boundary_patches']:
 block=re.search(r'\b'+name+r'\s*\{([^{}]*)\}',boundary,re.S)[1]; count=int(re.search(r'nFaces\s+(\d+)',block)[1]); val=field(patch(phi,name),'value',count);flux[name]=float(val.sum());values.append(val)
allflux=np.concatenate(values); imbalance=abs(allflux.sum())/(-allflux[allflux<0].sum())
r={'scope':'Unconverged steady iteration100 diagnostic; not physical time, final acceptance or flight performance','geometry_hashes_verified':True,'iteration':100,'cells':cells,'wing_faces':n,'yPlus':{'area_weighted_median':quant[0],'area_weighted_p95':quant[1],'area_weighted_p99':quant[2],'max':float(y.max()),'area_fraction_above_2':float(A[y>2].sum()/A.sum())},'independent_force_total_pressure_viscous_N':F.tolist(),'native_force_total_pressure_viscous_N':Fn.tolist(),'max_force_difference_N':float(abs(F-Fn).max()),'independent_moment_total_pressure_viscous_Nm':M.tolist(),'native_moment_total_pressure_viscous_Nm':Mn.tolist(),'max_moment_difference_Nm':float(abs(M-Mn).max()),'coefficient_order':['Cd','Cl','CmPitch'],'independent_coefficients':coeff.tolist(),'native_coefficients':native.tolist(),'coefficient_abs_difference':abs(coeff-native).tolist(),'boundary_volume_flux_m3_s':flux,'relative_mass_imbalance':float(imbalance),'field_sha256':{f:hashlib.sha256((case/'100'/f).read_bytes()).hexdigest() for f in ['p','phi','yPlus','wallShearStress']},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(case/'independent-checkpoint-analysis.json').write_text(json.dumps(r,indent=2)+'\n');np.savez_compressed(case/'wing-surface-checkpoint100.npz',centres=centres,area=A,Cp=p/(.5*m['flow']['speed_m_s']**2),yPlus=y,face_force=fp+fv)
print(json.dumps(r,indent=2))
