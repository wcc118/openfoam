from pathlib import Path
import shutil,json,re,subprocess,time
base=Path('/home/foam/projects/openfoam/runs');flow=base/'extended-wing-flow-diagnostic-20261030';motion=base/'extended-wing-prescribed-motion-20261030';out=base/'extended-wing-transient-pilot-20261030'
# Parallel steady run writes processor fields; reconstruct a snapshot in a separate case.
assert not out.exists();out.mkdir();shutil.copytree(flow/'constant',out/'constant');shutil.copytree(flow/'system',out/'system');shutil.copytree(flow/'0',out/'0')
for i in range(4):
 d=out/f'processor{i}';d.mkdir();shutil.copytree(flow/f'processor{i}'/'constant',d/'constant');shutil.copytree(flow/f'processor{i}'/'100',d/'100')
image='sha256:0e81e41e58ddd100d133d6bf51a088c49068842ca0108c355c51c94ee883b853'
basecmd=['docker','run','--rm','--network','none','--cpus','4','--memory','20g','--user','1000:1000','-v',str(out)+':/case','-w','/case','--entrypoint','/bin/bash',image]
r=subprocess.run(basecmd+['-c','source /usr/lib/openfoam/openfoam2412/etc/bashrc && reconstructPar -time 100 > log.reconstructSnapshot 2>&1'],timeout=240);assert r.returncode==0
for name in ['U','p','k','omega','nut']:shutil.copy2(out/'100'/name,out/'0'/name)
for name in ['U','p']:
 f=out/'0'/name;s=f.read_text();start=s.index('wing',s.index('boundaryField'));opening=s.index('{',start);depth=1;end=opening+1
 while depth:
  depth+=(s[end]=='{')-(s[end]=='}');end+=1
 bc='type movingWallVelocity; value uniform (0 0 0);' if name=='U' else 'type fixedFluxPressure; value uniform 0;'
 f.write_text(s[:opening]+'{ '+bc+' }'+s[end:])
shutil.copy2(motion/'0/pointDisplacement',out/'0/pointDisplacement')
for name in ['dynamicMeshDict','wingMode']:shutil.copy2(motion/'constant'/name,out/'constant'/name)
s=(out/'system/controlDict').read_text().replace('application simpleFoam','application pimpleFoam');s=re.sub(r'endTime [^;]+;','endTime 0.000005;',s);s=re.sub(r'deltaT [^;]+;','deltaT 0.000001;',s);s=s.replace('writeInterval 100','writeInterval 5');s+='\nadjustTimeStep no;\n';(out/'system/controlDict').write_text(s)
s=(out/'system/fvSchemes').read_text().replace('default steadyState','default Euler').replace('bounded Gauss','Gauss');(out/'system/fvSchemes').write_text(s)
(out/'system/fvSolution').write_text('FoamFile {version 2.0; format ascii; class dictionary; object fvSolution;}\nsolvers {\np {solver GAMG; tolerance 1e-8; relTol 0.05; smoother GaussSeidel;}\npFinal {$p; relTol 0;}\npcorr {$p; tolerance 1e-8; relTol 0;}\npcorrFinal {$pcorr;}\n"(U|k|omega)" {solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0.1;}\n"(U|k|omega)Final" {solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0;}\ncellDisplacement {solver GAMG; tolerance 1e-10; relTol 0; smoother GaussSeidel; maxIter 300;}\ncellDisplacementFinal {$cellDisplacement; relTol 0;}\n}\nPIMPLE {nOuterCorrectors 2; nCorrectors 2; nNonOrthogonalCorrectors 1; correctPhi true; moveMeshOuterCorrectors false;}\nrelaxationFactors {equations {".*" 1;}}\n')
(out/'manifest.json').write_text(json.dumps(dict(scope='Five-step prescribed-motion CFD plumbing and throughput pilot, NOT a damping estimate or coupled FSI.',mesh_layer_gate_passed=False,steady_initialization_iteration=100,steady_convergence_claim=False,steps=5,dt_s=1e-6,frequency_hz=8.810675,mean_tip_amplitude_m=.0001,source_revision='8338650',image=image,pressure='kinematic gauge m2/s2',axes='x downstream, y span, z up',rho_kg_m3=1.2250532683653954,area_m2=.24774144),indent=2));print(str(out))
