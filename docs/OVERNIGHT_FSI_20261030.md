# Overnight FSI continuation — 2026-10-30

## What is ready to preview

On the PC, open `G:\projects\openfoam\viewers\wing-instability-comparison.html`.
It compares actual decaying motion at20m/s with growing motion at25m/s in the
explicitly hypothetical soft-torsion wing. Play slowly or scrub toward2seconds.
The M12/N24 model used by this preview remains identified in its source and report.
`goland-instability-comparison.html` gives the independently checked benchmark
comparison at150/175m/s. Both share physical scales between their panels.
`instability-comparison.png` summarizes the time histories and numerical sensitivity.
The earlier equilibrium and airspeed comparison viewers remain available.
`extended-wing-fine-mesh-slices.png` and`extended-wing-fine-layer-coverage.png`
show the new matching extended CFD mesh and its achieved layer distribution.

This answers the request to see instability: the increasing bending and twist are
computed coupled modal–UVLM histories. They are not animations synthesized from
an assumed growing envelope. They do not establish flutter of the original
aluminum wing or of the actual carbon/spar/joint configuration.

## Numerical result

The diagnostic reduces only the fifth generalized modal stiffness to1% while
retaining native mass and mode shapes. First bending stays8.810675Hz; torsion
moves from169.4779 to16.94779Hz. Its aerodynamic reference is flat and unloaded.
Physical structural damping is explicitly assumed zero.

The oscillatory crossing moves from22.56636m/s on M8/N16 to23.10665 on M12/N24
and23.34976 on M16/N32, all with20modes and matched physical timesteps. The last
change is1.05%; aerodynamic-grid convergence is still unresolved. The actual
stable20/growing25m/s behavior survives all completed checks. The final M16 run
also agrees between independently stepped predictor-descriptor and causal
formulations to6.34e-13 in the growing response. The earlier M16 resource
interruption remains recorded as a failure, separate from the successful retry.

See [the detailed instability report](INSTABILITY_DEMONSTRATION.md) for growth,
frequency, modal tracking, wake/time/mode sensitivity, physical displacement and
energy/work checks.203 repository tests and32 new browser combinations passed;
96 earlier speed-viewer combinations also passed. These are numerical and
software checks, not experimental validation.

## Matching extended-wing CFD

The new CFD geometry has2.4384m full span and0.1016m chord, matching the extended
structural configuration. It is a closed-TE NACA4412 provisional shell midsurface,
not a verified outer skin. Native surface checks found a closed, connected surface
without self-intersections. The original four-foot full-span flow field was not
stretched onto this wing. The prescribed motion mirrors the original first
bending mode across the rigid center/root; no finite fuselage or antisymmetric
structural motion is represented. This CFD case uses the cambered geometry and
unmodified native bending mode, not the flat soft-torsion instability model.

The coarse mesh passes the configured numerical quality checks but covers only
70.6943% of wall area with layers, below the90% requirement. Only8.97% of area
has the requested12layers. This failure remains visible; all coarse-mesh fluid
results are pipeline diagnostics. The fine mesh finished meshing in2829seconds, but the subsequent checkMesh
process was killed by global out-of-memory pressure. The kernel log identifies
checkMesh; the WSL VM has32GiB despite the PC having64GiB physical RAM. Its
completed11,472,632-cell mesh was checked after other workloads released memory.
Canonical and chord-scaled numerical quality checks both pass. Layers cover
98.8237% of wall area, exceeding the90% gate;69.3481% has all12requested layers
and area-weighted layer count is10.0667. The extended geometry check still flags
851982 low-connectivity-determinant cells and470779 concave cells (two failed
extended checks), plus9825 concave faces. Those diagnostics are retained and
must not be silently equated with the passing canonical meshQuality checks.
No flow/yPlus or moving-mesh qualification has yet been run on this fine mesh.

A native OpenFOAM utility exports the wing patch's actual point ordering. Mapping
uses native shell translations, piecewise interpolation over span/perimeter and
triangle interpolation over the closed tip caps. The original perimeter-only map
failed on cap-interior points; that failure led to the cap correction. Native-node
identity error is2.71e-20m and all167665 CFD wing points are mapped. The maximum
surface projection distance is147.64micrometres; root displacement is about1e-15m.

The prescribed mesh-motion test imposes0.1mm mean tip bending at8.810675Hz. Saved
positive peak, zero crossing, negative peak and final return match prescribed
wing positions within5.02e-14m. This verifies boundary ordering, signs and motion.
It does not establish the interior mesh's fitness for fluid dynamics: the initial
mesh extension passed the positive peak but failed strict quality checks at the
remaining phases. Interior displacement persisted at zero wing displacement,
reaching0.215mm at the final return. The solver/checkMesh command exited0 despite
three reported failed quality checks. Those checks are failures, not successful
acceptance. A separate extension experiment uses a dedicated uncorrected mesh-displacement
Laplacian without changing fluid schemes or quality thresholds. It passes all
five strict checks (initial state plus four phases), with the same boundary
position accuracy. Final interior offset decreases to6.89micrometres but is not
zero. The three-cycle extension passes all13 sampled quality checks and
preserves wing positions to5.02e-14m. Maximum interior offsets at the successive
full-cycle returns are6.89,7.29,7.63micrometres. This is an improvement in mesh
robustness, not proof of exact reversible mesh extension or long-run convergence.

The rigid-flow diagnostic uses30m/s, zero incidence, rho1.225053268kg/m3,
nu1.4605775e-5m2/s and fully turbulent k–omega SST. Its SIMPLE history uses
iteration count, not physical seconds. The primary stopped this unqualified
diagnostic after its saved iteration300 checkpoint to prioritize moving-flow
plumbing and fine-mesh checks; the original500-iteration target was not completed.
The native exit137 and explicit stop decision are retained. A separate moving-mesh pimpleFoam pilot
starts from iteration100, explicitly without claiming converged initialization.
It uses five requested1microsecond physical steps,0.1mm prescribed bending and
the same density/area/moment origin. It is a plumbing/throughput experiment,
not an oscillation-length damping estimate and not two-way structural feedback.
The serial pilot completed only the first1microsecond step (about652seconds
including initialization) before timing out during its second step at905.8seconds.
It did not complete the requested five-step run. A separate parallel pilot uses
the improved mesh extension and preserves the checkpoint face flux. Native
pointProcAddressing checks show exact agreement of all167665 unique wing points
and mode values between serial and four-process decomposition, including shared
points. That check is distinct from parallel fluid convergence. The parallel
pilot completed four1microsecond steps (893seconds elapsed at the fourth) before
timing out during the fifth at905.8seconds. Neither layered-mesh pilot completed
its requested five steps. Both use sine motion with nonzero initial prescribed
velocity, so startup force transients are not periodic aerodynamic work or damping.

A deliberately coarse no-layer alternative has172130cells and uses the same
extended surface. Its first attempt failed on two highly skewed boundary faces;
tighter generation targets (boundary skew4, internal skew3, nonorthogonality60)
produced a mesh passing the unchanged acceptance checks. The no-layer flow run
completed500iterations in310seconds. It is only a cheap plumbing experiment;
no-layer viscous forces must not be promoted to aerodynamic validation. Its
native-mode projection failed the unchanged1mm surface-distance guard. Refining
the surface produced362208cells and again passed numerical quality, but the
nearest closed-surface mapping still reached1.02726mm and remained failed.
The corresponding500-iteration steady initialization completed in247seconds.
A separately labeled analytic parabolic wall-motion control isolates the fluid
plumbing from that failed native structural map; it does not establish native
modal CFD coupling.

The analytic control completed20steps to0.002s atdt=0.0001s in48seconds,
then another20steps to0.004s with a native wall-force/work observer in53seconds.
Both final moved meshes pass the strict quality check. Saved wing displacement
at0.002s agrees with the prescribed analytic motion within4.98e-14m. The observer
uses OpenFOAM's actual per-face pressure-plus-viscous force field dotted with its
actual movingWallVelocity boundary U and globally reduces across MPI ranks.
Its summed force agrees with native force.dat within4.96e-12N across20samples.
Positive work over that short upward-moving segment is expected even for a
constant lift load; it is not evidence of negative damping. A bounded continuation
to0.12s is gathering one complete observed prescribed-motion cycle. Its outcome
will be appended after the native command terminates.

## Review and reproducibility

Work is on PR37, deliberately stacked on the aluminum-shell branch, not merged.
The independent reviewer did not produce an accepted verdict: earlier runs hit
harness protocol checks and the latest run repeated a query until cancelled.
Run20261030T044521Z-918253 exited143; logs/checkpoint were retained and its outcome
acknowledged. Independent review remains outstanding despite the passing tests.

[Frozen experiment sources](evidence/extended-cfd-sources-20261030/README.md)
retain the actual input drivers, native point-order utility and independent checks;
[component evidence](evidence/extended-cfd-components-20261030.json) records the
reported outcomes. Large native artifacts, logs and failures are retained under
`runs/instability-20261030/` on the Spark and matching timestamped run directories
under`/home/foam/projects/openfoam/runs/` in the PC OpenFOAM WSL distribution.
PC previews were transferred and their SHA256 hashes checked against source.
Pinned runtime/image and source details accompany each experiment and the detailed
instability report. The checked-in evidence contains reports rather than raw
multi-million-cell meshes or large histories.

## Next engineering decision

Keep the verified UVLM path for instability exploration. First make the full-wing
CFD mesh-motion and force-transfer components reliable, then run prescribed
harmonic flow long enough to measure force phase and aerodynamic work. Compare
with UVLM using matching geometry, reference state, amplitude and frequency.
Only then close the structural feedback through the existing implicit preCICE
participant and check timestep/coupling convergence. A working synthetic preCICE
flap test does not establish this wing's complete load/motion mapping.

In parallel, bring torsion into a physically realizable structural model using
section/spar/joint stiffness and mass information. The artificial generalized-
stiffness example is useful for seeing the mechanism; it must remain separate
from a design prediction. No speed from this report is a flight limit.
