from pathlib import Path
import shutil,subprocess,json,time,tarfile,hashlib
base=Path('/home/foam/projects/openfoam/runs');out=base/'issue38-interface-v3-20261030';mesh=base/'issue38-span32-20261030';out.mkdir(exist_ok=False)
source=out/'source';source.mkdir();archive=Path('/mnt/g/projects/openfoam/build/issue38-interface-source-v3.tar.gz')
with tarfile.open(archive) as t:t.extractall(source,filter='data')
shutil.copy2(source/'check_native_exports.py',source/'scripts/check_native_exports.py')
shutil.copytree(mesh/'constant/polyMesh',out/'constant/polyMesh');shutil.copytree(mesh/'system',out/'system');(out/'0').mkdir()
(out/'system/controlDict').write_text('FoamFile {version 2.0; format ascii; class dictionary; object controlDict;}\napplication wingInterfaceExport; startFrom startTime; startTime 0; stopAt endTime; endTime 1; deltaT 1; writeControl timeStep; writeInterval 1; writeFormat ascii; writePrecision 17; runTimeModifiable false;\n')
(out/'system/decomposeParDict').write_text('FoamFile {version 2.0; format ascii; class dictionary; object decomposeParDict;}\nnumberOfSubdomains 4; method scotch;\n')
(out/'run.sh').write_text('source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\nexport FOAM_USER_APPBIN=/source/bin\nmkdir -p "$FOAM_USER_APPBIN"\n(cd /source/tools/wingInterfaceExport && wmake) > log.build 2>&1\n/source/bin/wingInterfaceExport > log.export.serial 2>&1\ndecomposePar > log.decompose 2>&1\nmpirun -np 4 /source/bin/wingInterfaceExport -parallel > log.export.parallel 2>&1\ncd /source\n/opt/precice-python/bin/python -m scripts.cfd_interface_transfer /case/interface.json --output /case/transfer-serial.json > /case/log.transfer 2>&1\n/opt/precice-python/bin/python -m unittest discover -s tests -p test_cfd_interface_transfer.py > /case/log.tests 2>&1\n/opt/precice-python/bin/python -m scripts.check_native_exports > /case/log.nativeVerification 2>&1\n')
name='issue38-interface-v3-20261030';cmd=['docker','run','--rm','--name',name,'--network','none','--cpus','4','--memory','6g','--user','1000:1000','-v',str(out)+':/case','-v',str(source)+':/source','-v',str(mesh)+':/mesh:ro','-v',str(base/'issue38-native-motion-20261030')+':/motion:ro','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','/case/run.sh'];start=time.monotonic()
with (out/'launcher.log').open('w') as f:
 try:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=600).returncode
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5',name],stdout=f,stderr=subprocess.STDOUT,timeout=30);code=124
r=dict(exit_code=code,elapsed_s=time.monotonic()-start,command=cmd,source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
(out/'execution.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(code)
