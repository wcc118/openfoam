from pathlib import Path
import subprocess,json,time,hashlib,shutil
root=Path('/home/connellwc83/projects/openfoam/runs/normal-spacing-controls-20261025');root.mkdir()
image='opencfd/openfoam-default@sha256:b8b674f7d634a7b272efa00beabfe13eefdfe9d83b28281522544d06d47a17e4'
report={'scope':'Ideal coarse-surface-face normal-spacing controls under reviewed chord-floor convention; all dimensionless thresholds unchanged','cases':{}}
for name,dx,dy,dz,floor in [('spacing8um',.0015875,.0015875,.000008,1e-13*.1016**3),('spacing12um',.0015875,.0015875,.000012,1e-13*.1016**3),('spacing20um',.0015875,.0015875,.000020,1e-13*.1016**3)]:
 p=root/name;(p/'system').mkdir(parents=True);x,y,z=3*dx,3*dy,3*dz
 (p/'system/blockMeshDict').write_text(f'''FoamFile {{version 2.0; format ascii; class dictionary; object blockMeshDict;}}
scale 1;
vertices ((0 0 0)({x} 0 0)({x} {y} 0)(0 {y} 0)(0 0 {z})({x} 0 {z})({x} {y} {z})(0 {y} {z}));
blocks (hex (0 1 2 3 4 5 6 7) (3 3 3) simpleGrading (1 1 1));
edges (); boundary (); defaultPatch {{name walls; type wall;}} mergePatchPairs ();
''')
 shutil.copy2('/home/connellwc83/projects/openfoam/runs/orthogonal-aspect-control-20261025/system/controlDict',p/'system/controlDict')
 for f in ['fvSchemes','fvSolution']:shutil.copy2(Path('/home/connellwc83/projects/openfoam/runs/orthogonal-aspect-control-20261025/system')/f,p/'system'/f)
 payload='''source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1
set -eu
'''
 canonical=Path('/home/connellwc83/projects/openfoam/runs/pyramid-volume-controls-v3-20261025/fine-canonical/system/meshQualityDict').read_text()
 assert 'minVol 1e-13;' in canonical
 (p/'system/meshQualityDict').write_text(canonical if floor is None else canonical.replace('minVol 1e-13;',f'minVol {floor:.17g};'))
 payload+='blockMesh > log.blockMesh 2>&1\ncheckMesh -allTopology -meshQuality > log.topologyQuality 2>&1\ncheckMesh -allGeometry -allTopology > log.extended 2>&1\n'
 (p/'run.sh').write_text(payload)
 cmd=['docker','run','--rm','--pull','never','--network','none','--memory','512m','--cpus','1','--user','1000:1000','--mount',f'type=bind,src={p},dst=/work','--workdir','/work','--entrypoint','/bin/bash',image,'/work/run.sh']
 t=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
 (p/'stdout.log').write_text(r.stdout);(p/'stderr.log').write_text(r.stderr)
 log=(p/'log.topologyQuality').read_text() if (p/'log.topologyQuality').exists() else ''
 report['cases'][name]={'command':cmd,'exit_code':r.returncode,'elapsed_s':time.monotonic()-t,'cell_dimensions_m':[dx,dy,dz],'analytic_cell_volume_m3':dx*dy*dz,'analytic_face_pyramid_volume_m3':dx*dy*dz/6,'minVol_override':floor,'quality_dict_mesh_pass':'Mesh OK.' in log,'sha256':{str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file() and (f.name.startswith('log.') or f.parent.name=='system')}}
 print(name,r.returncode,'Mesh OK.' in log,flush=True)
(root/'execution.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

if any(v['exit_code']!=0 for v in report['cases'].values()):raise SystemExit(1)
