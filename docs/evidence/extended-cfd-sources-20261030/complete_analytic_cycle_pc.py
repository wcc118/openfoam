"""Observe an existing bounded run, retain timeout evidence, and finish its saved cycle."""
from pathlib import Path
import json,re,sys,time,subprocess,shutil
p=Path('/home/foam/projects/openfoam/runs')/sys.argv[1]
assert p.name in ['extended-wing-analytic-motion-control-20261030','extended-wing-analytic-halfstep-20261030']
manifest=p/'cycle-execution.json'
while True:
 r=json.loads(manifest.read_text())
 if r.get('status')!='running':break
 time.sleep(10)
print('Observed original terminal result: '+json.dumps(r),flush=True)
assert r.get('exit_code') in [0,124],r
image='sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853'
name='openfoam-cycle-complete-'+('half' if 'halfstep' in p.name else 'coarse')
def execute(shell,timeout,log):
 cmd=['docker','run','--rm','--name',name,'--network','none','--cpus','4','--memory','4g','--user','1000:1000','-v',str(p)+':/case','-v','/mnt/g/projects/openfoam/build/check_analytic_cycle_positions.py:/analysis/positions.py:ro','-w','/case','--entrypoint','/bin/bash',image,'-c','source /usr/lib/openfoam/openfoam2412/etc/bashrc && '+shell]
 start=time.monotonic()
 with (p/log).open('x') as f:
  try:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:
   subprocess.run(['docker','stop','-t','5',name],stdout=f,stderr=subprocess.STDOUT);code=124
 return dict(command=cmd,exit_code=code,elapsed_seconds=time.monotonic()-start,status='process_completed' if code==0 else 'process_failed')
if r['exit_code']==124:
 assert not (p/'cycle-execution.attempt1.json').exists()
 for f in ['cycle-execution.json','log.pimpleFoam','launcher.log','system/controlDict']:
  q=p/f
  if q.exists():shutil.copy2(q,str(q)+'.attempt1' if f!='cycle-execution.json' else p/'cycle-execution.attempt1.json')
 times=[]
 for rank in range(4):
  times.append(max(float(q.name) for q in (p/f'processor{rank}').iterdir() if q.is_dir() and re.fullmatch(r'[0-9.eE+-]+',q.name) and (q/'U').exists() and (q/'polyMesh/points').exists()))
 assert len(set(times))==1 and .004<times[0]<.12,times
 (p/'resume-decision.json').write_text(json.dumps(dict(reason='Original bounded walltime expired; retain incomplete attempt and restart latest complete saved state. Preserve overlap rows for comparison.',checkpoint_s=times[0],original_exit_code=124,trace='wall-work-cycle-resume1.csv',new_timeout_s=9000),indent=2))
 f=p/'system/controlDict';s=f.read_text();assert 'startFrom latestTime;' in s and 'wall-work-cycle.csv' in s
 f.write_text(s.replace('wall-work-cycle.csv','wall-work-cycle-resume1.csv'))
 manifest.write_text(json.dumps(dict(status='running',phase='resume1',checkpoint_s=times[0])))
 result=execute('mpirun -np 4 pimpleFoam -parallel > log.pimpleFoam 2>&1',9000,'resume1-launcher.log')
 manifest.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 if result['exit_code']:raise SystemExit(result['exit_code'])
result=execute("reconstructPar -time '0.004:0.12' > log.reconstructAll 2>&1 && checkMesh -allTopology -meshQuality -time '0.004:0.12' > log.allMovedQuality 2>&1 && /opt/precice-python/bin/python /analysis/positions.py > log.allPositions 2>&1",1800,'all-checks-launcher.log')
q=(p/'log.allMovedQuality').read_text() if (p/'log.allMovedQuality').exists() else ''
result.update(mesh_ok_count=q.count('Mesh OK.'),failed_check_lines=[s for s in q.splitlines() if 'Failed' in s],strict_sampled_quality_passed='Failed' not in q and q.count('Mesh OK.')>1)
(p/'cycle-verification-execution.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
raise SystemExit(result['exit_code'] or (0 if result['strict_sampled_quality_passed'] else 2))
