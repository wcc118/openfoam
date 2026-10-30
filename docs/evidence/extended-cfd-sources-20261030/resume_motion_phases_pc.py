from pathlib import Path
import subprocess,json,time,re,shutil
p=Path('/home/foam/projects/openfoam/runs/extended-wing-prescribed-motion-20261030')
for name in ['system/controlDict','log.moveDynamicMesh','motion-execution.json']:
 shutil.copy2(p/name,p/(name+'.attempt2'))
f=p/'system/controlDict';s=f.read_text().replace('startFrom startTime','startFrom latestTime');s=re.sub(r'deltaT [^;]+;',f'deltaT {1/8.810675/4:.16g};',s);s=s.replace('writeInterval 25','writeInterval 1');f.write_text(s)
(p/'phase-restart-decision.json').write_text(json.dumps(dict(reason='The initial 25 small steps reached and independently verified the positive displacement peak (position error <5.1e-14 m). Continue the remaining three quarter-cycle phases with larger geometry-only steps to check return, negative peak and final return. This elliptic mesh-motion component check is not fluid temporal-resolution evidence.',prior_attempt='Interrupted intentionally after saved quarter-period; retain attempt2 logs and exit137.',remaining_steps=3),indent=2))
cmd=['docker','run','--rm','--name','openfoam-extended-motion-phases-20261030','--network','none','--cpus','4','--memory','12g','--user','1000:1000','-v',str(p)+':/case','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','/case/run-motion.sh']
start=time.monotonic();rpt=dict(command=cmd,status='running')
with (p/'motion-phases-launch.log').open('w') as f:
 try:
  r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=600);rpt.update(exit_code=r.returncode,status='completed' if r.returncode==0 else 'failed')
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5','openfoam-extended-motion-phases-20261030'],stdout=f,stderr=subprocess.STDOUT);rpt.update(exit_code=124,status='timeout')
rpt['elapsed_seconds']=time.monotonic()-start;(p/'motion-phases-execution.json').write_text(json.dumps(rpt,indent=2));print(json.dumps(rpt));raise SystemExit(rpt['exit_code'])
