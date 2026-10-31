"""Loaded-reference native CFD release, bounded duration and exclusive outputs."""
from pathlib import Path
import hashlib,json,math,re,shutil,subprocess,sys,tarfile,time
root=Path('/home/foam/projects/openfoam/runs');build=Path('/mnt/g/projects/openfoam/build')
variant=sys.argv[1] if len(sys.argv)>1 else 'explicit'
assert variant in ('pilot','pilot2','explicit','half','implicit')
dt=.00025 if variant=='half' else .0005
end_time=.01 if variant in ('pilot','pilot2','implicit') else .65
steps=round(end_time/dt)
assert steps>0 and math.isclose(steps*dt,end_time,rel_tol=0,abs_tol=1e-12)
write_stride=math.gcd(steps,200)  # Always save complete fields at the terminal step.
reference_q=.01492455473113748
out=root/('issue38-loaded-'+variant+'-20261030');out.mkdir(exist_ok=False)
with tarfile.open(build/'issue38-loaded-source.tar.gz') as archive:archive.extractall(out/'pipeline',filter='data')
source=out/'pipeline/docs/evidence/coupled-baseline-sources-20261030';pilot=root/'issue38-native-pilot-base-20261030';mesh=root/'issue38-estimate-mesh-20261030';exporter=root/'issue38-interface-v4-20261030/source'
fluid=out/'fluid';solid=out/'solid';fluid.mkdir();solid.mkdir()
for folder in ('constant','system'):shutil.copytree(pilot/folder,fluid/folder)
steady=root/'issue38-static-release-20261030'
assert json.loads((steady/'execution.json').read_text())['exit_code']==0
fluid.joinpath('0').mkdir()
for f in ('U','p','k','omega','nut','phi'):shutil.copy2(steady/'500'/f,fluid/'0'/f)
shutil.copy2(pilot/'0/pointDisplacement',fluid/'0/pointDisplacement')
shutil.rmtree(fluid/'constant/polyMesh');shutil.copytree(steady/'constant/polyMesh',fluid/'constant/polyMesh')
p=fluid/'0/U';s=p.read_text();s,n=re.subn(r'type\s+noSlip;', 'type movingWallVelocity; value uniform (0 0 0);',s);assert n==1;p.write_text(s)
initial_force=float((steady/'processor0/native-interface-work.csv').read_text().splitlines()[-1].split(',')[7])

# Preserve initial native fields but remove prescribed motion: preCICE owns wing displacement.
p=fluid/'0/pointDisplacement';s=p.read_text();s=s[:s.index('wing {')]+'wing {type fixedValue; value uniform (0 0 0);}\n}\n';p.write_text(s)
p=fluid/'system/controlDict';s=p.read_text()
for key,value in [('startFrom','startTime'),('startTime','0'),('endTime',str(end_time)),('deltaT',f'{dt:.17g}'),('writeInterval',str(steps))]:
 if key=='writeInterval':s=s.replace('writeControl timeStep; writeInterval 20;','writeControl timeStep; writeInterval '+str(write_stride)+';')
 else:s,n=re.subn(r'\b'+key+r'\s+[^;]+;',key+' '+value+';',s);assert n==1,(key,n)
# Existing observer retains measured wall power and Q; remove prescribed sine comparison.
s=s.replace('Foam::scalar actualPower=Foam::sum(f & u), referencePower=Foam::sum(f & faceMode)*rate;', 'Foam::scalar actualPower=Foam::sum(f & u), referencePower=0;')
s=s.replace("<< rate*.0001", "<< 0")
end=s.rfind('}');s=s[:end]+'\nprecice {type preciceAdapterFunctionObject; libs ("libpreciceAdapterFunctionObject.so");}\n'+s[end:];p.write_text(s)
# Fresh source has no code caches; OpenFOAM generates the observer library in this case.
(fluid/'system/preciceDict').write_text('''FoamFile {version 2.0; format ascii; class dictionary; object preciceDict;}
preciceConfig "../precice-config.xml";
participant Fluid;
modules (FSI);
interfaces {
 Loads {mesh Fluid-Forces; patches (wing); locations faceCenters; writeData (Force);}
 Motion {mesh Fluid-Motion; patches (wing); locations faceNodes; readData (Displacement);}
}
FSI {rho rho [1 -3 0 0 0 0 0] 1.2250532683653954;}
''')
implicit=variant=='implicit';scheme='serial-implicit' if implicit else 'serial-explicit'
xml='''<?xml version="1.0"?>
<precice-configuration>
 <data:vector name="Force"/><data:vector name="Displacement"/>
 <mesh name="Fluid-Forces" dimensions="3"><use-data name="Force"/></mesh>
 <mesh name="Fluid-Motion" dimensions="3"><use-data name="Displacement"/></mesh>
 <mesh name="Solid-Forces" dimensions="3"><use-data name="Force"/></mesh>
 <mesh name="Solid-Motion" dimensions="3"><use-data name="Displacement"/></mesh>
 <participant name="Fluid">
  <provide-mesh name="Fluid-Forces"/><provide-mesh name="Fluid-Motion"/>
  <receive-mesh name="Solid-Forces" from="Solid"/><receive-mesh name="Solid-Motion" from="Solid"/>
  <read-data name="Displacement" mesh="Fluid-Motion"/><write-data name="Force" mesh="Fluid-Forces"/>
  <mapping:nearest-neighbor direction="read" from="Solid-Motion" to="Fluid-Motion" constraint="consistent"/>
  <mapping:nearest-neighbor direction="write" from="Fluid-Forces" to="Solid-Forces" constraint="conservative"/>
 </participant>
 <participant name="Solid">
  <provide-mesh name="Solid-Forces"/><provide-mesh name="Solid-Motion"/>
  <read-data name="Force" mesh="Solid-Forces"/><write-data name="Displacement" mesh="Solid-Motion"/>
 </participant>
 <m2n:sockets acceptor="Fluid" connector="Solid" exchange-directory=".."/>
 <coupling-scheme:SCHEME>
  <time-window-size value="DT"/><max-time value="0.0005"/>
  <participants first="Fluid" second="Solid"/>
  <exchange data="Force" mesh="Solid-Forces" from="Fluid" to="Solid"/>
  <exchange data="Displacement" mesh="Solid-Motion" from="Solid" to="Fluid" initialize="true"/>
  IMPLICIT
 </coupling-scheme:SCHEME>
</precice-configuration>
'''
extra='''<max-iterations value="30"/>
 <absolute-convergence-measure data="Displacement" mesh="Solid-Motion" limit="1e-7"/>
 <relative-convergence-measure data="Force" mesh="Solid-Forces" limit="1e-3"/>
 <acceleration:constant><relaxation value="0.5"/></acceleration:constant>''' if implicit else ''
(out/'precice-config.xml').write_text(xml.replace('SCHEME',scheme).replace('DT',str(dt)).replace('IMPLICIT',extra).replace('<max-time value="0.0005"/>', '<max-time value="'+str(end_time)+'"/>'))
config=(out/'precice-config.xml').read_text()
assert float(re.search(r'<time-window-size value="([^"]+)"',config)[1])==dt
assert float(re.search(r'<max-time value="([^"]+)"',config)[1])==end_time
settings=dict(coupling='implicit' if implicit else 'explicit',mass_kg=.45423328577302213,stiffness_N_m=1392.057119541888,damping_N_s_m=0.,end_time_s=end_time,max_iterations=30,displacement_limit_m=.015,reference_q_m=reference_q,initial_q_m=reference_q,initial_v_m_s=0.,initial_force_N=initial_force,initial_state='steady flow at perturbed loaded pose; release from rest; no gravity',mode_frequency_Hz=8.810675,native_modal_sha256='8f5870bafb5f77b48f423102b5ab4451d710054e4f89bb15da76317da6cb0236',approximation='one symmetric first-bending mode, fixed reference W and nearest shell projection; off-surface moment defect retained; no layers; no physical damping claim')
(solid/'settings.json').write_text(json.dumps(settings,indent=2))
(out/'run.sh').write_text('''source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1
set -eu
export PYTHONPATH=/case/pipeline
cd /case/fluid
/exporter/bin/wingInterfaceExport > log.export.serial 2>&1
decomposePar > log.decompose 2>&1
mpirun -np 4 /exporter/bin/wingInterfaceExport -parallel > log.export.parallel 2>&1
/opt/precice-python/bin/python /case/pipeline/docs/evidence/three-milestone-sources-20261030/prepare_loaded_assets.py > log.prepare 2>&1
mpirun -np 4 pimpleFoam -parallel > log.pimpleFoam 2>&1 &
fluid_pid=$!
cd /case/solid
/opt/precice-python/bin/python -m scripts.experiments.native_modal_participant --assets interface.npz --settings settings.json --config ../precice-config.xml --output result > log.solid 2>&1 &
solid_pid=$!
trap 'kill "$fluid_pid" "$solid_pid" 2>/dev/null || true' EXIT
set +e
wait "$solid_pid"
solid_status=$?
if [ "$solid_status" -ne 0 ]; then kill "$fluid_pid" 2>/dev/null || true; fi
wait "$fluid_pid"
fluid_status=$?
printf 'solid=%s fluid=%s\\n' "$solid_status" "$fluid_status"
[ "$solid_status" -eq 0 ] && [ "$fluid_status" -eq 0 ] || exit 2
set -e
cd /case/fluid
reconstructPar -latestTime > log.reconstruct 2>&1
checkMesh -allTopology -meshQuality -time "0:" > log.quality 2>&1
sed -i "s/startFrom startTime/startFrom latestTime/" system/controlDict
/exporter/bin/wingInterfaceExport > log.export.final 2>&1
''')
(out/'manifest.json').write_text(json.dumps(dict(variant=variant,dt_s=dt,steps=steps,write_stride=write_stride,source_archive_sha256=hashlib.sha256((build/'issue38-loaded-source.tar.gz').read_bytes()).hexdigest(),initial_fields={f:hashlib.sha256((fluid/'0'/f).read_bytes()).hexdigest() for f in ('U','p','k','omega','nut','phi')},settings=settings),indent=2))
cmd=['docker','run','--rm','--name',out.name,'--network','none','--cpus','4','--memory','8g','--user','1000:1000','-v',str(out)+':/case','-v',str(mesh)+':/mesh:ro','-v',str(exporter)+':/exporter:ro','-w','/case','--entrypoint','/usr/bin/timeout','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','7200','/bin/bash','/case/run.sh']
start=time.monotonic();(out/'execution.json').write_text(json.dumps(dict(status='running',command=cmd)))
with (out/'launcher.log').open('w') as log:
 try:code=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=7230).returncode
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5',out.name],stdout=log,stderr=subprocess.STDOUT,timeout=30);code=124
if code==0:
 history=json.loads((solid/'result/modal-history.json').read_text())
 if not history['completed'] or len(history['rows'])!=steps or any(abs(r['dt_s']-dt)>1e-12 for r in history['rows']):
  code=3
result=dict(exit_code=code,elapsed_s=time.monotonic()-start,command=cmd,status='process_completed' if code==0 else 'failed_or_timeout');(out/'execution.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
for path in (out/'launcher.log',solid/'log.solid',fluid/'log.pimpleFoam'):
 if path.exists():print(str(path),path.read_text()[-2200:])
raise SystemExit(code)
