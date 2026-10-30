from pathlib import Path
import json,hashlib,copy,re,shutil
import numpy as np
repo=Path('/tmp/openfoam-native-cfd');root=Path('/home/connellwc83/projects/openfoam/runs/native-cfd-20261030');e=root/'evidence';base=e/'issue38-native-pilot-base-20261030'
raw=(base/'interface.json').read_bytes();whole=json.loads(raw);centers=np.array([f['center_m'] for f in whole['faces']]);counts=np.array([len(f['point_indices']) for f in whole['faces']]);n=len(counts)
selection=sorted(set([0,1,2,n//4,n//2,3*n//4,n-1,int(np.argmax(counts))]+[int(f(centers[:,axis])) for axis in range(3) for f in (np.argmin,np.argmax)]))
faces=copy.deepcopy([whole['faces'][i] for i in selection]);indices=sorted({i for f in faces for i in f['point_indices']});remap={old:new for new,old in enumerate(indices)}
for f in faces:f['point_indices']=[remap[i] for i in f['point_indices']]
geometry=copy.deepcopy(whole);geometry['point_ids']=[whole['point_ids'][i] for i in indices];geometry['points_m']=[whole['points_m'][i] for i in indices];geometry['faces']=faces
rows=np.vstack([np.loadtxt(base/f'processor{i}/final-face-loads.csv',delimiter=',') for i in range(4)]);lookup={int(r[0]):r[4:7].tolist() for r in rows}
s=(base/'constant/wingMode').read_text();match=re.search(r'(?:^|\n)\s*(\d+)\s*\n\s*\(',s);body=s[match.end():];body=body[:body.rfind(')')];mode=np.fromstring(body.replace('(',' ').replace(')',' '),sep=' ').reshape(-1,3)/.0001
fixture=dict(geometry=geometry,loads=dict(quantity='integrated_point_force',force_unit='N',face_ids=[f['id'] for f in faces],forces_N=[lookup[f['id']] for f in faces]),modes=dict(point_ids=geometry['point_ids'],basis_units='dimensionless',coordinate_units='m',shapes=[mode[indices].tolist()]),provenance=dict(scope='Excerpt of native prescribed-bending startup CFD output; not experimental data or a flutter case.',source_case='issue38-native-pilot-base-20261030',source_export_sha256=hashlib.sha256(raw).hexdigest(),selected_face_indices=selection,selection='first three, quarter/half/three-quarter/last, max polygon size, and centre extrema',native_mode_normalization='mean tip z=1; q in metres; no modal mass/dynamics inferred'))
p=repo/'tests/fixtures/cfd_interface/native_span32_excerpt.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(fixture,indent=2)+'\n')
summary={'scope':'Issue38 bounded native CFD interface/mesh/startup milestone; implicit feedback remains no-go.','archive_sha256':hashlib.sha256((root/'native-evidence.tar.gz').read_bytes()).hexdigest(),'pc_archive':r'G:\projects\openfoam\build\issue38-native-evidence.tar.gz','baseline_projection':json.loads((root/'baseline-projection.json').read_text()),'snap_projection':json.loads((root/'snap-convergence-projection.json').read_text())}
for case,files in {'issue38-span32-20261030':['execution.json','manifest.json','motion-map-report.json'], 'issue38-native-motion-20261030':['execution.json','manifest.json'],'issue38-interface-v4-20261030':['execution.json','native-verification.json','native-modal-transfer.json'],'issue38-native-pilot-base-20261030':['execution.json','pilot-analysis.json','actual-load-transfer.json'],'issue38-native-pilot-half-20261030':['execution.json','pilot-analysis.json','actual-load-transfer.json']}.items():
 summary[case]={f:json.loads((e/case/f).read_text()) for f in files}
a,b=[summary[f'issue38-native-pilot-{tag}-20261030']['pilot-analysis.json'] for tag in ('base','half')];assert a['flow_initial_hashes']==b['flow_initial_hashes']
wa,wb=[np.loadtxt(e/f'issue38-native-pilot-{tag}-20261030/processor0/native-interface-work.csv',delimiter=',') for tag in ('base','half')]
common=np.array([wb[np.argmin(abs(wb[:,0]-t))] for t in wa[:,0]]);assert np.max(abs(common[:,0]-wa[:,0]))<1e-12
summary['pilot_comparison']=dict(identical_initial_flow_fields=True,common_time_max_force_component_difference_N=float(np.max(abs(wa[:,1:4]-common[:,1:4]))),partial_work_difference_J=b['actual_wall_work_right_endpoint_J']-a['actual_wall_work_right_endpoint_J'],partial_work_relative_change=float(b['actual_wall_work_right_endpoint_J']/a['actual_wall_work_right_endpoint_J']-1),warning='Only0.44% of one cycle; startup and Courant/timestep sensitivity unresolved. Positive partial work from mean lift is not damping.')
summary['native_excerpt']=dict(points=len(indices),faces=len(faces),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_export_sha256=hashlib.sha256(raw).hexdigest())
summary['failed_export_attempts']={name:json.loads((e/name/'execution.json').read_text()) for name in ['issue38-interface-20261030','issue38-interface-v2-20261030','issue38-interface-v3-20261030']}
(repo/'docs/evidence').mkdir(exist_ok=True);(repo/'docs/evidence/native-cfd-milestone-20261030.json').write_text(json.dumps(summary,indent=2)+'\n')
archive=repo/'docs/evidence/native-cfd-sources-20261030';archive.mkdir(exist_ok=True)
for p in root.glob('*.py'):shutil.copy2(p,archive/p.name)
shutil.copy2(root/'native-work-function.dict',archive/'native-work-function.dict')
shutil.copy2(root.parent/'instability-20261030/motion-assets/map_motion_nearest_caps.py',archive/'map_motion_nearest_caps.py')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in archive.iterdir() if p.is_file()}
(archive/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(excerpt=summary['native_excerpt'],comparison=summary['pilot_comparison']),indent=2))
