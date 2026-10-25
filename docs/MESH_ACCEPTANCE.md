# Mesh acceptance: numerical checks and extended diagnostics

For issue#4's rigid-wing low-Mach investigation, use the checks below before a
first flow solve. This revises the initial blanket requirement that extended
checkMesh print “Mesh OK.” The change is based on native source and independent
controls, not on relaxing numerical thresholds. Independent review of this
contract and its retained evidence is required before applying it to a flow case.

## Required checks

1. Record the exact case, geometry, runtime, resource limits and command hashes.
2. Run `checkMesh -allTopology -meshQuality` with the **unchanged canonical
   v2412 meshQualityDict** retained in the case. Require completed “Mesh OK.”,
   no failed checks or fatal errors, valid topology, positive geometry and the
   configured numerical-quality limits. Preserve the complete log and dictionary.
3. Separately run `checkMesh -allGeometry -allTopology`. Preserve all findings,
   cell/face sets and statistics. Explain differences from the numerical-quality
   result using the documented metric definitions. An unexplained contradiction,
   nonfinite result or fatal error blocks progression.
4. Require at least90% **wall area**, not face count, with added layers. Report
   achieved layer counts, total thickness and wall spacing separately. A nominal
   request does not establish achieved resolution. Inspect leading-edge,
   trailing-edge, tip and wake cuts and surface coverage maps.
5. A passing mesh gate only permits a checked first flow run. Achieved yPlus,
   force/residual convergence, mass balance, traction/sign normalization and
   repeated results remain required by the rigid-wing contract. Mesh/domain
   sensitivity is required before accepting a polar or comparative design claim.

Canonical numerical limits remain unchanged, including maximum non-orthogonality
65°, skewness4 internally/20 at boundaries, minimum face weight0.05, volume
ratio0.01, tet quality1e-15 and numerical cell determinant0.001. The exact
canonical dictionary is authoritative; these examples are not a substitute for it.

Extended concavity and connectivity-determinant flags remain prominently
reported warnings with cell counts and locations. They are not automatically
reclassified as harmless: actual plane crossings occur in the wing meshes.
They also are not interchangeable with negative volumes, invalid face pyramids,
or failures of the numerical-quality dictionary. The initial investigation is
limited to rigid-wing numerical verification, not deforming-mesh/FSI acceptance.

## Why the two determinant reports differ

Pinned OpenFOAM v2412 source uses two distinct definitions:

- `polyMesh::checkCellDeterminant` delegates to
  `primitiveMeshTools::cellDeterminant`, using internal/coupled faces only. It
  forms a sum of squared face-area vectors normalized by average internal face
  area, and reports determinant magnitude divided by8. Its warning limit is1e-3.
- `polyMeshGeometry::checkCellDeterminant`, used by mesh motion quality checks,
  includes all cell faces and forms area-weighted unit-normal outer products,
  normalizing by total area and by the cube value1/27.

Identical printed threshold numbers do not mean identical quantities. The
27-cell orthogonal anisotropic control already demonstrated that the extended
metric can flag undistorted thin cells. All-boundary single-cell controls have
zero extended determinant and are not used to choose any determinant tolerance.

The original trial3, copied without changing its geometry, passes basic
checkMesh and `checkMesh -allTopology -meshQuality` with the unmodified canonical
dictionary. Its extended check still reports18,892 low-connectivity-determinant
cells and118,066 concavity flags. This resolves the apparent discrepancy in
those reports; it does **not** accept trial3, which still fails area coverage.

## Why concavity needs interpretation

The extended face-centre/plane test flags normalized dot products above -1e-6,
including near-coplanar face arrangements. A convex cube with one flat face split
into triangles triggers this flag, whereas the unsplit cube does not. A separate
non-convex L-prism triggers a positive crossing, demonstrating that the diagnostic
can distinguish these cases. The wing has both near-coplanar and positive-crossing
cells; no claim of general convexity is made.

The face-centre diagnostic is read-only, reproduces the native flagged counts,
and reports distributions rather than introducing a new acceptance threshold.
Further evidence of poor solution behavior or unresolved shape sensitivity must
lead to mesh changes, not removal of failed flow cases from reporting.

## Evidence and provenance

- [Paired mesh cases and geometric controls](evidence/mesh-diagnostics-20261025/README.md).
- [Trial3 numerical-quality log](evidence/mesh-diagnostics-20261025/numerical-quality-trial3/log.topologyQuality).
- [Unchanged canonical dictionary](evidence/mesh-diagnostics-20261025/numerical-quality-trial3/meshQualityDict).
- [Pinned upstream source hashes](evidence/mesh-diagnostics-20261025/numerical-quality-trial3/upstream-source-hashes.json).
- Image/source paths and raw case locations are retained with the experiments.
- [OpenCFD layer documentation](https://doc.openfoam.com/2212/tools/pre-processing/mesh/generation/snappyhexmesh/layers/)
  supplies background; observed v2412 behavior and source govern these findings.

No current case is accepted merely by this contract change. Trial3 and trial5
still fail90% area coverage; trial6 deliberately has no layers. Trial7 is a
separate refinement experiment awaiting completed results.
