# Computed shell motion preview

Download [wing-coupled-pilot.html](wing-coupled-pilot.html) and open it locally.
It works offline. Choose a scenario, scrub physical time, or press Play.
Playback rate and deformation magnification are independent; the trace reports
actual mean tip displacement. Small-disturbance cases default to 500× geometry;
steady-load cases default to 1×. Colors show displacement, not stress.

Six computed histories compare a coarse and finer ten-mode shell/UVLM pilot at
20 and 60 m/s (small disturbance) and 30 m/s (steady reference-load forcing).
The finer steady-load case stops near 0.046 seconds at an exploratory 20 mm
motion guard. Its short playback is intentional. This guard is not a physical
failure or flight limit.

The model is the 48-inch rigid-root hollow aluminum surrogate with provisional
4-inch chord/NACA4412 and 0.050-inch skin. It has no actual carbon layup, spars,
extension joint, control system or test calibration. Cambered reference geometry
is deliberately untrimmed; structural damping is assumed zero. The motion comes
from linear unsteady lifting-surface coupling, not a new OpenFOAM CFD run.

Numerical evidence and interpretation: [coupled pilot report](../docs/SHELL_COUPLED_PILOT.md).
Embedded data retain source hashes. The native half-wing mesh/modes are replayed
using the same full-span symmetric modal normalization as the computation.
