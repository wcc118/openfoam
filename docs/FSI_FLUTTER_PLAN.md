# Extended-wing FSI and flutter plan

Owner authorized this plan and execution on 2026-10-27. Objective: a checked,
test-anchored baseline and useful redesign delta, not an exact flight-clearance
speed. Parent issue #24; first shell-interface implementation #34.

## Configuration and scope

First working model: 48 in (1.2192 m) from a rigid root to free tip, provisional
4 in chord and NACA4412 section, continuous hollow 0.050 in (1.27 mm) isotropic
7075-T6 aluminum shell. Two-dimensional CQUAD4 elements have 3D coordinates.
Owner-selected simplification omits real carbon layup, two inner spars and the
outer-over-inner extension joint. The assumed 8 in overlap is metadata only.
Axes: x downstream, y root-to-tip, z up; SI solver units, right-hand rotations.
The shell follows a closed-TE midsurface, not a verified aerodynamic outer surface.

The previous four-foot full-span CFD is the owner's stubby configuration. Never
stretch those pressures onto this extended structure. Its saved steady diagnostic
results do not determine aerodynamic damping. New CFD runs remain ON HOLD.
Lower-order unsteady lifting-surface calculations and structural runs are authorized.
No merge authorization is implied by proceeding with engineering work.

## Verified foundations and limits

- PR31: shell static/modal generator; 79 tests and nine native MYSTRAN19 solves.
  Fine mass .90514 kg, tip bending 1.48327 mm/N, first frequency 8.810675 Hz.
  Higher modes not fully mesh-converged. Fine mesh: 96 rotational AUTOSPCs; disabling
  them changes torsional tip compliance .181%. Ten finite positive modes despite
  documented massless rotational DOFs. Tip-local distortion must not be called GJ.
- PR27: force/moment/virtual-work-conserving small-motion surface transfer,
  including native 181780-face force check. This span-based primitive is not a
  general shell-to-aerodynamic mapper.
- PR29: checked diagonal modal Newmark dynamics and checkpoint restoration.
  Synthetic implicit preCICE flap test completed 200 windows; no wing flutter claim.
- Pinned MYSTRAN19.0.0 and SHARPy2.4 Goland experiment coupled native structural
  matrices to UVLM. Baseline and GJ+10% redesign deltas agreed with SHARPy within
  .00937 percentage points. This is a benchmark beam adapter, not a shell importer.
- Source/reuse inventory: docs/REUSE_INVENTORY.md. Reuse these checked pieces,
  keep explicit frame/DOF normalization maps, pin sources; no mutable sibling imports.

## 1. Establish a trustworthy shell modal interface (issue34)

Extract frequencies and native mass-normalized modes with input/output hashes.
Check root constraints, modal mass/orthogonality and expected global bending,
torsion, in-plane and local-section motions. Compare a refined mesh by mode shape,
not merely sorted frequency; flag ambiguous mode correspondence.

Fit each cross-section's displacement to translation plus physical rotation and
report mass-weighted residual. This diagnoses whether a beam-like aerodynamic
interface discards important skin distortion. An acceptable approximation must
be demonstrated; do not overwrite shell modes with a fitted beam.

Define surface motion u=Hq and generalized force Q=H^T f using the same H.
Verify force/motion virtual work, units, reference geometry and mode scaling.
Record native modal M/K and leave physical damping unknown; any zero-damping
calculation is an explicitly labeled assumption, not measured damping.

Deliverable: mode table, section-distortion metrics, explicit interface contract,
reproducible extraction evidence and tests. Stop before aerodynamic integration
if modal normalization or relevant section kinematics cannot be established.

## 2. Couple to unsteady lifting-surface aerodynamics

Create an aerodynamic surface for the same extended geometry, with explicit
midsurface/outer-surface or camber-surface mapping. Audit pinned SHARPy UVLM input,
force and frame conventions against the tested Goland adapter. Supply native
shell modal dynamics rather than merely replacing a beam's frequencies. Verify
both displacement and velocity coupling, generalized loads and rigid-motion signs.
Use an unloaded small-perturbation reference first, then a defined aerodynamic
operating equilibrium where required. No arbitrary damping or stiffness tuning.

Reproduce a compatible benchmark with the chosen interface and check zero-flow
structural behavior and aerodynamic subsystem stability. Demonstrate that the
coupled solver actually consumes the supplied shell modes/mass/stiffness.
An incompressible attached-flow model is a first-tier approximation: record its
Mach/Re/angle bounds and don't extrapolate through stall or compressibility blindly.

## 3. Locate and verify a surrogate flutter boundary

Sweep airspeed initially coarsely; track eigenvalue real part (growth rate), damping,
frequency and modal character. Track mode identity through close approaches.
Bracket an actual oscillatory sign crossing and refine only that interval. Separate
static divergence from flutter. A stable sampled range is not proof of no flutter.

Check retained structural modes, aerodynamic panel/wake resolution, time step or
state-space/ROM settings, reference angle and assumed damping. Cross-check one
stable and one unstable condition with a time response and a small disturbance.
Deliver damping/frequency-versus-speed plots, mode visualization, numerical bounds,
and a clearly labeled ALUMINUM SURROGATE result. No test-calibrated claim yet.

## 4. Make the baseline representative and compare a redesign

Add actual section/spars, overlap load path, carbon stiffness, distributed mass,
CG/inertia, relevant controls/hinges and root compliance in a prioritized sequence.
Use measured mass, static bending/twist and modal data if available; compare flutter
test speed with IAS/TAS/density/configuration plus oscillation frequency/mode shape.
A speed match alone cannot identify the physical mechanism. Preserve independent
test/configuration evidence where possible and don't tune a separate baseline for
each redesign. Compute paired baseline/redesign speed changes and sensitivity to
uncertain properties. Report a delta as unresolved if its uncertainty overlaps zero.

## 5. Selected transient OpenFOAM FSI (requires lifting CFD hold)

Only after the reduced model is useful, choose a small number of conditions that
answer an aerodynamic-fidelity question. Build the matching extended moving mesh;
use transient flow, conservative loads, displacement/velocity transfer, implicit
preCICE iterations and checkpoint rollback. Check moving-mesh quality, coupling
convergence and time-step sensitivity before interpreting growth/decay.
No full -10..10 degree steady sweep is required for flutter. No automatic CFD
launch follows approval of this plan; the owner's explicit hold remains in force.

## Cost and stopping rules

Spend compute on the modes and aerodynamic phase lag controlling the paired delta.
Use reduced models to bracket speed, then selectively increase fidelity. Initial
numerical target: changes under about 1% in boundary/delta when adding relevant modes
or refining aerodynamics, and well below the redesign improvement being evaluated;
this is a planning target, not a promise of accuracy. Stop refining once numerical
changes are small relative to physical-input uncertainty. Escalate disagreement,
mode changes or failed checks rather than presenting a favorable optimization result.
Record exact solver/input versions, active assumptions, failed runs and decisions.

References: https://precice.org/adapter-openfoam-overview.html ;
https://ic-sharpy.readthedocs.io/en/dev_vortex_rad/content/example_notebooks/linear_goland_flutter.html .
Local benchmark evidence: runs/wing-fsi-goal-20261026/goland-adapter/decision.md;
shell evidence: runs/aluminum-shell-20261027/. Large native artifacts stay outside Git.

2026-10-29: [Loaded equilibrium and thickness comparison](SHELL_LOADED_EQUILIBRIUM.md)
now separates frozen-load structure, untrimmed load-on response, and incremental
UVLM about a solved clamped loaded shape at 30 m/s. Native .060-inch skin variant
reduces loaded tip displacement from 12.59 to 10.48 mm for 20% more mass; first
bending frequency barely changes. This advances the exploratory pipeline, not
flutter qualification. Next vary one numerical setting on this fixed reference.
