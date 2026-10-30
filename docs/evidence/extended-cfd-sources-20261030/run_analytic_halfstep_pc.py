from pathlib import Path
import subprocess,json,time
p=Path('/home/foam/projects/openfoam/runs/extended-wing-analytic-halfstep-20261030')
cmd=['docker','run','--rm','--name','openfoam-analytic-halfstep-20261030','--network','none','--cpus','4','--memory','4g','--user','1000:1000','-v',str(p)+':/case','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','-c','source /usr/lib/openfoam/openfoam2412/etc/bashrc && mpirun -np 4 pimpleFoam -parallel > log.pimpleFoam 2>&1 && reconstructPar -latestTime > log.reconstructPar 2>&1 && checkMesh -allTopology -meshQuality -latestTime > log.movedQuality 2>&1']
assert json.loads((p/'parallel-map-check.json').read_text())['passed']
start=time.monotonic();rpt=dict(command=cmd,status='running');(p/'cycle-execution.json').write_text(json.dumps(rpt))
with (p/'launcher.log').open('w') as f:
 try:
  r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=5400);rpt.update(exit_code=r.returncode,status='process_completed' if r.returncode==0 else 'process_failed')
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5','openfoam-analytic-halfstep-20261030'],stdout=f,stderr=subprocess.STDOUT);rpt.update(exit_code=124,status='timeout')
rpt['strict_moved_quality_passed']=(p/'log.movedQuality').exists() and 'Failed' not in (p/'log.movedQuality').read_text() and 'Mesh OK.' in (p/'log.movedQuality').read_text()
rpt['elapsed_seconds']=time.monotonic()-start;(p/'cycle-execution.json').write_text(json.dumps(rpt,indent=2));print(json.dumps(rpt));raise SystemExit(rpt['exit_code'])
