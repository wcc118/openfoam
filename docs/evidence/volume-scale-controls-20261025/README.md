# Dimensional face-pyramid volume controls

These independent 27-cell grids test a dimensional quality limit. They do not
validate a wing mesh or its flow. Native ARM64 and AMD64 OpenCFD v2412 give the
same pass/fail results; commands, image pins and raw-report hashes are in
`control-summary.json`. Full ARM64 numerical-quality logs are retained here.
Raw extended logs and native PC logs remain in the referenced run directories.

A rectangular cell with sides 100, 100 and20 micrometres has volume2e-13m³ and
six equal face-pyramid volumes of3.333333e-14m³. A3×3×3 grid of these cells has
aspect ratio5, zero non-orthogonality and roundoff-level skewness. The canonical
SI `minVol=1e-13` rejects all108 faces, even though basic geometry and the separate
extended check pass. This is an absolute dimensional-floor rejection, not an
inverted or non-orthogonal cell.

The canonical dictionary itself describes minVol as an absolute pyramid volume
and advises choosing it for the expected cell scale. Our earlier insistence on
an unchanged SI default was therefore too restrictive at these dimensions; this
is a correction to our acceptance convention, not an OpenFOAM software defect.

The source excerpt shows `polyMeshGeometry::checkFacePyramids` comparing the
signed geometric pyramid volume with `minPyrVol`. Volume changes with the cube
of a uniform length scale. The reference chord is fixed in advance at0.1016m,
from the provisional geometry. The proposed SI floor is therefore
`1e-13 * (0.1016)^3 = 1.048772096e-16 m³`, equivalent to applying the original
floor after dividing every coordinate by that chord.

| Case | Coordinates | minVol | Native result on both hosts |
| --- | --- | --- | --- |
| fine-canonical | SI | 1e-13 | Fail:108 face pyramids |
| fine-chord-floor | Same SI mesh | 1.048772096e-16 | Mesh OK |
| normalized-canonical | Coordinates divided by0.1016 | Original1e-13 | Mesh OK |
| inverted-chord-floor | SI, one interior point moved | 1.048772096e-16 | Fail:6 checks;4 negative-volume cells |

The inverted control moves vertex21 from `(1e-4,1e-4,2e-5)`m to
`(1e-4,1e-4,-1e-4)`m. Its minimum cell volume is-1e-13m³ and four face pyramids
fail even with the scaled positive floor. This verifies that the proposed
convention does not disable rejection of inversion. It does not prove every
possible defect is caught.

All checkMesh processes exit0, including rejected grids. Textual check results
remain authoritative. Initial setup attempts without fvSchemes failed before
checking geometry; they are retained at `runs/pyramid-volume-controls-20261025`
and are not used as evidence for the scale conclusion. The successful earlier
coarse/fine controls remain at `runs/pyramid-volume-controls-v2-20261025`.

The archived Python scripts record the primary experiments, with their original
absolute paths. They are not supported portable tooling. The pristine grid is
reconstructible from blockMeshDict; the inversion script specifies its point
change. Source hashes and the native source excerpt support the dimensional
interpretation. No wing run has yet used this revised convention; previous
failed cases keep their original classifications.
