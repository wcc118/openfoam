from pathlib import Path
import shutil,json,re,subprocess
base=Path('/home/foam/projects/openfoam/runs');flow=base/'extended-wing-plumbing-flow-v3-20261030';template=base/'extended-wing-transient-parallel-20261030';motion=base/'extended-wing-prescribed-motion-20261030';assets=base/'extended-motion-assets-20261030';out=base/'extended-wing-analytic-motion-control-20261030'
assert json.loads((flow/'execution.json').read_text())['exit_code']==0
shutil.copy2('/mnt/g/projects/openfoam/build/map_analytic_control.py',assets/'map_analytic_control.py')
out.mkdir(exist_ok=False);shutil.copytree(flow/'constant',out/'constant');shutil.copytree(template/'system',out/'system');(out/'0').mkdir()
for name in ['U','p','k','omega','nut','phi']:shutil.copy2(flow/'500'/name,out/'0'/name)
for name in ['U','p']:
 f=out/'0'/name;s=f.read_text();start=s.index('wing',s.index('boundaryField'));opening=s.index('{',start);depth=1;end=opening+1
 while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
 bc='type movingWallVelocity; value uniform (0 0 0);' if name=='U' else 'type fixedFluxPressure; value uniform 0;'
 f.write_text(s[:opening]+'{ '+bc+' }'+s[end:])
shutil.copy2(motion/'0/pointDisplacement',out/'0/pointDisplacement');
f=out/'0/pointDisplacement';f.write_text(f.read_text().replace('prescribedNativeBending','prescribedAnalyticBending'));
shutil.copy2(motion/'constant/dynamicMeshDict',out/'constant/dynamicMeshDict')
f=out/'system/controlDict';s=f.read_text();s=re.sub(r'endTime [^;]+;','endTime 0.002;',s);s=re.sub(r'deltaT [^;]+;','deltaT 0.0001;',s);s=s.replace('writeInterval 5','writeInterval 10');f.write_text(s)
(out/'manifest.json').write_text(json.dumps(dict(scope='Analytic parabolic prescribed-wall CFD control on a coarse no-layer mesh. Not native structural modes, two-way FSI, viscous accuracy, damping or flutter. Native projection failed and remains failed.',source_flow=str(flow),source_iteration=500,dt_s=.0001,steps=20,end_time_s=.002,frequency_hz=8.810675,nominal_tip_amplitude_m=.0001,mpi_ranks=4,mesh_layer_gate_passed=False,pressure='kinematic gauge m2/s2',rho_kg_m3=1.2250532683653954,area_m2=.24774144,axes='x downstream,y span,z up',source_revision='476330b'),indent=2))
(out/'prepare.sh').write_text('source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\n/assets/bin/wingPointMap > log.pointMap.serial 2>&1\n/opt/precice-python/bin/python /assets/map_analytic_control.py /case > log.mapMotion.serial 2>&1\ndecomposePar > log.decomposePar 2>&1\nmpirun -np 4 /assets/bin/wingPointMap -parallel > log.pointMap.parallel 2>&1\nfor rank in 0 1 2 3; do /opt/precice-python/bin/python /assets/map_analytic_control.py /case/processor${rank} > log.mapMotion.${rank} 2>&1; done\n/opt/precice-python/bin/python /check.py > log.parallelMapCheck 2>&1\n')
cmd=['docker','run','--rm','--network','none','--cpus','4','--memory','4g','--user','1000:1000','-v',str(out)+':/case','-v',str(out)+':/reference:ro','-v',str(assets)+':/assets:ro','-v','/mnt/g/projects/openfoam/build/check_parallel_map_pc.py:/check.py:ro','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','/case/prepare.sh']
r=subprocess.run(cmd,timeout=180);print(json.dumps(dict(case=str(out),exit_code=r.returncode)));raise SystemExit(r.returncode)
