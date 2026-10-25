# Paired mesh diagnostics and geometric controls

Issue#4 retained rejected experiments. All acceptance gates remain unresolved;
none of these cases has been used for a generated-wing flow solve.

## Paired PC cases

Same pinned amd64 v2412 image, geometry and settings. Trial3 requests18 layers;
trial5 requests12 with the same first-layer20μm and ratio1.25. Trial6 disables
layer addition to inspect the snapped mesh. Exact input hashes and extended
checkMesh logs are retained in each directory. Raw PC case directories are under
`/home/foam/projects/openfoam/runs/` using the directory names here.

| Metric | Trial3:18 layers | Trial5:12 layers | Trial6:no layers |
| --- | ---: | ---: | ---: |
| Cells | 1,143,909 | 1,206,367 | 659,829 |
| Wall-area layer coverage | 83.6734% | 86.7372% | Not applicable |
| Face-count coverage | 78.8497% | 91.7254% | Not applicable |
| Full requested layer-area coverage | 0% | 22.7600% | Not applicable |
| Small-determinant cells | 18,892 | 164,540 | 0 |
| Extended concavity flags | 118,066 | 111,781 | 53,846 |
| Near-coplanar diagnostic class | 59,050 | 52,549 | 1,002 |
| Positive plane-crossing class | 59,016 | 59,232 | 52,844 |

Trial5 still fails90% wall-area coverage; face-count coverage would misleadingly
pass. Package thickness alone is not an adequate fix. Trial6 demonstrates that
many plane crossings exist before layers are added. The higher surface
resolution trial7 timed out at1100s during final checking. Its saved3,023,087-cell
checkpoint separately fails6 topology/numerical-quality checks and10 extended
checks. It remains rejected; raw generation completion was not observed.

PC18-layer control meshing took199.33s vs370.58s for the prior Spark run. Wall
counts and quality failures match; coverage differs by about6.9e-12 and VTK bytes
differ. These single diagnostic timings do not establish production CFD speedup.

## Meaning of the extended concavity flag

The pinned source `primitiveMeshCheck.C`, `checkConcaveCells`, normalizes the
outward face normal and displacement between each pair of face centres, then
flags a cell if any dot product exceeds -1e-6. Its comment explicitly includes
concave **or planar** arrangements. This does not mean all flagged cells are
geometrically non-convex, nor that their numerical suitability is established.

Three small independent controls are retained:

- Unit cube, six faces: no concavity flag; no positive plane crossing.
- Same unit cube, top face split into two coplanar triangles: basic checkMesh
  passes; extended concavity flags one cell. The diagnostic classifies it as
  near-coplanar, with maximum normalized dot product0.
- Deliberately non-convex L-shaped prism of volume3: one concavity flag and one
  positive plane-crossing cell; maximum dot product approximately0.707107.

Single-cell controls also have zero determinant because of their all-boundary
configuration. They establish the concavity distinction only; they are not a
basis for changing determinant tolerances. The earlier27-cell orthogonal
anisotropic control addresses that separate question.

A read-only native diagnostic mirrors the upstream face-centre/plane calculation
and reproduces its flagged-cell counts exactly. It partitions flagged cells into
`-1e-6 < maxDot <= 1e-6` (near-coplanar) and `maxDot > 1e-6` (positive crossing),
and reports additional dot-product bins. These bins are diagnostic, not new
acceptance thresholds. It neither modifies the mesh nor patches the solver.
Source/build artifacts remain in raw `runs/mesh-concavity-diagnostic-20261025` on
Spark and PC; source/binary/upstream-file hashes are in diagnostic-provenance.json.
Native control and PC-case diagnostic logs are retained here. This limited
face-centre test is not a general proof of cell convexity or CFD accuracy.

The latest offline preview compares trials3/5 and shows trial5 sections and
upper/lower layer coverage. PC: `G:\projects\openfoam\runs\wing-baseline-pc-20261025\preview.html`.
The original trial3 preview is preserved as sibling `mesh-preview-trial3.html`.
