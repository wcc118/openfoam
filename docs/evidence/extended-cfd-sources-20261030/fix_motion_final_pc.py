from pathlib import Path
import shutil,json
p=Path('/home/foam/projects/openfoam/runs/extended-wing-prescribed-motion-20261030')
for name in ['log.moveDynamicMesh','motion-execution.json','system/fvSolution']:shutil.copy2(p/name,p/(name+'.attempt1'))
f=p/'system/fvSolution';s=f.read_text();assert s.count('maxIter 300;}}')==1;s=s.replace('maxIter 300;}}','maxIter 300;} cellDisplacementFinal {$cellDisplacement; relTol 0;}}');f.write_text(s)
(p/'attempt1-decision.json').write_text(json.dumps(dict(status='failed_configuration',reason='moveDynamicMesh requested cellDisplacementFinal missing from fvSolution; add final solver inheriting same1e-10 tolerance and relTol0. No timestep or quality tolerance change.'),indent=2))
