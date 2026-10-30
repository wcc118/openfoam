from pathlib import Path
import shutil,json,subprocess,re,time
base=Path('/home/foam/projects/openfoam/runs');src=base/'extended-wing-prescribed-motion-20261030';out=base/'extended-wing-motion-extension-20261030';out.mkdir(exist_ok=False)
for d in ['constant','system','0']:shutil.copytree(src/d,out/d)
shutil.copy2(src/'wing-points.dat',out/'wing-points.dat')
f=out/'system/controlDict';s=f.read_text().replace('startFrom latestTime','startFrom startTime');f.write_text(s)
f=out/'system/fvSchemes';s=f.read_text().replace('laplacianSchemes {','laplacianSchemes { laplacian(diffusivity,cellDisplacement) Gauss linear uncorrected;');f.write_text(s)
(out/'manifest.json').write_text(json.dumps(dict(scope='Geometry-only diagnostic: fresh four-phase native mode motion, dedicated uncorrected mesh-displacement Laplacian. Fluid schemes and quality thresholds unchanged. Tests whether deferred nonorthogonal correction causes retained interior distortion.',source=str(src),mean_tip_amplitude_m=.0001,frequency_hz=8.810675,steps=4,fluid_solver=False,mesh_layer_gate_passed=False),indent=2))
(out/'run.sh').write_text("source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\nmoveDynamicMesh > log.moveDynamicMesh 2>&1\ncheckMesh -allTopology -meshQuality -time '0:' > log.movedQuality 2>&1\n")
cmd=['docker','run','--rm','--name','openfoam-motion-extension-20261030','--network','none','--cpus','2','--memory','12g','--user','1000:1000','-v',str(out)+':/case','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','/case/run.sh']
start=time.monotonic();rpt=dict(command=cmd,status='running')
with (out/'launcher.log').open('w') as f:
 try:
  r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=600);rpt.update(exit_code=r.returncode,status='process_completed' if r.returncode==0 else 'process_failed')
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5','openfoam-motion-extension-20261030'],stdout=f,stderr=subprocess.STDOUT);rpt.update(exit_code=124,status='timeout')
t=(out/'log.movedQuality').read_text() if (out/'log.movedQuality').exists() else '';rpt['strict_quality_passed']='Failed' not in t and t.count('Mesh OK.')==5
rpt['elapsed_seconds']=time.monotonic()-start;(out/'execution.json').write_text(json.dumps(rpt,indent=2));print(json.dumps(rpt));raise SystemExit(rpt['exit_code'] or (0 if rpt['strict_quality_passed'] else 2))
