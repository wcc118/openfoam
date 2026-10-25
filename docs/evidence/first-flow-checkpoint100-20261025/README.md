# First wing-flow checkpoints

These are diagnostic snapshots of the provisional NACA4412 rigid wing at 30 m/s
and 4° incidence, using the trial9 mesh with 2,850,441 cells. They do not establish
convergence, physical validity, flutter behavior or flight performance. SIMPLE
iteration labels are not physical seconds.

The first run requested 500 iterations but reached its 1,800-second execution
limit after 333 complete iterations, with iteration334 partially executed.
The container was stopped successfully; no final500 fields exist. The isolated
iteration100 and iteration300 reconstructions are retained separately. Their
successful execution is not successful completion of the original solve.

## Provenance

The six original JSON/Python inputs are unchanged from primary input commit
`9d3b6c4`. Source setup revision is `48a6f9b47e6c66b271c90a4bd6fa64a14ff82c08`.
`source-manifest.json` records mesh hashes, atmospheric inputs, reference values,
axes and field setup. `execution.json` records the successful iteration100
reconstruction, exit0 in24.5s. These native results were executed by primary
Codex; the documentation worker did not execute the CFD case.

Raw cases remain outside Git:

- PC source: `/home/foam/projects/openfoam/runs/wing-flow-alpha4-pc-20261025`
- Spark checkpoint: `runs/wing-flow-alpha4-checkpoint100-pc-20261025`
- Spark later checkpoint: `runs/wing-flow-alpha4-checkpoint300-pc-20261025`
- PC preview: `G:\projects\openfoam\runs\wing-baseline-pc-20261025\flow-preview.html`

The preview can advance to later checkpoints; the JSON records fix each snapshot.
The archived scripts retain their original absolute paths and are one-off
analysis records, not supported general-purpose tools. Full fields and native
mesh files are required to reproduce their calculations.

## Independent extraction

Mesh hashes were compared with the source manifest. Polygon geometry was
independently integrated in native face order; triangle and translated-square
geometry oracles are in `prepare-wing-integration.py`. Force agreement below
checks the resulting integration, not a separate comparison of every native
face centre or normal.

The pressure boundary is zeroGradient with no stored boundary value; wall p is
read from each face's owner cell. Kinematic pressure and wallShearStress give
force `rho * (p * Sf - wallShearStress * area)`, with fluid-domain outward Sf.
Moments use quarter-chord origin `(0.0254, 0, 0)` m. Drag/lift directions and
reference normalization follow the source manifest.

| Diagnostic | Iteration100 | Iteration300 |
| --- | ---: | ---: |
| Maximum force-component discrepancy, N | 1.77e-12 | 2.23e-12 |
| Maximum moment-component discrepancy, N m | 3.49e-14 | 7.94e-14 |
| Relative net boundary mass imbalance | 3.124e-8 | 5.985e-9 |
| Area-weighted yPlus median | 0.9523 | 0.9547 |
| Area-weighted yPlus 95th percentile | 4.1787 | 4.4918 |
| Wall area above yPlus2 | 10.196% | 9.829% |

Force agreement is consistent with written field precision and verifies
extraction, not physical accuracy. The yPlus95 target is <=2: both checkpoints
miss it. No final500 window or repeatability assessment is available.

At iteration100, trailing10%chord contains53.77% of the failing area and outer
5%span contains31.01%. These regions can overlap. `yplus-regions.json` preserves
the region definitions and denominators; face-count weighting is not used.

## Later execution records

`later/iteration300-analysis.json` and `later/initial-run-execution.json` retain
the later checkpoint and timeout. The first iteration300 reconstruction failed
because a primary script substitution changed Docker UID/GID1000 to3000.
`later/reconstruction300-failed.json` preserves that failure; the corrected
1000:1000 retry succeeded and is recorded separately. The original flow case
was unaffected. This was an orchestration error, not a CFD-model failure.

Validation of this archive includes byte comparison of the original six files
against commit9d3b6c4 and `git diff --check`. It does not rerun the CFD analysis.
Mesh/domain sensitivity and physical reference validation remain outstanding.
