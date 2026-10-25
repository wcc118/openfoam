# Parameterized wing surface

Generate a fresh output directory using Python's standard library:

```bash
python3 scripts/generate_wing.py --output runs/wing-unique
python3 scripts/generate_wing.py --airfoil 0012 --output runs/symmetric-unique
python3 -m unittest discover -s tests -v
```

Open `preview.html` directly in a browser. It has inline SVG oblique, section and
planform outlines, with no server, CDN, FreeCAD or ParaView dependency. `wing.stl`
is the closed surface; `section.csv` contains dimensional normal-offset section
coordinates. `geometry.json` records inputs, conventions, checks, source revision,
source hash and artifact hashes. Repeating inputs preserves geometry hashes;
timestamps/source provenance can differ. Existing directories are refused.

The default is a **demonstration**, not an owner-approved wing: NACA 4412, full span
1.2192 m, nominal chord 0.1016 m, S=0.12387072 m². No sweep or twist. All dimensions
are SI; x downstream, y span, z up. Moment origin is (.0254,0,0) m. The actual
bounding box slightly exceeds nominal chord due to normal offsets; do not clip
or rescale that geometry. Dimensions accepted in [1e-5,1e4] m are software bounds,
not evidence of engineering applicability over that range.

Options: `--airfoil 4412|0012`, `--span-m`, `--chord-m`, `--points` (9..1025,
default129 cosine stations), `--span-sections` (2..257, default2); product of the
last two is capped at100000. Two span sections exactly describe this extruded
polygon; intermediate coplanar sections add no shape detail. Surface triangles
are often slender. This is a geometry representation, **not a CFD volume mesh**;
volume-cell quality and boundary-layer resolution require separate checks.

## Reuse audit and checks

Audited `wcc118/aero` `panel_solver/geometry.py` at
`79c1236252fe12e0518384a33cd45c181e2df740`. Reused its NACA construction concept,
correcting the missing chordwise normal offsets. The standard `5*t` polynomial
already represents half thickness. Use the finite-TE coefficient -0.1015;
0012 TE half-thickness is .00126 times chord. Do not use the old cambered
`Airfoil.thickness` helper as a physical thickness oracle.

Independent coordinates use the normal-offset NACA 4412 table in
[PDAS sections](https://www.pdas.com/sections45.html), at exact mean-line stations
.1,.4,.8, with 1e-6 chord tolerance. See also
[PDAS thickness definition](https://www.pdas.com/naca456thick4.html).
Tests exercise 0012 symmetry, integrated section area, dimensional scaling,
deterministic exports, invalid inputs and deliberately corrupted surfaces.

The generator shares LE vertices, closes the finite TE and both tips, requires
finite/nonzero triangle areas, two opposite edge traversals, one connected
component and positive signed volume agreeing with section area times span.
It does not implement a general-purpose self-intersection detector. Run the
pinned OpenFOAM `surfaceCheck -checkSelfIntersection wing.stl` for each meshing
candidate. Its exit code alone is not acceptance: inspect the text findings.

## Native surface evidence and diagnostic

The two-section 4412 and 0012 baselines each have514 vertices/1024 triangles.
The pinned v2412 ARM64 runtime reported no illegal triangles, closed surface,
one connected part, one consistent-normal zone, no nearby points, and no
self-intersection for both. Evidence is in `docs/evidence/geometry-20261025.json`.

Retain an important adverse result: an earlier17-section 4412 export reported
one self-intersection (three for its equivalent OBJ). A diagnostic build of the
same v2412 surfaceCheck source added logging only, without changing the stock
algorithm. It showed edge11004 running from y=.45719999074935913 to
.38100001215934753 m, but the alleged intersection was at y=.51781986619311926 m,
outside that segment. This demonstrates a false positive for that reported hit;
it is not permission to ignore other checker findings. The default2-section
representation avoids unnecessary coplanar seams and passes the unmodified tool.
The 17-section 0012 also passed. Logs, diagnostic source and build remain in
`runs/surface-diagnostic-20261025` and `runs/wing-preview-20261025`.

No volume mesh, flow convergence, physical validation or flutter evidence is
implied by these surface checks. Tip, leading-edge and trailing-edge volume-mesh
behavior still need inspection in issue4.
