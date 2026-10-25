"""One-off x86 qualification adapter; retained with raw run evidence."""
import hashlib, importlib.util, json, platform, subprocess
from pathlib import Path
from datetime import datetime, timezone
root=Path('/home/foam/projects/openfoam')
spec=importlib.util.spec_from_file_location('qualification',root/'scripts/qualify_runtime.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
q.OPENFOAM_IMAGE='opencfd/openfoam-default@sha256:adbf625ac47ed81b34018602a6caeb4076bfacc2046b2f8cd36f82adb376946b'
out=root/'runs/pc-runtime-20261025'
out.mkdir(parents=True,exist_ok=False)
r={'scope':'runtime qualification and within-host repeatability, not physical validation','status':'failed','architecture':platform.machine(),'image_reference':q.OPENFOAM_IMAGE,'started_utc':datetime.now(timezone.utc).isoformat(),'limits':{'cpus':2,'memory':'2g'},'adapter_sha256':q.sha256_file(__file__),'verifier_sha256':q.sha256_file(root/'scripts/qualify_runtime.py')}
try:
    q.require(platform.machine()=='x86_64','expected x86_64')
    p=subprocess.run(['docker','image','inspect',q.OPENFOAM_IMAGE],capture_output=True,text=True,check=True)
    (out/'image-inspect.json').write_text(p.stdout)
    identity=json.loads(p.stdout)[0]
    q.require(identity['Architecture']=='amd64' and identity['Os']=='linux','wrong platform')
    r['image_id']=identity['Id']
    r['source_revision']=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    (out/'run.sh').write_text(q.SHELL_PAYLOAD)
    command=q.container_command(out)
    p=subprocess.run(command,capture_output=True,text=True)
    r['command']=command;r['exit_code']=p.returncode
    (out/'container_stdout.log').write_text(p.stdout);(out/'container_stderr.log').write_text(p.stderr)
    q.require(p.returncode==0,'container failed')
    r['checks']=q.verify_acceptance(out)
    r['status']='passed'
except Exception as e:
    r['error']=str(e)
finally:
    r['finished_utc']=datetime.now(timezone.utc).isoformat()
    r['artifacts_sha256']={str(p.relative_to(out)):q.sha256_file(p) for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'qualify_report.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
print(json.dumps(r,indent=2))
raise SystemExit(0 if r['status']=='passed' else 1)
