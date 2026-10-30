from pathlib import Path
import shutil,subprocess,json
base=Path('/home/foam/projects/openfoam/runs');src=base/'extended-wing-transient-pilot-20261030';out=base/'extended-wing-transient-parallel-20261030';assets=base/'extended-motion-assets-20261030';out.mkdir(exist_ok=False)
for name in ['constant','system','0']:shutil.copytree(src/name,out/name)
# Preserve the steady checkpoint face flux when available; its reference mesh matches.
phi=src/'100/phi'
if phi.exists():shutil.copy2(phi,out/'0/phi')
f=out/'system/fvSchemes';s=f.read_text().replace('laplacianSchemes {','laplacianSchemes { laplacian(diffusivity,cellDisplacement) Gauss linear uncorrected;');f.write_text(s)
manifest=json.loads((src/'manifest.json').read_text());manifest.update(mpi_ranks=4,preserved_initial_phi=phi.exists(),mesh_motion_scheme='Dedicated uncorrected Laplacian, passed all five full-cycle saved mesh-quality checks in geometry-only experiment. Residual interior drift retained in report.',scope='Five-step parallel prescribed-motion CFD diagnostic, not coupled FSI or damping estimate. Wall-layer gate still failed.');(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
script='source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1\nset -eu\ndecomposePar > log.decomposePar 2>&1\nmpirun -np 4 /assets/bin/wingPointMap -parallel > log.pointMap 2>&1\nfor rank in 0 1 2 3; do /opt/precice-python/bin/python /assets/map_motion_caps.py /case/processor${rank} > log.mapMotion.${rank} 2>&1; done\n'
(out/'prepare.sh').write_text(script)
cmd=['docker','run','--rm','--network','none','--cpus','4','--memory','16g','--user','1000:1000','-v',str(out)+':/case','-v',str(assets)+':/assets:ro','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','/case/prepare.sh']
r=subprocess.run(cmd,timeout=300);print(json.dumps(dict(exit_code=r.returncode,case=str(out),preserved_initial_phi=phi.exists())));raise SystemExit(r.returncode)
