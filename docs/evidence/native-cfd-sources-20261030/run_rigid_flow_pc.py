from pathlib import Path
import importlib.util,subprocess,time,json,hashlib,shutil
base=Path('/home/foam/projects/openfoam/runs');mesh=base/'issue38-span32-20261030';out=base/'issue38-rigid-flow-20261030'
verification=json.loads((mesh/'execution.json').read_text());assert verification['strict_quality_passed'] and verification['map_passed']
assert json.loads((base/'issue38-native-motion-20261030/execution.json').read_text())['strict_quality_passed']
source=Path('/mnt/g/projects/openfoam/build/generate_extended_flow_base.py');spec=importlib.util.spec_from_file_location('flow',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.SPAN=2.4384;m.AREA=m.SPAN*m.CHORD
report=m.generate_case(mesh/'constant/polyMesh',out,alpha=0.,iterations=500)
report.update(scope='Pipeline-only rigid-flow diagnostic on numerical-quality-passing mesh with NO boundary layers and deliberately coarse resolution. Owner permits imperfect exploratory models. Not accepted viscous CFD, not dynamic damping, not flutter.',source_revision='8338650e529330c6570964b070fd7a94222619f7',generator_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),explicit_overrides={'SPAN_m':m.SPAN,'AREA_m2':m.AREA},surface='Same closed-TE NACA4412 provisional midsurface as shell, no outer-skin offset',mesh_layer_gate_passed=False)
(out/'manifest.json').write_text(json.dumps(report,indent=2))
shutil.copy2(mesh/'system/meshQualityDict',out/'system/meshQualityDict')
(out/'system/decomposeParDict').write_text(m.foam_header('decomposeParDict')+'numberOfSubdomains 4; method scotch;\n')
(out/'run-flow.sh').write_text('''source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1
set -eu
decomposePar > log.decomposePar 2>&1
mpirun -np 4 simpleFoam -parallel > log.simpleFoam 2>&1
reconstructPar -latestTime > log.reconstructPar 2>&1
''')
cmd=['docker','run','--rm','--name','issue38-rigid-flow-20261030','--network','none','--cpus','4','--memory','8g','--user','1000:1000','-v',str(out)+':/case','-w','/case','--entrypoint','/bin/bash','opencfd/openfoam-default@sha256:adbf625ac47ed81b34018602a6caeb4076bfacc2046b2f8cd36f82adb376946b','/case/run-flow.sh']
rpt=dict(command=cmd,status='running',started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()));(out/'execution.json').write_text(json.dumps(rpt,indent=2));start=time.monotonic()
with (out/'launcher.log').open('w') as f:
 try:
  r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=1200);rpt.update(exit_code=r.returncode,status='process_completed' if r.returncode==0 else 'process_failed')
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5','issue38-rigid-flow-20261030'],stdout=f,stderr=subprocess.STDOUT);rpt.update(exit_code=124,status='timeout')
rpt['elapsed_seconds']=time.monotonic()-start;(out/'execution.json').write_text(json.dumps(rpt,indent=2));print(json.dumps(rpt));raise SystemExit(rpt['exit_code'])
