from pathlib import Path
import shutil,subprocess,json,time
base=Path('/home/foam/projects/openfoam/runs');src=base/'extended-wing-cfd-coarse-20261030';out=base/'extended-wing-plumbing-mesh-20261030';out.mkdir(exist_ok=False)
shutil.copytree(src/'system',out/'system');(out/'constant').mkdir();shutil.copytree(src/'constant/triSurface',out/'constant/triSurface');(out/'0').mkdir()
f=out/'system/blockMeshDict';f.write_text(f.read_text().replace('(40 68 20)','(40 16 20)'))
f=out/'system/snappyHexMeshDict';s=f.read_text().replace('addLayers true','addLayers false').replace('level 6','level 5').replace('level (4 5)','level (3 4)').replace('((.02 3)(.06 2)(.12 1))','((.02 2)(.06 1)(.12 0))').replace('((1e15 3))','((1e15 2))').replace('wake {mode inside; levels ((1e15 2))','wake {mode inside; levels ((1e15 1))').replace('outerWake {mode inside; levels ((1e15 1))','outerWake {mode inside; levels ((1e15 0))').replace('4000000','750000');f.write_text(s)
(out/'manifest.json').write_text(json.dumps(dict(scope='Deliberately coarse no-layer moving-flow plumbing experiment. NO viscous aerodynamic accuracy, damping validation, flutter or flight claim. Same extended closed-TE wing surface, coarsened span grid and refinement.',source_mesh_inputs=str(src),boundary_layers=False,base_grid=[40,16,20],surface_levels=[3,4],max_cell_target=750000,quality_thresholds='Unchanged canonical/scaled numerical checks',span_m=2.4384,chord_m=.1016),indent=2))
(out/'run.sh').write_text('source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\nsurfaceCheck -checkSelfIntersection constant/triSurface/wing.stl > log.surfaceCheck 2>&1\nblockMesh > log.blockMesh 2>&1\nsurfaceFeatureExtract > log.surfaceFeatureExtract 2>&1\nsnappyHexMesh -overwrite > log.snappyHexMesh 2>&1\ncheckMesh -allTopology -meshQuality > log.scaledQuality 2>&1\n')
cmd=['docker','run','--rm','--name','openfoam-plumbing-mesh-20261030','--network','none','--cpus','2','--memory','4g','--user','1000:1000','-v',str(out)+':/work','-w','/work','--entrypoint','/bin/bash','opencfd/openfoam-default@sha256:adbf625ac47ed81b34018602a6caeb4076bfacc2046b2f8cd36f82adb376946b','/work/run.sh'];start=time.monotonic();rpt=dict(command=cmd)
with (out/'launcher.log').open('w') as f:
 try:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=300);rpt['exit_code']=r.returncode
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','5','openfoam-plumbing-mesh-20261030'],stdout=f,stderr=subprocess.STDOUT);rpt['exit_code']=124
rpt['elapsed_seconds']=time.monotonic()-start;(out/'execution.json').write_text(json.dumps(rpt,indent=2));print(json.dumps(rpt));raise SystemExit(rpt['exit_code'])
