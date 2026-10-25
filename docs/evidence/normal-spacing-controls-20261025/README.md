# Ideal normal-spacing quality controls

27-cell orthogonal-grid controls for issue#4, using the chord-normalized volume
floor from `docs/MESH_ACCEPTANCE.md`. All dimensionless thresholds remain
unchanged from the canonical v2412 v2412 meshQualityDict.

## Experimental design

Three coarse-surface-face configurations with fixed in-plane dimensions
L=1.5875mm and out-of-plane thicknesses h=8/12/20μm:

| Case | Cell dimensions (L, L, h) | h/L | Analytic volume (m³) |
| --- | --- | --- | --- |
| spacing8um | (1.5875, 1.5875, 0.008) | 0.005038 | 2.016125e-11 |
| spacing12um | (1.5875, 1.5875, 0.012) | 0.007557 | 3.0241875e-11 |
| spacing20um | (1.5875, 1.5875, 0.020) | 0.012594 | 5.0403125e-11 |

The chord floor is `1e-13 * 0.1016³ = 1.048772096e-16 m³`, identical to
`docs/MESH_ACCEPTANCE.md`.

## Native topologyQuality checks

`checkMesh -allTopology -meshQuality` with canonical minDeterminant 0.001:

| Case | Failures | Status |
| --- | ---: | --- |
| spacing8um | 108 faces on cells with determinant < 0.001 | fail |
| spacing12um | 0 | pass |
| spacing20um | 0 | pass |

All 27 cells fail determinant checking for h=8μm; h=12μm and h=20μm pass.

## Extended determinant (allGeometry)

`checkMesh -allGeometry -allTopology` uses the alternative determinant
definition documented in `docs/MESH_ACCEPTANCE.md` ("Why the two determinant
reports differ"). This includes all cell faces and forms area-weighted unit-normal
outer products, normalizing by total area and by the cube value 1/27.

| Case | Small-determinant cells | Status |
| --- | ---: | --- |
| spacing8um | 27 | fail |
| spacing12um | 27 | fail |
| spacing20um | 27 | fail |

**All 27 cells flag as underdetermined in all 3 cases.** This diagnostic is not
interchangeable with topologyQuality; it flags thin cells even when topologyQuality
passes. See `docs/MESH_ACCEPTANCE.md` for the two distinct determinant definitions.

## Analytic numerical determinant

The ideal rectangular determinant formula from the canonical OpenFOAM source is:
```
D = 27 * L * h² / (L + 2*h)³
```

| Case | h (m) | D (analytic) | minDeterminant |
| --- | ---: | ---: | ---: |
| spacing8um | 8e-06 | 0.00066535064 | 0.001 |
| spacing12um | 1.2e-05 | 0.00147485410 | 0.001 |
| spacing20um | 2e-05 | 0.00397717314 | 0.001 |

The threshold 0.001 is unchanged from the canonical dimensionless limit.
spacing8um fails (D < 0.001); spacing12um and spacing20um exceed the threshold.
Native logs report **failed cell counts**, not these exact numerical values.

## Process exit status

All native processes exit 0 even when quality reports fail. Exit 0 does not
indicate mesh acceptance; only `Mesh OK.` in topologyQuality indicates pass.
See `docs/MESH_EVIDENCE.md` for gate definitions.

## Control script provenance

`generate-controls.py` retains original absolute paths (Spark PC host) and is not
a portable CLI. `archive-sha256.json` covers all existing inputs; do not modify
these hashes. The script is retained evidence, not a recommended workflow.

## Relationship to trial16

`wing-trial16` uses the chord-floor convention and passes topologyQuality
(`Mesh OK.`). Its area coverage 0.2148957454146394 fails the 0.9 gate, so it
remains unqualified for flow solves. This case is separate from the 27-cell
controls; it demonstrates a wing mesh that passes native quality checks but
still fails layer-coverage requirements.

## Evidence files

- `spacing{8,12,20}um/log.topologyQuality` — native quality check logs
- `spacing{8,12,20}um/log.extended` — extended determinant logs
- `spacing{8,12,20}um/log.blockMesh` — blockMesh execution logs
- `spacing{8,12,20}um/system/meshQualityDict` — canonical dictionary with chord floor
- `archive-sha256.json` — all input file hashes
- `execution.json` — Docker execution parameters and outcomes
- `generate-controls.py` — control generation script
- `wing-trial16/` — related wing mesh evidence (not a completed trial18 claim)

No completed-trial18 claims, yPlus guarantees, or flutter/flight inference.
