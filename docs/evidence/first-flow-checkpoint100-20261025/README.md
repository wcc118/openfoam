# First-flow checkpoint100 evidence archive

This directory contains immutable diagnostic evidence extracted from iteration100
of an unconverged steady-flow case. The original solve continues beyond this
checkpoint; this archive is a snapshot for analysis and reproduction.

## Reconstruction scope

**This is not convergence or physical validation.** The evidence is extracted from
a native OpenFOAM run that will continue to iteration500 (not completed at
archive time). SIMPLE iteration count is **not physical time**.

- Primary input commit: `9d3b6c4`
- Evidence directory: `docs/evidence/first-flow-checkpoint100-20261025`
- Source case (external, immutable): `/home/foam/projects/openfoam/runs/wing-flow-alpha4-pc-20261025`
- PC preview: `G:\projects\openfoam\runs\wing-baseline-pc-20261025\flow-preview.html`

## Source configuration (source-manifest.json)

| Parameter | Value |
|-----------|-------|
| Generator | `scripts/generate_flow_case.py` |
| Revision | `48a6f9b47e6c66b271c90a4bd6fa64a14ff82c08` |
| Mesh trial | `trial9` |
| Cells | 2,850,441 |
| Boundary patches | inlet, outlet, farfield, wing |
| Iterations requested | 500 |

Flow conditions:
- Speed: 30 m/s
- Angle of attack: 4°
- Density: 1.2250532683653954 kg/m³
- Kinematic viscosity: 1.4605775310347254e-5 m²/s
- Dynamic pressure: 551.273970764428 Pa

Geometry:
- Span: 1.2192 m
- Chord: 0.1016 m
- Reference area: 0.12387072 m²
- Moment origin: (0.0254, 0, 0) m

## Extraction command (execution.json)

```bash
docker run \
  --name openfoam-wing-checkpoint100-20261025 \
  --rm --pull never --network none --memory 6g --cpus 2 \
  --user 1000:1000 \
  --mount type=bind,src=/home/foam/projects/openfoam/runs/wing-flow-alpha4-checkpoint100-pc-20261025,dst=/work \
  --workdir /work \
  --entrypoint /bin/bash \
  opencfd/openfoam-default@sha256:adbf625ac47ed81b34018602a6caeb4076bfacc2046b2f8cd36f82adb376946b \
  -lc "source /usr/lib/openfoam/openfoam2412/etc/bashrc && reconstructPar -time 100 -fields '(p phi yPlus wallShearStress)' > log.reconstructPar 2>&1"
```

Exit code: 0, elapsed: 24.5 seconds.

## Key results (independent-checkpoint-analysis.json)

### Geometry verification

Geometry hashes verified against source mesh. Triangle polygon integration used
for area vectors and triangle-area-weighted centres. Independent calculation
confirms face normals and centres match native extraction.

### Force/moment agreement

Independent pressure-plus-viscous traction calculation using formula:
`rho * (p * Sf - wallShearStress * area)` with p=zeroGradient owner values.

| Metric | Independent | Native | Max difference |
|--------|-------------|--------|----------------|
| Force (N) | [-0.413, -2.38e-5, 34.75] | [-0.413, -2.38e-5, 34.75] | 1.77e-12 |
| Moment (Nm) | [0.000652, -0.349, 7.66e-5] | [0.000652, -0.349, 7.66e-5] | 3.48e-14 |

Coefficient agreement (Cd, Cl, CmPitch):
- Independent: [0.02946, 0.5080, -0.05037]
- Native: [0.02946, 0.5080, -0.05037]
- Absolute difference: [2.7e-15, 2.2e-14, 3.5e-15]

**Note:** Agreement is at machine precision. This verifies extraction, not
physical accuracy.

### Mass conservation

Boundary volume flux (m³/s):
- Inlet: -67.963
- Outlet: 68.010
- Farfield: -0.0470
- Wing: 0.0

Relative mass imbalance: 3.12e-08

### yPlus statistics (area-weighted)

| Metric | Value |
|--------|-------|
| Median | 0.952 |
| 95th percentile | 4.18 |
| 99th percentile | 11.9 |
| Maximum | 51.2 |
| Fraction above 2.0 | 10.2% |

### Spatial yPlus distribution (yplus-regions.json)

| Region | Area fraction | Share of failing area | Within region fraction > 2 |
|--------|--------------|----------------------|---------------------------|
| Tip 5% | 5.58% | 31.0% | 56.6% |
| Interior 95% | 94.4% | 69.0% | 7.45% |
| Leading 10% | 10.8% | 23.0% | 21.8% |
| Trailing 10% | 10.2% | 53.8% | 53.8% |

## Field hashes (independent-checkpoint-analysis.json)

```
p:            6f12bda14711b7fc7ae8d73c4e18faa4877167562af884d9ff2c10ac134d029a
phi:          bde40250e58403e50e86b62ec0c7b501f793d0cae37110d1a038f4257d15c797
yPlus:        ef21f0609e2f2f75f9b50a8407597c50cd196e19f80b46b1852c689b047d2023
wallShearStress: 24b877ef891d5c1789d10adc48dee50234dc1f2e6a988ab5e1da7eca834ea4ed
```

## Diagnostic scripts (archived one-off use only)

- `analyze-flow100.py`: Independent force/moment extraction from OpenFOAM fields
- `prepare-wing-integration.py`: Native-order polygon integration for wing surface

These scripts use absolute paths and are archived for reproducibility verification
only. They are not supported CLI tools.

## Limitations

1. **No convergence claim**: Iteration100 is early in a 500-iteration solve.
   Residual control, coefficient stability, and mesh convergence remain unverified.

2. **No physical validation**: Agreement at machine precision verifies numerical
   extraction, not correct physics or boundary conditions.

3. **No flutter or performance acceptance**: This is a single-point steady-state
   snapshot. Dynamic stability and flight-envelope qualification are separate work.

4. **External source case**: Raw multi-million-cell fields reside outside Git.
   This archive contains extracted statistics and verification scripts.

5. **Local PC preview**: PC preview HTML at `G:\projects\openfoam\runs\wing-baseline-pc-20261025\flow-preview.html`
   is not committed; use the archived JSON for analysis.

## Verification commands

```bash
# Verify evidence files unchanged from input commit
cd /home/connellwc83/.local/share/opencode-orchestration/isolated-checkouts/tmp.5ApW5HMo5l/checkout
git show 9d3b6c4:docs/evidence/first-flow-checkpoint100-20261025/ | grep -E '^100644'
sha256sum docs/evidence/first-flow-checkpoint100-20261025/*

# Check whitespace errors
git diff --check

# Verify git tree matches
git ls-tree 9d3b6c4 docs/evidence/first-flow-checkpoint100-20261025/
```

## Referencing

Link from `docs/FIRST_FLOW_CASE.md` using this directory path and commit reference.
