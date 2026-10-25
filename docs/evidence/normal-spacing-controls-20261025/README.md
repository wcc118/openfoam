# Ideal normal-spacing quality controls

27-cell orthogonal-grid controls for issue#4, using the chord-normalized volume
floor from [MESH_ACCEPTANCE.md](../../MESH_ACCEPTANCE.md). All dimensionless thresholds remain
unchanged from the canonical v2412 meshQualityDict.

## Experimental design

Three coarse-surface-face configurations with fixed in-plane dimensions
L=1.5875mm and out-of-plane thicknesses h=8/12/20μm:

| Case | Cell dimensions (L, L, h), mm | h/L | Analytic volume (m³) |
| --- | --- | --- | --- |
| spacing8um | (1.5875, 1.5875, 0.008) | 0.005038 | 2.016125e-11 |
| spacing12um | (1.5875, 1.5875, 0.012) | 0.007557 | 3.0241875e-11 |
| spacing20um | (1.5875, 1.5875, 0.020) | 0.012594 | 5.0403125e-11 |

The chord floor is `1e-13 * 0.1016³ = 1.048772096e-16 m³`, identical to
[MESH_ACCEPTANCE.md](../../MESH_ACCEPTANCE.md).

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
definition documented in [MESH_ACCEPTANCE.md](../../MESH_ACCEPTANCE.md) ("Why the two determinant
reports differ"). The extended metric uses internal/coupled faces only, forms a sum of
squared face-area vectors normalized by average internal face area, and
reports determinant magnitude divided by8. In contrast, the numerical-quality
metric includes all faces and uses area-weighted unit-normal outer products,
normalized by total area and the cube value1/27.

| Case | Small-determinant cells | Status |
| --- | ---: | --- |
| spacing8um | 27 | fail |
| spacing12um | 27 | fail |
| spacing20um | 27 | fail |

**All 27 cells flag as underdetermined in all 3 cases.** This diagnostic is not
interchangeable with topologyQuality; it flags thin cells even when topologyQuality
passes. See [MESH_ACCEPTANCE.md](../../MESH_ACCEPTANCE.md) for the two distinct determinant definitions.

## Analytic numerical determinant

For an ideal rectangular cell, applying the numerical-quality definition gives:
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
Numerical-quality logs report **failing face counts**; extended logs report
flagged cell counts. Neither supplies these exact analytic numerical-metric values.

## Process exit status

All native processes exit 0 even when quality reports fail. Exit 0 does not
indicate mesh acceptance; a completed `Mesh OK.` numerical-quality report is one gate, alongside
coverage, spacing and the remaining checks.
See [MESH_EVIDENCE.md](../../MESH_EVIDENCE.md) for gate definitions.

## Control script provenance

`generate-controls.py` retains original absolute paths (Spark host) and is not
a portable CLI. `archive-sha256.json` covers the archived input and output files; do not modify
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
- `archive-sha256.json` — archived input/output file hashes
- `execution.json` — Docker execution parameters and outcomes
- `generate-controls.py` — control generation script
- `wing-trial16/` — related wing mesh evidence

These controls do not establish wing yPlus, flow convergence, flutter or flight capability.
