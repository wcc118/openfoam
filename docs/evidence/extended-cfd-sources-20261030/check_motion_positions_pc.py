from pathlib import Path
import json,re,math,hashlib
import numpy as np
p=Path('/case')
def vectors(path):
 s=path.read_text();s=re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
 # OpenFOAM vector lists have count followed by opening parenthesis on separate lines.
 m=re.search(r'(?:^|\n)\s*(\d+)\s*\n\s*\(',s)
 if not m: raise ValueError('No vector list: '+str(path))
 n=int(m[1]);a=np.fromstring(s[m.end():].replace('(',' ').replace(')',' ').replace(';',' '),sep=' ')
 assert a.size==n*3,(path,n,a.size)
 return a.reshape(n,3)
a=np.loadtxt(p/'wing-points.dat',skiprows=1);ids=a[:,0].astype(int);original=a[:,1:]
mode=vectors(p/'constant/wingMode');assert mode.shape==original.shape
freq=8.810675;rows=[]
for t in sorted((q for q in p.iterdir() if q.is_dir() and re.fullmatch(r'[0-9.eE+-]+',q.name)),key=lambda q:float(q.name)):
 path=t/'polyMesh/points'
 if not path.exists():continue
 factor=math.sin(2*math.pi*freq*float(t.name));actual=vectors(path)[ids]
 error=np.linalg.norm(actual-original-factor*mode,axis=1)
 rows.append(dict(time_s=float(t.name),phase_cycles=freq*float(t.name),factor=factor,max_position_error_m=float(error.max()),rms_error_m=float(np.sqrt(np.mean(error**2))),max_actual_displacement_m=float(np.linalg.norm(actual-original,axis=1).max()),points_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
report=dict(scope='Independent saved-point verification against native patch indices and imposed mode; geometry only, not fluid or coupled FSI.',checked_phases=rows,all_observed_pass=bool(rows) and all(r['max_position_error_m']<1e-9 for r in rows),complete_cycle=bool(rows) and rows[-1]['phase_cycles']>.99999)
(p/'position-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
raise SystemExit(0 if report['all_observed_pass'] else 1)
