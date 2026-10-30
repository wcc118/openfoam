"""Historical PC driver, pinned existing mesh/runtime; exclusive outputs."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys,tarfile,time
root=Path('/home/foam/projects/openfoam/runs');build=Path('/mnt/g/projects/openfoam/build')
variant=sys.argv[1] if len(sys.argv)>1 else 'explicit'
assert variant in ('explicit','half','implicit')
dt=.0000125 if variant=='half' else .000025;steps=40 if variant=='half' else 20
out=root/('issue38-coupled-'+variant+'-20261030');out.mkdir(exist_ok=False)
with tarfile.open(build/'issue38-coupled-source.tar.gz') as archive:archive.extractall(out/'pipeline',filter='data')
source=out/'pipeline/docs/evidence/coupled-baseline-sources-20261030';pilot=root/'issue38-native-pilot-base-20261030';mesh=root/'issue38-span32-20261030';exporter=root/'issue38-interface-v4-20261030/source'
fluid=out/'fluid';solid=out/'solid';fluid.mkdir();solid.mkdir()
for folder in ('0','constant','system'):shutil.copytree(pilot/folder,fluid/folder)
# Preserve initial native fields but remove prescribed motion: preCICE owns wing displacement.
p=fluid/'0/pointDisplacement';s=p.read_text();s=s[:s.index('wing {')]+'wing {type fixedValue; value uniform (0 0 0);}\n}\n';p.write_text(s)
p=fluid/'system/controlDict';s=p.read_text()
for key,value in [('startFrom','startTime'),('startTime','0'),('endTime','.0005'),('deltaT',f'{dt:.17g}'),('writeInterval',str(steps))]:
 if key=='writeInterval':s=s.replace('writeControl timeStep; writeInterval 20;','writeControl timeStep; writeInterval '+str(steps)+';')
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
(out/'precice-config.xml').write_text(xml.replace('SCHEME',scheme).replace('DT',str(dt)).replace('IMPLICIT',extra))
settings=dict(coupling='implicit' if implicit else 'explicit',mass_kg=.45423328577302213,stiffness_N_m=1392.057119541888,damping_N_s_m=0.,end_time_s=.0005,max_iterations=30,displacement_limit_m=.0005,initial_state='q=v=0; untrimmed cambered-wing load startup; no gravity',mode_frequency_Hz=8.810675,native_modal_sha256='8f5870bafb5f77b48f423102b5ab4451d710054e4f89bb15da76317da6cb0236',approximation='one symmetric first-bending mode, fixed reference W and nearest shell projection; off-surface moment defect retained; no layers; no physical damping claim')
(solid/'settings.json').write_text(json.dumps(settings,indent=2))
(out/'run.sh').write_text('''source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1
set -eu
export PYTHONPATH=/case/pipeline
cd /case/fluid
/exporter/bin/wingInterfaceExport > log.export.serial 2>&1
decomposePar > log.decompose 2>&1
mpirun -np 4 /exporter/bin/wingInterfaceExport -parallel > log.export.parallel 2>&1
/opt/precice-python/bin/python /case/pipeline/docs/evidence/coupled-baseline-sources-20261030/prepare_assets.py > log.prepare 2>&1
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
(out/'manifest.json').write_text(json.dumps(dict(variant=variant,dt_s=dt,steps=steps,source_archive_sha256=hashlib.sha256((build/'issue38-coupled-source.tar.gz').read_bytes()).hexdigest(),initial_fields={f:hashlib.sha256((fluid/'0'/f).read_bytes()).hexdigest() for f in ('U','p','k','omega','nut','phi')},settings=settings),indent=2))
cmd=['docker','run','--rm','--name',out.name,'--network','none','--cpus','4','--memory','8g','--user','1000:1000','-v',str(out)+':/case','-v',str(mesh)+':/mesh:ro','-v',str(exporter)+':/exporter:ro','-w','/case','--entrypoint','/usr/bin/timeout','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','1800','/bin/bash','/case/run.sh']
start=time.monotonic();(out/'execution.json').write_text(json.dumps(dict(status='running',command=cmd)))
with (out/'launcher.log').open('w') as log:
 try:code=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=1830).returncode
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5',out.name],stdout=log,stderr=subprocess.STDOUT,timeout=30);code=124
result=dict(exit_code=code,elapsed_s=time.monotonic()-start,command=cmd,status='process_completed' if code==0 else 'failed_or_timeout');(out/'execution.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
for path in (out/'launcher.log',solid/'log.solid',fluid/'log.pimpleFoam'):
 if path.exists():print(str(path),path.read_text()[-2200:])
raise SystemExit(code)
