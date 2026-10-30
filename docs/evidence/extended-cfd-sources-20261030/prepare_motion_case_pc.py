from pathlib import Path
import shutil,json,hashlib,subprocess,time
base=Path('/home/foam/projects/openfoam/runs');src=base/'extended-wing-cfd-coarse-20261030';out=base/'extended-wing-prescribed-motion-20261030';out.mkdir(exist_ok=False)
# Numerical-quality pass permits a geometry-motion diagnostic, not a viscous-flow claim.
assert 'Mesh OK.' in (src/'log.scaledQuality').read_text()
shutil.copytree(src/'constant/polyMesh',out/'constant/polyMesh');(out/'system').mkdir();(out/'0').mkdir()
for name in ['fvSchemes','meshQualityDict','meshQualityDict.canonical']:
 shutil.copy2(src/'system'/name,out/'system'/name)
def header(obj,cls='dictionary'):return f'FoamFile {{version 2.0; format ascii; class {cls}; object {obj};}}\n'
freq=8.810675;period=1/freq
(out/'system/controlDict').write_text(header('controlDict')+f'''application moveDynamicMesh;
startFrom startTime; startTime 0; stopAt endTime; endTime {period:.16g}; deltaT {period/100:.16g};
writeControl timeStep; writeInterval 25; purgeWrite 0; writeFormat ascii; writePrecision 14; timeFormat general; timePrecision 14; runTimeModifiable false;
''')
(out/'constant/dynamicMeshDict').write_text(header('dynamicMeshDict')+'''dynamicFvMesh dynamicMotionSolverFvMesh;
motionSolverLibs ("libfvMotionSolvers.so");
solver displacementLaplacian;
displacementLaplacianCoeffs {diffusivity quadratic inverseDistance (wing);}
''')
(out/'system/fvSolution').write_text(header('fvSolution')+'''solvers {cellDisplacement {solver GAMG; tolerance 1e-10; relTol 0; smoother GaussSeidel; maxIter 300;}}
''')
s=(out/'system/fvSchemes').read_text();s=s.replace('ddtSchemes { default steadyState; }','ddtSchemes { default Euler; }');(out/'system/fvSchemes').write_text(s)
point=header('pointDisplacement','pointVectorField')+'''dimensions [0 1 0 0 0 0 0];
internalField uniform (0 0 0);
boundaryField {
inlet {type fixedValue; value uniform (0 0 0);}
outlet {type fixedValue; value uniform (0 0 0);}
farfield {type fixedValue; value uniform (0 0 0);}
wing {
 type codedFixedValue;
 value uniform (0 0 0);
 name prescribedNativeBending;
 codeInclude
 #{
 #include "IFstream.H"
 #};
 code
 #{
  static Foam::vectorField mode;
  if (mode.empty())
  {
    Foam::IFstream input(this->db().time().path()/this->db().time().constant()/"wingMode");
    if (!input.good()) FatalErrorInFunction << "Cannot read wingMode" << exit(FatalError);
    input >> mode;
  }
  if (mode.size()!=this->size()) FatalErrorInFunction << "wingMode point count mismatch" << exit(FatalError);
  const Foam::scalar factor=Foam::sin(2.0*3.14159265358979323846*8.810675*this->db().time().value());
  operator==(factor*mode);
 #};
}
}
'''
(out/'0/pointDisplacement').write_text(point)
manifest=dict(scope='Prescribed native first-bending mesh-motion component test, not CFD flow or coupled FSI. Coarse mesh fails viscous layer coverage (70.69%) despite passing numerical quality; no aerodynamic interpretation.',source_mesh=str(src),frequency_hz=freq,tip_amplitude_m=.0001,period_s=period,steps=100,flow_solver_executed=False,initial_velocity_note='Sine starts at zero displacement with nonzero prescribed velocity; only mesh-motion plumbing is tested.')
manifest['input_hashes']={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and 'polyMesh' not in str(p)};(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
assets=base/'extended-motion-assets-20261030'
cmd=['docker','run','--rm','--network','none','--cpus','2','--memory','8g','--user','1000:1000','-v',str(out)+':/case','-v',str(assets)+':/assets','-w','/case','--entrypoint','/bin/bash','sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853','-c','source /usr/lib/openfoam/openfoam2412/etc/bashrc && /assets/bin/wingPointMap > log.pointMap 2>&1 && /opt/precice-python/bin/python /assets/map_motion.py /case > log.mapMotion 2>&1']
r=subprocess.run(cmd,timeout=180);print(json.dumps(dict(case=str(out),mapping_exit_code=r.returncode)));raise SystemExit(r.returncode)
