from pathlib import Path
import subprocess
p=Path('/home/foam/projects/openfoam/runs/extended-wing-analytic-motion-control-20261030')
r=subprocess.run(['docker','run','--rm','--network','none','--cpus','1','--memory','2g','--user','1000:1000','-v',str(p)+':/case','-v','/mnt/g/projects/openfoam/build/locate_cycle_mesh_failures_pc.py:/analysis.py:ro','--entrypoint','/opt/precice-python/bin/python','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','/analysis.py'],timeout=180)
raise SystemExit(r.returncode)
