from pathlib import Path
import subprocess,json,time
p=Path('/home/foam/projects/openfoam/runs/extended-wing-cfd-offset-20261030')
mem={line.split(':')[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()};assert mem['MemAvailable']>20*1024*1024
cmd=['docker','run','--rm','--name','openfoam-fine-wall-spacing-20261030','--network','none','--cpus','2','--memory','22g','--user','1000:1000','-v',str(p)+':/case','-v','/mnt/g/projects/openfoam/build/fine-wall-spacing-summary.py:/analysis/wall-spacing-summary.py:ro','-v','/mnt/g/projects/openfoam/build/summarize_mesh_reference.py:/analysis/summarize_mesh.py:ro','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','-c',"source /usr/lib/openfoam/openfoam2412/etc/bashrc && checkMesh -writeFields '(wallDistance)' -time 0 > log.wallDistance 2>&1 && /opt/precice-python/bin/python /analysis/wall-spacing-summary.py > log.wallSpacingSummary 2>&1"]
rpt=dict(command=cmd,scope='Reuse checked meshWave wall-distance/VTK-native identity and area-weighted wall-spacing analysis on new fine mesh. Geometric spacing, not yPlus or flow validation.',available_memory_kib=mem['MemAvailable']);start=time.monotonic()
with (p/'wall-spacing-launcher.log').open('w') as f:
 try:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=1200);rpt['exit_code']=r.returncode
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5','openfoam-fine-wall-spacing-20261030'],stdout=f,stderr=subprocess.STDOUT);rpt['exit_code']=124
rpt['elapsed_seconds']=time.monotonic()-start;(p/'wall-spacing-execution.json').write_text(json.dumps(rpt,indent=2));print(json.dumps(rpt));raise SystemExit(rpt['exit_code'])
