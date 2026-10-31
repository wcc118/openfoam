from pathlib import Path
import json,numpy as np
p=Path('/home/foam/projects/openfoam/runs/issue38-loaded-pilot-20261030');a=np.load(p/'solid/interface.npz');e=json.loads((p/'fluid/interface.json').read_text());assert e['point_ids']==a['point_ids'].tolist();err=float(np.max(abs(np.array(e['points_m'])-a['points'])));r=dict(case=p.name,max_saved_wall_change_m=err,point_count=len(e['point_ids']),scope='Only audit stationary CFD wall for retrospective startup control; invalid requested coupling window remains invalid.')
assert err<1e-12;(p/'frozen-wall-audit.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
