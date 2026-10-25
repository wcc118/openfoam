# Rejected wing mesh experiments, 2026-10-25

These retained inputs and mesh-check logs document failed experiments for issue
#4. They are not production cases and must not feed a flow/optimization loop.
No generated-wing flow solve was performed.

Both use the generated closed NACA4412 full-span1.2192m/chord0.1016m baseline,
the pinned ARM64 OpenFOAM v2412 image, and sequential blockMesh,
surfaceFeatureExtract, snappyHexMesh -overwrite, checkMesh -allGeometry
-allTopology, then postProcess slices. Exact dictionaries are retained below;
STL and native wall-VTK hashes identify omitted larger artifacts. Raw files are
in the project `runs/mesh-trial3-20261025` and `runs/mesh-trial4-20261025`.

| Evidence | Trial 3 | Trial 4 |
| --- | ---: | ---: |
| Layer-area coverage | 83.6734% | 81.5348% |
| Face-count coverage | 78.8497% | 70.0615% |
| Area-weighted layer count | 6.2647 | 5.7150 |
| Area with all 18 requested layers | 0% | 0.3539% |
| Failed extended mesh checks | 2 | 10 |
| Outcome | Rejected | Rejected |

Trial3's default shrinker produced small-determinant and concave-cell failures.
Trial4 substituted displacementLaplacian mesh shrinking and produced additional
negative-volume/orientation/skewness failures. Both finished with process exit0;
checkMesh text and independent achieved-layer metrics establish rejection.
Neither reaches the predeclared90% area-with-layers gate. Area with any layers is
not adequate thickness, yPlus, convergence, or physical validation.

An independent orthogonal anisotropic27-cell control also failed the default
extended determinant check despite positive, flat, orthogonal geometry. Thus
this check needs informed interpretation for boundary-layer anisotropy; no
threshold has been relaxed, and this does not waive the wing trials' other
failures. Further engineering should examine layer termination, trailing-edge
and tip topology, and alternative meshing layouts before another parameter sweep.

The historical plot script is retained for provenance, not installed as a general
utility. It uses NumPy/Matplotlib and fixed local raw paths. Its upper/lower labels
were corrected after checking centroids: CFD wall normals point into the solid;
negative-z normals identify the upper wing here. Native VTK evidence readers,
not image colors, determine quantitative gates.

The owner-facing standalone HTML embeds cross-sections and surface coverage,
with rejection labels and source hashes. PC location:
`G:\projects\openfoam\runs\wing-baseline-pc-20261025\mesh-preview.html`.
Original wing geometry preview links/embeds it and preserves a geometry-only copy.

Later visualization should show physical-time3D flow playback with synchronized
forces/moments, then deformation and disturbance decay/growth. This requires
accepted mesh/steady evidence and time-step sensitivity first. Solver iteration
playback is not physical time; no current artifact predicts flutter.
