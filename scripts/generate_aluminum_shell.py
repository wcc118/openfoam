"""Owner-defined hollow aluminum surrogate: 2D CQUAD4 shells in 3D coordinates."""
import argparse
import hashlib
import json
import math
from pathlib import Path

E, NU, RHO = 71.7e9, 0.33, 2810.


def perimeter(points, chord):
    # Normal-offset NACA4412; closed TE (-0.1036), unlike CFD finite TE.
    upper, lower = [], []
    for i in range(points):
        x = (1-math.cos(math.pi*i/(points-1)))/2
        if x < .4:
            yc, slope = .04/.4**2*(.8*x-x*x), .08/.4**2*(.4-x)
        else:
            yc, slope = .04/.6**2*(.2+.8*x-x*x), .08/.6**2*(.4-x)
        yt = .6*(.2969*math.sqrt(x)-.126*x-.3516*x*x+.2843*x**3-.1036*x**4)
        if i in (0, points-1):
            yt = 0.
        theta = math.atan(slope)
        upper.append((chord*(x-yt*math.sin(theta)), chord*(yc+yt*math.cos(theta))))
        lower.append((chord*(x+yt*math.sin(theta)), chord*(yc-yt*math.cos(theta))))
    return lower + list(reversed(upper[1:-1]))


def real(value):
    # MYSTRAN free-field real fields must retain a decimal and fit 16 columns.
    return f'{value:.8E}'


def card(name, *values):
    return ','.join([name]+[real(x) if isinstance(x, float) else str(x) for x in values])


def model(points=17, sections=25, span=1.2192, chord=.1016, thickness=.00127):
    if type(points) is not int or not 5 <= points <= 129:
        raise ValueError('points must be integer 5..129 per surface')
    if type(sections) is not int or not 2 <= sections <= 257:
        raise ValueError('sections must be integer 2..257')
    if not all(math.isfinite(v) and 0 < v <= 10 for v in (span, chord, thickness)):
        raise ValueError('dimensions must be positive finite metres, <=10')
    if thickness >= .05*chord:
        raise ValueError('thickness outside this thin-shell surrogate scope')
    poly = perimeter(points, chord)
    n = len(poly)
    nodes = [(x, span*j/(sections-1), z) for j in range(sections) for x,z in poly]
    # CCW x-z perimeter: edge cross +y is outward.
    quads = [(j*n+i+1, j*n+(i+1)%n+1, (j+1)*n+(i+1)%n+1, (j+1)*n+i+1)
             for j in range(sections-1) for i in range(n)]
    lengths = [math.dist(poly[i],poly[(i+1)%n]) for i in range(n)]
    area = sum(lengths)*span
    xc = sum(x for x,z in poly)/n
    zc = sum(z for x,z in poly)/n
    polar = sum((x-xc)**2+(z-zc)**2 for x,z in poly)
    loads = {
        'bending': [(0.,0.,1./n) for _ in poly],
        'torsion': [((z-zc)/polar,0.,-(x-xc)/polar) for x,z in poly],
    }
    origin = (xc,0.,zc)
    resultants = {}
    for name, forces in loads.items():
        force = [sum(f[k] for f in forces) for k in range(3)]
        moments = [0.,0.,0.]
        for (x,z), f in zip(poly,forces):
            r = (x-xc,span,z-zc)
            for k in range(3):
                moments[k] += r[(k+1)%3]*f[(k+2)%3]-r[(k+2)%3]*f[(k+1)%3]
        resultants[name] = {'force_N':force,'moment_Nm':moments}
    decks = {}
    common = [card('MAT1',1,E,'',NU,RHO),card('PSHELL',1,1,thickness,1,1.,1,5./6.,0.)]
    common += [card('GRID',i+1,'',*v) for i,v in enumerate(nodes)]
    common += [card('CQUAD4',i+1,1,*q) for i,q in enumerate(quads)]
    common += [card('SPC1',1,123456,i+1) for i in range(n)]
    for name in ('bending','torsion','modal'):
        lines = ['SOL '+('103' if name=='modal' else '101'),'CEND','ECHO = NONE',
                 'SPC = 1','DISPLACEMENT = ALL','SPCFORCE = ALL',
                 'METHOD = 3' if name=='modal' else 'LOAD = 2','BEGIN BULK']
        lines += common
        if name=='modal':
            lines += [card('EIGRL',3,'','',10)]
        else:
            lines += [card('FORCE',2,(sections-1)*n+i+1,0,1.,*f) for i,f in enumerate(loads[name])]
        decks[name] = '\n'.join(lines+['ENDDATA'])+'\n'
    manifest = {'model':'continuous hollow aluminum surrogate; 2D quadrilateral shell elements',
        'span_m':span,'chord_m':chord,'thickness_m':thickness,'points_per_surface':points,
        'span_sections':sections,'perimeter_nodes':n,'node_count':len(nodes),'element_count':len(quads),
        'E_Pa':E,'nu':NU,'G_Pa':E/(2*(1+NU)),'rho_kg_m3':RHO,'mass_kg':area*thickness*RHO,
        'midsurface_area_m2':area,'min_panel_area_m2':min(lengths)*span/(sections-1),
        'axes':{'x':'chord downstream','y':'root to tip','z':'up'},'moment_origin_m':origin,
        'resultants':resultants,'overlap_m':.2032,'overlap_model':'metadata only; no double skin/contact',
        'geometry':'provisional NACA4412 midsurface with closed TE coefficient -0.1036',
        'boundary':'all six DOFs clamped at y=0; free uncapped tip',
        'omissions':['internal spars','joint compliance','carbon anisotropy','end caps','damping','prestress'],
        'material_source':'ASM/MatWeb AA typical MA7075T6; elastic surrogate, not allowables',
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'deck_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in decks.items()}}
    return nodes,quads,loads,decks,manifest


def generate(output, **kwargs):
    nodes,quads,loads,decks,manifest = model(**kwargs)
    path=Path(output)
    path.mkdir(parents=True,exist_ok=False)
    for name,deck in decks.items():
        (path/(name+'.bdf')).write_text(deck)
    (path/'model.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    (path/'mesh.json').write_text(json.dumps({'nodes':nodes,'quads':quads}))
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True)
    p.add_argument('--points',type=int,default=17)
    p.add_argument('--sections',type=int,default=25)
    a=p.parse_args()
    print(json.dumps(generate(a.output,points=a.points,sections=a.sections),indent=2))
