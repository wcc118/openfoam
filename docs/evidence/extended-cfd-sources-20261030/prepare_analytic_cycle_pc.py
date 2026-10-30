from pathlib import Path
import json,shutil,re
p=Path('/home/foam/projects/openfoam/runs/extended-wing-analytic-motion-control-20261030')
assert json.loads((p/'wall-work-verification.json').read_text())['force_gate_passed']
assert json.loads((p/'execution.json').read_text())['strict_moved_quality_passed']
for name in ['execution.json','log.pimpleFoam','log.movedQuality','log.reconstructPar','system/controlDict']:
 shutil.copy2(p/name,p/(name+'.work-pilot'))
f=p/'system/controlDict';s=f.read_text();s=re.sub(r'endTime [^;]+;','endTime 0.12;',s);s=s.replace('writeInterval 10','writeInterval 50').replace('wall-work-pilot.csv','wall-work-cycle.csv');f.write_text(s)
assert not (p/'processor0/wall-work-cycle.csv').exists()
(p/'cycle-manifest.json').write_text(json.dumps(dict(scope='One full observed prescribed-motion cycle plus end margin, analytic parabolic wall shape on no-layer mesh. NOT native modal feedback, physical damping validation or flutter.',start_s=.004,end_s=.12,dt_s=.0001,frequency_hz=8.810675,period_s=1/8.810675,body_motion='0.1mm*min(abs(y)/1.2192m,1)^2*sin(2pi*f*t), z only',work_trace='Actual native per-face force dot actual boundary U, global MPI reduction. Start includes inherited startup transient; no periodic-convergence claim.',first_full_observed_cycle_start_s=.004,first_full_observed_cycle_end_s=.004+1/8.810675,walltime_limit_s=2400),indent=2));print('prepared bounded prescribed-motion cycle')
