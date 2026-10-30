from pathlib import Path
import json,re,shutil,hashlib,subprocess,time,sys
base=Path('/home/foam/projects/openfoam/runs');build=Path('/mnt/g/projects/openfoam/build');flow=base/'issue38-rigid-flow-20261030';mesh=base/'issue38-span32-20261030';motion=base/'issue38-native-motion-20261030';template=base/'extended-wing-transient-parallel-20261030';exporter=base/'issue38-interface-v4-20261030/source'
half=len(sys.argv)>1 and sys.argv[1]=='half';dt=.0000125 if half else .000025;steps=40 if half else 20
out=base/('issue38-native-pilot-'+('half' if half else 'base')+'-20261030')
assert json.loads((flow/'execution.json').read_text())['exit_code']==0
assert json.loads((base/'issue38-interface-v4-20261030/execution.json').read_text())['exit_code']==0
out.mkdir(exist_ok=False);shutil.copytree(flow/'constant',out/'constant');shutil.copytree(template/'system',out/'system');(out/'0').mkdir()
for field in ('U','p','k','omega','nut','phi'):shutil.copy2(flow/'500'/field,out/'0'/field)
for name in ('U','p'):
 p=out/'0'/name;s=p.read_text();start=s.index('wing',s.index('boundaryField'));opening=s.index('{',start);end=opening+1;depth=1
 while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
 bc='type movingWallVelocity; value uniform (0 0 0);' if name=='U' else 'type fixedFluxPressure; value uniform 0;'
 p.write_text(s[:opening]+'{ '+bc+' }'+s[end:])
shutil.copy2(motion/'0/pointDisplacement',out/'0/pointDisplacement');shutil.copy2(motion/'constant/dynamicMeshDict',out/'constant/dynamicMeshDict');shutil.copy2(mesh/'constant/wingMode',out/'constant/wingMode');shutil.copy2(mesh/'system/meshQualityDict',out/'system/meshQualityDict')
p=out/'system/controlDict';s=p.read_text()
for key,value in [('startFrom','startTime'),('startTime','0'),('endTime','.0005'),('deltaT',f'{dt:.17g}'),('writePrecision','17'),('timePrecision','17')]:
 s,n=re.subn(r'\b'+key+r'\s+[^;]+;',key+' '+value+';',s);assert n==1,(key,n)
# Only change the top-level write interval; function-object histories remain every step.
s=s.replace('writeControl timeStep; writeInterval 5;','writeControl timeStep; writeInterval '+str(steps)+';')
assert ('writeInterval '+str(steps)+';') in s
s=s.replace('forces { type forces;','forces { type forces; writeFields true;')
end=s.rfind('}');s=s[:end]+(build/'issue38-native-work-function.dict').read_text()+'\n'+s[end:];p.write_text(s)
p=out/'system/fvSchemes';s=p.read_text()
if 'laplacian(diffusivity,cellDisplacement)' not in s:s=s.replace('laplacianSchemes {','laplacianSchemes { laplacian(diffusivity,cellDisplacement) Gauss linear uncorrected;')
p.write_text(s)
pipeline=out/'pipeline';(pipeline/'scripts').mkdir(parents=True)
for name in ('cfd_interface_transfer.py','modal_surface.py'):shutil.copy2(exporter/'scripts'/name,pipeline/'scripts'/name)
shutil.copy2(build/'issue38-prepare-native-modes.py',pipeline/'prepare_native_modes.py')
manifest=dict(scope='Prescribed first native bending-mode startup CFD pilot on no-layer diagnostic mesh. Not periodic damping, viscous validation, two-way FSI or flutter.',dt_s=dt,steps=steps,end_time_s=.0005,frequency_hz=8.810675,mean_tip_amplitude_m=.0001,initial_velocity='sine motion starts at zero displacement with nonzero velocity; startup impulse is deliberate and not a damping measure',initial_flow='fresh rigid iteration500 on this same mesh; not claimed converged',rho_kg_m3=1.2250532683653954,nu_m2_s=1.4605775e-5,airspeed_m_s=30.,airspeed_convention='TAS',area_m2=.24774144,chord_m=.1016,full_span_m=2.4384,moment_origin_m=[.0254,0,0],axes=['x_downstream','y_spanwise','z_up'],pressure='kinematic gauge m2/s2',turbulence='fully turbulent k-omega SST; no transition model',boundary_layers=False,mpi_ranks=4,source_modal_sha256=json.loads((mesh/'motion-map-report.json').read_text())['native_sha256'],flow_initial_hashes={name:hashlib.sha256((flow/'500'/name).read_bytes()).hexdigest() for name in ('U','p','k','omega','nut','phi')},inputs={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and 'polyMesh' not in str(p)})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
(out/'run.sh').write_text('source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\n/exporter/bin/wingInterfaceExport > log.export.serial 2>&1\ndecomposePar > log.decompose 2>&1\nmpirun -np 4 /exporter/bin/wingInterfaceExport -parallel > log.export.parallel 2>&1\n/opt/precice-python/bin/python /case/pipeline/prepare_native_modes.py > log.prepareModes 2>&1\nmpirun -np 4 pimpleFoam -parallel > log.pimpleFoam 2>&1\nreconstructPar -latestTime > log.reconstruct 2>&1\ncheckMesh -allTopology -meshQuality -time "0:" > log.quality 2>&1\nsed -i "s/startFrom startTime/startFrom latestTime/" system/controlDict\n/exporter/bin/wingInterfaceExport > log.export.final 2>&1\n')
name=out.name;cmd=['docker','run','--rm','--name',name,'--network','none','--cpus','4','--memory','8g','--user','1000:1000','-v',str(out)+':/case','-v',str(mesh)+':/mesh:ro','-v',str(exporter)+':/exporter:ro','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','/case/run.sh'];start=time.monotonic()
(out/'execution.json').write_text(json.dumps(dict(status='running',command=cmd)))
with (out/'launcher.log').open('w') as f:
 try:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=1200).returncode
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5',name],stdout=f,stderr=subprocess.STDOUT,timeout=30);code=124
q=(out/'log.quality').read_text() if (out/'log.quality').exists() else ''
r=dict(status='process_completed' if code==0 else 'failed_or_timeout',exit_code=code,elapsed_s=time.monotonic()-start,command=cmd,mesh_ok_count=q.count('Mesh OK.'),strict_sampled_quality_passed=q.count('Mesh OK.')==2 and 'Failed' not in q)
(out/'execution.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(code or (0 if r['strict_sampled_quality_passed'] else 2))
