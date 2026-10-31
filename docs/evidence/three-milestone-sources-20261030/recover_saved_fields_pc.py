"""Recover completed solver data after a final field-write scheduling failure."""
from pathlib import Path
import json,re,shlex,subprocess,time,hashlib,math,sys
root=Path('/home/foam/projects/openfoam/runs');variant=sys.argv[1];assert variant in ('explicit','half')
case=root/('issue38-loaded-'+variant+'-20261030');fluid=case/'fluid';target=case/'postprocess-recovery.json'
assert not target.exists(),'Recovery already recorded; preserve it.'
original=json.loads((case/'execution.json').read_text());assert original.get('exit_code')==1
assert 'solid=0 fluid=0' in (case/'launcher.log').read_text()
history_path=case/'solid/result/modal-history.json';h=json.loads(history_path.read_text());assert h['completed']
assert abs(h['rows'][-1]['time_s']-h['settings']['end_time_s'])<1e-10
names=[];required=('U','p','k','omega','nut','phi','polyMesh/points')
for p in (fluid/'processor0').iterdir():
 try:t=float(p.name)
 except ValueError:continue
 if not p.is_dir() or not math.isfinite(t) or t<=0:continue
 if all((fluid/f'processor{i}'/p.name/f).is_file() for i in range(4) for f in required):names.append(p.name)
names.sort(key=float);assert names
last=names[-1]
control=fluid/'system/controlDict';backup=fluid/'system/controlDict.before-field-recovery';assert not backup.exists();backup.write_bytes(control.read_bytes())
s=control.read_text()
for key,value in [('startFrom','startTime'),('startTime',last)]:s,n=re.subn(r'\b'+key+r'\s+[^;]+;',key+' '+value+';',s);assert n==1
control.write_text(s)
(fluid/'interface.before-field-recovery.json').write_bytes((fluid/'interface.json').read_bytes())
script=case/'recover-fields.sh';assert not script.exists()
script.write_text('source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\nreconstructPar -time '+shlex.quote(','.join(names))+' > log.reconstruct.recovery 2>&1\ncheckMesh -allTopology -meshQuality -time '+shlex.quote('0,'+','.join(names))+' > log.quality.recovery 2>&1\n/exporter/bin/wingInterfaceExport > log.export.recovery 2>&1\n')
exporter=root/'issue38-interface-v4-20261030/source'
cmd=['docker','run','--rm','--network','none','--cpus','2','--memory','6g','--user','1000:1000','-v',str(case)+':/case','-v',str(exporter)+':/exporter:ro','-w','/case/fluid','--entrypoint','/usr/bin/timeout','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','600','/bin/bash','/case/recover-fields.sh']
start=time.monotonic()
with (case/'recovery-launcher.log').open('x') as stream:code=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT,timeout=630).returncode
quality=(fluid/'log.quality.recovery').read_text() if (fluid/'log.quality.recovery').exists() else ''
passed=code==0 and quality.count('Mesh OK.')==len(names)+1 and 'Failed' not in quality
r=dict(exit_code=code,passed=passed,status='postprocessing_recovered' if passed else 'recovery_failed',original_execution=original,solver_return_codes={'solid':0,'fluid':0},history_completed=h['completed'],history_windows=len(h['rows']),history_end_time_s=h['rows'][-1]['time_s'],analysis_end_time_s=float(last),saved_field_times_s=[float(x) for x in names],mesh_ok_count=quality.count('Mesh OK.'),elapsed_s=time.monotonic()-start,history_sha256=hashlib.sha256(history_path.read_bytes()).hexdigest(),scope='Solver completed the requested history. Reconstruct only complete saved field times; final unsaved tail is excluded from fitted comparisons. Original failed postprocessing execution/log remains unchanged.',command=cmd)
target.write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 2)
