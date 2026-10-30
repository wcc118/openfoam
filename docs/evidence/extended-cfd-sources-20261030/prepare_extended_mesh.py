from pathlib import Path
import importlib.util,json,hashlib,shutil,math
repo=Path('/tmp/openfoam-uvlm-verification')
base=Path('/home/connellwc83/projects/openfoam/runs')
out=base/'extended-wing-cfd-20261030';out.mkdir(exist_ok=False)
source=base/'mesh-trial30-wake-envelope-pc-20261025'
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
shell=module('shell',repo/'scripts/generate_aluminum_shell.py')
wing=module('wing',repo/'scripts/generate_wing.py')
points=33;poly=shell.perimeter(points,.1016);n=len(poly);span=2.4384
verts=[(x,y,z) for y in (-span/2,span/2) for x,z in poly]
faces=[]
for i in range(n):
 a=i;b=(i+1)%n;c=n+b;d=n+i;faces.extend([(a,d,b),(b,d,c)])
for side in [0,1]:
 off=side*n
 def lo(i):return off+i
 def up(i):return off+(n-i if i not in (0,points-1) else i)
 for i in range(points-1):
  for t in [(lo(i),lo(i+1),up(i)),(lo(i+1),up(i+1),up(i))]:
   if len(set(t))==3:faces.append(t if side==0 else tuple(reversed(t)))
area=sum(poly[i][0]*poly[(i+1)%n][1]-poly[(i+1)%n][0]*poly[i][1] for i in range(n))/2
check=wing.validate(verts,faces,area*span)
(out/'constant/triSurface').mkdir(parents=True)
with (out/'constant/triSurface/wing.stl').open('w') as f:
 f.write('solid wing\n')
 for face in faces:
  norm=wing.normal(verts,face);norm=[v/math.sqrt(sum(w*w for w in norm)) for v in norm]
  f.write('facet normal '+' '.join(f'{v:.15g}' for v in norm)+'\nouter loop\n')
  for i in face:f.write('vertex '+' '.join(f'{v:.15g}' for v in verts[i])+'\n')
  f.write('endloop\nendfacet\n')
 f.write('endsolid wing\n')
(out/'system').mkdir();(out/'0').mkdir()
for name in ['blockMeshDict','snappyHexMeshDict','surfaceFeatureExtractDict','fvSchemes','fvSolution','controlDict','slices']:
 shutil.copy2(source/'system'/name,out/'system'/name)
p=out/'system/blockMeshDict';s=p.read_text().replace('1.1176','1.7272').replace('(40 44 20)','(40 68 20)');p.write_text(s)
p=out/'system/snappyHexMeshDict';s=p.read_text()
for a,b in [('.56','1.1696'),('.67','1.2796'),('-.8 ','-1.4096 '),('1.2 .8 ','1.2 1.4096 '),('-.75 ','-1.3596 '),('.8 .75 ','.8 1.3596 '),('6000000','8000000')]:s=s.replace(a,b)
p.write_text(s)
# Existing slices are diagnostic; shift tip from the old semispan to the new.
p=out/'system/slices';s=p.read_text().replace('0.60','1.21').replace('0.6 ','1.21 ');p.write_text(s)
manifest=dict(scope='Extended 48-inch semispan provisional NACA4412 closed-TE shell midsurface used as CFD surface. No outer-skin offset; this remains a surrogate. Newly generated mesh, no stretched pressures.',span_m=span,chord_m=.1016,points_per_surface=points,surface_check=check,
 domain_bounds_m=[[-.508,-1.7272,-.508],[1.524,1.7272,.508]],mesh_source='trial30 settings adapted to doubled span, unchanged chord and quality/layer settings',
 source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [repo/'scripts/generate_aluminum_shell.py',repo/'scripts/generate_wing.py',Path(__file__)]})
manifest['input_hashes']={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(out/'run-mesh.sh').write_text('''source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1
set -eu
surfaceCheck -checkSelfIntersection constant/triSurface/wing.stl > log.surfaceCheck 2>&1
blockMesh > log.blockMesh 2>&1
surfaceFeatureExtract > log.surfaceFeatureExtract 2>&1
snappyHexMesh -overwrite > log.snappyHexMesh 2>&1
cp "$WM_PROJECT_DIR/etc/caseDicts/meshQualityDict" system/meshQualityDict
cp system/meshQualityDict system/meshQualityDict.canonical
checkMesh -allTopology -meshQuality > log.canonicalQuality 2>&1
sed -i 's/^minVol 1e-13;/minVol 1.048772096e-16;/' system/meshQualityDict
checkMesh -allTopology -meshQuality > log.scaledQuality 2>&1
checkMesh -allGeometry -allTopology > log.extended 2>&1
postProcess -func slices -time 0 > log.slices 2>&1
''')
print(out,check)
