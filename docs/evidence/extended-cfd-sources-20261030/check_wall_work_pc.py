from pathlib import Path
import csv,json,math
p=Path('/home/foam/projects/openfoam/runs/extended-wing-analytic-motion-control-20261030');rows=[[float(v) for v in r] for r in csv.reader((p/'processor0/wall-work-pilot.csv').open())]
forces={}
for f in (p/'postProcessing/forces').rglob('force.dat'):
 for line in f.read_text().splitlines():
  if not line.strip() or line.lstrip().startswith('#'):continue
  a=[float(v) for v in line.split()];forces[round(a[0],12)]=a[1:4]
errors=[]
for row in rows:
 assert all(math.isfinite(v) for v in row),row
 ref=forces[round(row[0],12)];errors.append(max(abs(a-b) for a,b in zip(row[1:4],ref)))
assert len(rows)==20 and all(b[0]>a[0] for a,b in zip(rows,rows[1:]))
assert max(errors)<1e-8,max(errors)
work=sum(.5*(a[4]+b[4])*(b[0]-a[0]) for a,b in zip(rows,rows[1:]))
r=dict(scope='Native per-face force reduction equals native forces function output; applied wall-velocity power is recorded, not physical damping validation.',rows=len(rows),start_s=rows[0][0],end_s=rows[-1][0],max_force_difference_N=max(errors),force_gate_passed=True,power_min_W=min(r[4] for r in rows),power_max_W=max(r[4] for r in rows),sampled_trapezoid_work_J=work,face_counts=sorted(set(r[5] for r in rows)),native_field_lines=[x.strip() for x in (p/'log.pimpleFoam').read_text().splitlines() if 'wallWork nativeField=' in x][:2]);(p/'wall-work-verification.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
