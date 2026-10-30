from pathlib import Path
import subprocess,json,time,shutil,sys
base=Path('/home/foam/projects/openfoam/runs');tag=sys.argv[1];assert tag in ('base','half');case=base/('issue38-native-pilot-'+tag+'-20261030')
shutil.copy2('/mnt/g/projects/openfoam/build/issue38-analyze-native-pilot.py',case/'pipeline/analyze_native_pilot.py')
name='issue38-analysis-'+tag
cmd=['docker','run','--rm','--name',name,'--network','none','--cpus','1','--memory','4g','--user','1000:1000','-v',str(case)+':/case','-v',str(base/'extended-motion-assets-20261030')+':/mapping:ro','-w','/case','--entrypoint','/opt/precice-python/bin/python','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','/case/pipeline/analyze_native_pilot.py']
start=time.monotonic()
with (case/'log.pilotAnalysis').open('w') as f:
 try:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=300).returncode
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5',name],stdout=f,stderr=subprocess.STDOUT,timeout=30);code=124
result=dict(exit_code=code,elapsed_s=time.monotonic()-start,command=cmd);(case/'analysis-execution.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));raise SystemExit(code)
