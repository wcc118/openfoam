# Mesh evidence reader

`scripts/summarize_mesh.py` reads retained OpenFOAM wall-surface VTK and checkMesh
logs. Its limited gate requires explicit completed mesh-log success and sufficient
area with at least one layer. Passing does not establish yPlus, adequate layer
thickness, flow convergence, physical validity, or flight capability.

```bash
python3 scripts/summarize_mesh.py \
  --wall-surface runs/CASE/postProcessing/slices/0/wingSurface.vtk \
  --mesh-log runs/CASE/log.checkMesh \
  --requested-layers 18 --minimum-coverage 0.9 \
  --output runs/CASE/mesh-evidence.json
```

Supported input is legacy VTK **2.0 ASCII POLYDATA**: POINTS float/double,
POLYGONS, CELL_DATA and one FIELD named nSurfaceLayers with one component and
exactly one tuple per polygon. Optional top-level FIELD TimeValue is accepted.
Numeric arrays are whitespace-delimited, regardless of line wrapping. Other
formats/fields, missing arrays, invalid indices/counts, zero-area facets, nonfinite
values, and noninteger/negative/overrequested layer counts are rejected.
Each input is bounded to 64 MiB; points and polygons to one million each;
polygon size to 1024 vertices. These bounds limit accepted input, not peak Python
memory to 64 MiB.

Requested layers must be an integer in [1,1000]; minimum coverage must be finite
in [0,1]. Polygon area is the magnitude of its area vector, appropriate for these
surface facets, not a general reconstruction of curved or self-intersecting faces.
Metrics distinguish face coverage, area coverage (layers > 0), area-weighted
layer count, and area with the full requested layer count (`full_area` in square
metres, `full_area_coverage` as a fraction). Input coordinates must be metres.

An independent example has adjacent rectangles of widths 1 and 3, height 1.
Layer counts 0 and 18 give area coverage 0.75, face coverage 0.5, weighted layers
13.5, and full area 3. Swapping the counts gives area coverage 0.25 and weighted
layers 4.5. This catches accidental face-count weighting.

The JSON records absolute input paths, SHA-256 of original bytes (including line
endings), parameters, metrics, separate coverage and mesh-log outcomes, and the
limited overall result. `Failed N mesh checks.` or FOAM FATAL fails even if the
process exited zero. `Mesh OK.` requires a subsequent `End` marker; absent or
unfinished results remain unknown and cannot pass.

Exit codes: 0 limited gate pass, 1 observed gate failure, 2 input/output error.
Malformed surface evidence retains an input-error JSON when both inputs were
read successfully. Missing/unreadable/oversized inputs or invalid CLI parameters
fail before report creation. Output creation is exclusive; existing files are
never overwritten. Inputs are never modified.

Run all tests with `python3 -m unittest discover -s tests -v`. Tests cover unequal
area oracles, wrapping/metadata, finite values/counts/indices, bounds, completed
logs and failure precedence, raw-byte hashes, error reports, and no overwrite.
Source: issue #10, parent #4. Native rejected cases remain engineering evidence;
this reader cannot waive their mesh or layer deficiencies.
