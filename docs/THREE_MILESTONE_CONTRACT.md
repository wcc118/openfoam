# Three estimating milestones

Owner authorizes continuing through loaded baseline, useful cyclic response and
bending/torsion airspeed/stiffness comparisons. These are estimating experiments,
not flight clearance. User-facing results use imperial units; canonical quantities
remain SI. The small existing nearest-shell moment defect is accepted and visible.

Primary owns equilibrium, coupling physics, model changes, runtime experiments and
interpretation. Reuse main907675c native preCICE/modal/transfer components, the
unchanged native source NPZ, and inspect pinned PR37 source28d70e8 for UVLM controls.
Do not merge unrelated pending PRs or import mutable sibling checkouts.

Loaded state must satisfy measured aerodynamic generalized loads versus structural
restoring loads within a reported practical residual. Frozen Q/K is an initial
estimate only. Check geometry at that pose and over the intended perturbation
range before interpreting cyclic response. Preserve geometry failures.

Cyclic classification needs several usable same-sign extrema about an explicitly
stated reference, with recorded fitting interval, frequency and growth rate. A
short, failed, guarded or nonoscillatory history is not stable flutter evidence.
Check practical timestep/coupling sensitivity rather than require negligible error.
Separate native live CFD, prescribed-motion, frozen-load and UVLM controls.

Design deltas must include torsional participation and distinguish a hypothetical
generalized-stiffness change from an actual physical structural redesign. Preserve
geometry/load reference and solver assumptions when comparing cases. No optimizer
or side-quest aerodynamic feature is added. Work-machine modal/tunnel correlation
and commercial adapters remain subsequent work.
