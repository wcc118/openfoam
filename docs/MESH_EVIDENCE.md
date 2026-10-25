# Mesh evidence reader

Bounded VTK surface file parser and checkMesh log interpreter for OpenFOAM wall-layer coverage gates.

## Purpose

Parse OpenFOAM legacy ASCII VTK POLYDATA files with `nSurfaceLayers` CELL_DATA field,
compute face/area coverage metrics, and combine with checkMesh log parsing for a
limited gate evaluation. This is an **engineering analysis tool**, not a solver,
physical validation, or flight clearance tool.

## CLI usage

```bash
python3 scripts/summarize_mesh.py \
  --wall-surface FILE \
  --mesh-log FILE \
  --requested-layers INT \
  --minimum-coverage FLOAT \
  --output JSON
```

### Required arguments

- `--wall-surface FILE`: OpenFOAM VTK POLYDATA surface file (legacy ASCII)
- `--mesh-log FILE`: checkMesh log file
- `--output JSON`: Output JSON file (exclusive creation, fails if exists)

### Optional arguments

- `--requested-layers INT`: Requested wall layers (default: 18)
- `--minimum-coverage FLOAT`: Minimum area coverage threshold (default: 0.9)

## Input format

### VTK surface file

OpenFOAM legacy ASCII VTK POLYDATA with:
- `POINTS N float`: Vertex coordinates
- `POLYGONS N INDICES`: Polygon definitions
- `CELL_DATA N` + `FIELD FieldData 1` + `nSurfaceLayers 1 1 float`: Layer counts per face

Example:

```vtk
# vtk DataFile Version 2.0
Surface evidence
ASCII
DATASET POLYDATA
POINTS 6 float
0 0 0
1 0 0
1 1 0
0 1 0
4 0 0
4 1 0
POLYGONS 2 10
4 0 1 2 3
4 1 4 5 2
CELL_DATA 2
FIELD FieldData 1
nSurfaceLayers 1 1 float
0
18
```

### checkMesh log

Expected patterns:
- `Failed N mesh checks.` → failure regardless of exit code
- `Mesh OK.` → pass only if no failures detected
- Missing explicit result → unknown/fail

## Output JSON schema

```json
{
  "input": {
    "wall_surface": "path",
    "wall_surface_hash": "sha256",
    "mesh_log": "path",
    "mesh_log_hash": "sha256"
  },
  "parameters": {
    "requested_layers": 18,
    "minimum_coverage": 0.9
  },
  "metrics": {
    "total_faces": 100,
    "total_area": 1.234,
    "faces_with_layers": 90,
    "area_with_layers": 1.111,
    "face_coverage": 0.9,
    "area_coverage": 0.9,
    "weighted_layer_count": 15.5,
    "max_layer": 18,
    "full_area": 1.234
  },
  "mesh_check": {
    "result": {
      "mesh_ok": true,
      "failed_checks": 0,
      "raw_status": "ok"
    }
  },
  "coverage": {
    "gate_passed": true,
    "minimum_coverage": 0.9,
    "actual_coverage": 0.95
  },
  "overall": {
    "status": "pass" | "gate_failure" | "input_error",
    "gate_passed": true
  }
}
```

## Exit codes

- `0`: Limited gate passed (mesh check passed AND coverage >= threshold)
- `1`: Gate failure (mesh check failed OR coverage below threshold OR malformed input)
- `2`: Input error (malformed VTK, truncated data, nonfinite values, size exceeded)

## Scope and limitations

- **Input**: Only OpenFOAM legacy ASCII VTK POLYDATA format
- **Output**: Bounded metrics for gate evaluation, no yPlus/flow/physical validity claim
- **Constraints**: Input ≤64 MiB, points/polygons ≤1,000,000
- **Rejection**: Malformed/truncated/nonfinite/binary/unsupported files rejected with error
- **Coverage**: Area-weighted, not face-count-weighted
- **No promises**: Passing this gate does NOT indicate physical validity, flight capability, or solver acceptance

## Tests

Run tests with:

```bash
python3 -m unittest tests.test_summarize_mesh -v
```

Tests include:
- Polygon area oracle (3D cross-sum method)
- VTK parsing (basic, with layers, TimeValue ignored)
- Malformed input detection (truncated, invalid indices, nonfinite, binary)
- Coverage metrics (unequal areas, swapped layers, max tracking)
- checkMesh log parsing (Mesh OK, failed checks, missing result)
- Full workflow integration (pass, coverage failure, mesh failure)
- Output file protection (refuse overwrite)
- Input error handling (exit code 2)

## Evidence

Source: wcc118/openfoam issue #10, parent #4.

Memory references:
- solver exit0 is NOT evidence of pass (memory:9fd63745cf5d5342a23379a28a3d9d12)
- Never weaken or skip failed facets/tests (from engineering workflow)
- Tests must assert known independent expected values
