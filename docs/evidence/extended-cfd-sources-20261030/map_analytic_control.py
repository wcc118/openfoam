from pathlib import Path
import sys,json,hashlib
import numpy as np
p=Path(sys.argv[1]);a=np.loadtxt(p/'wing-points.dat',skiprows=1);u=np.zeros((len(a),3));u[:,2]=.0001*np.minimum(abs(a[:,2])/1.2192,1.)**2
with (p/'constant/wingMode').open('w') as f:
 f.write(str(len(u))+'\n(\n');f.writelines('('+' '.join(f'{v:.17g}' for v in row)+')\n' for row in u);f.write(')\n')
r=dict(scope='Analytic prescribed-wall control, not a native structural mode or FSI: u_z=0.1mm*min(abs(y)/1.2192m,1)^2*sin(2pi*8.810675Hz*t); u_x=u_y=0.',points=len(u),max_amplitude_m=float(u[:,2].max()),point_map_sha256=hashlib.sha256((p/'wing-points.dat').read_bytes()).hexdigest());(p/'analytic-map-report.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
