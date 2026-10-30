exec(open('/check.py').read().replace("raise SystemExit(0 if report['all_observed_pass'] else 1)",''))
initial=vectors(p/'constant/polyMesh/points')
rows=[]
for r in report['checked_phases']:
 t=min((q for q in p.iterdir() if q.is_dir() and re.fullmatch(r'[0-9.eE+-]+',q.name)),key=lambda q:abs(float(q.name)-r['time_s']))
 current=vectors(t/'polyMesh/points');disp=np.linalg.norm(current-initial,axis=1)
 rows.append(dict(time_s=r['time_s'],max_all_mesh_displacement_m=float(disp.max()),rms_all_mesh_displacement_m=float(np.sqrt(np.mean(disp**2)))))
print(json.dumps(rows));(p/'interior-displacement-check.json').write_text(json.dumps(rows,indent=2))
