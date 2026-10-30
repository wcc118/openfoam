from pathlib import Path
import shutil,re,subprocess,time,json
p=Path('/home/foam/projects/openfoam/runs/extended-wing-motion-extension-20261030')
for name in ['system/controlDict','log.moveDynamicMesh','log.movedQuality','execution.json','position-verification.json','interior-displacement-check.json','log-summary.json']:
 if (p/name).exists():shutil.copy2(p/name,p/(name+'.cycle1'))
f=p/'system/controlDict';s=f.read_text().replace('startFrom startTime','startFrom latestTime');s=re.sub(r'endTime [^;]+;',f'endTime {3/8.810675:.16g};',s);f.write_text(s)
cmd=['docker','run','--rm','--name','openfoam-motion-repeat-20261030','--network','none','--cpus','2','--memory','12g','--user','1000:1000','-v',str(p)+':/case','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','/case/run.sh']
start=time.monotonic();rpt=dict(command=cmd,scope='Extend successful geometry-only experiment to three cycles; check drift and all saved mesh phases, not fluid temporal convergence.')
with (p/'repeat-launcher.log').open('w') as f:
 try:
  r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=900);rpt.update(exit_code=r.returncode)
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5','openfoam-motion-repeat-20261030'],stdout=f,stderr=subprocess.STDOUT);rpt.update(exit_code=124)
t=(p/'log.movedQuality').read_text() if (p/'log.movedQuality').exists() else '';rpt['strict_quality_passed']='Failed' not in t and t.count('Mesh OK.')==13;rpt['mesh_ok_count']=t.count('Mesh OK.')
rpt['elapsed_seconds']=time.monotonic()-start;(p/'repeat-execution.json').write_text(json.dumps(rpt,indent=2));print(json.dumps(rpt));raise SystemExit(rpt['exit_code'] or (0 if rpt['strict_quality_passed'] else 2))
