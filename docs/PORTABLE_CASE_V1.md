# Portable case v1 — primary design contract, issue 39

This milestone executes the existing synthetic modal free-decay verification through
portable inputs. It does not port the UVLM matrices, close CFD feedback, import
commercial files, fit real measurements or predict flutter. Native CFD work remains
issue 38. This branch is based on main; the four listed primitive/test files are
verbatim reuse from PR29/PR37, with revisions and SHA256 in the fixture. Their reuse
is not a merge or independent approval of those PRs. No mutable sibling imports.

## Exact supported executable profile

`tests/fixtures/portable_case/free_decay.json` defines the v1 field names and units.
Implement `scripts/portable_case.py` exposing `validate_case(case)` and
`run_case(case)`, plus `python3 -m scripts.portable_case INPUT --output OUTPUT`.
Use ordinary repository package imports of modal_dynamics and modal_surface.
NumPy is the existing integrator dependency; document environment setup, no new
framework/dependency. No solver installation is necessary for this fixture.

All executable quantities use the exact declared SI conventions. Reject unsupported
units/axis systems/normalization instead of silently converting. This version accepts
only dimensionless translation modes, q in m, diagonal modal mass (kg), stiffness
(N/m), damping (kg/s). It does NOT assume unit modal mass or a half/full-wing factor.
H has shape [mode][node][xyz]. u=Hq and Q=H-transpose f use the SAME unscaled H.
Generalized forces have N units for this profile. Node IDs uniquely define ordering;
geometry, structure and aerodynamic node ID arrays must match exactly. Modes have
unique nonempty IDs. All configuration IDs must match. Components are ux,uy,uz;
reference shape is undeformed in the stated right-handed x/y/z frame. This first
profile has collocated nodal point forces, NOT face pressure or a CFD mesh mapper.

Validate dimensions and every numeric value (finite, not bool), nonempty geometry
and mode arrays, unique node IDs, valid nonempty tip IDs, positive modal masses,
nonnegative stiffness/damping, and frequency_hz=sqrt(K/M)/(2*pi) within relative
1e-10 plus absolute 1e-12 Hz. Require all initial state vectors and load arrays to
match mode/node dimensions. Time-history times start at zero, have at least two
samples, and strictly increase; forces are ENDPOINT values, no guessed sampling.
Use each time difference with existing ModalSystem.step. Reject mismatched units,
configuration, shape, normalization, unsupported source/history kinds or nonfinite
values before producing any output file. Required metadata strings are nonempty;
unknown extension/overlap is null (otherwise finite nonnegative metres).

Damping kind is assumed/measured/unknown. Unknown damping has null coefficient and
must be retained as unknown by validation, but execution must fail with a clear
message requiring an explicit value/assumption. Never silently use zero. Known
coefficients must be finite nonnegative. The provided fixture is explicitly assumed.

Aerodynamics source_kind is synthetic_prescribed or solver_export. For solver_export
require positive density/area/reference length, nonnegative airspeed and explicit TAS
convention; synthetic data may leave those fields null. All provided values must
still be validated. Quantity is integrated_point_force, force_unit N, pressure_meaning
not_applicable, time_convention seconds_from_start. Reject pressure/coefficient
inputs in this profile. history_kind may be steady for metadata validation with one
sample at zero, but run_case must reject it for transient/damping inference. No
flutter-classification function exists in this runner. Moment origin is explicit m.

## Experimental metadata, not an identification solver

measurements is a list, empty when no measurements exist. For each supplied record
require unique nonempty id, matching configuration_id, kind modal/steady_aero/dynamic_aero,
environment ground/in_flow, role calibration/validation, data_status metadata_only,
and nonempty channels. Each channel has unique id, position_m xyz, direction xyz
(unit vector within 1e-10), quantity and unit paired from displacement:m,
acceleration:m/s^2, force:N or pressure:Pa. Require excitation {known:bool,
description:nonempty}, sample_axis {kind:time_s or frequency_hz, values:list of
finite nonnegative strictly increasing numbers (empty allowed for unsupplied data)},
phase_convention null or nonempty string, uncertainty {status:unknown or specified,
description:nonempty}, provenance {source:nonempty, sha256:null or 64 hex characters}.
Unknowns are metadata, not filled-in measured values. Do not treat ground modes as
in-flow modes, or steady loads as aerodynamic damping. No actual measurements or
calibration are claimed; raw work data can remain external at the later handoff.

## Output and verification

Output a versioned JSON report with source input SHA256 (for CLI exact bytes),
case/configuration IDs, retained assumptions/provenance, and explicit numerical-only
scope. Include per-sample t, q, v, acceleration, generalized force, physical node
translations and mean tip translation (m). Include endpoint-trapezoidal modal and
physical displacement work and damping loss. Verify virtual work using the actual
endpoint forces and displacement increments; do not claim this is aerodynamic
feedback. Use the existing ModalSystem, displacements and generalized_forces.

The free-decay fixture reproduces the existing m=2, k=18, c=.8, q0=.7, v0=-.4,
T=.73 s analytic test, 320 steps; this is deliberately a synthetic oscillator.
Compare the entire physical tip history with the independently evaluated damped
oscillator solution; maximum displacement error <5e-5 m (inherited test scale;
report observed error and timestep, not a physical-accuracy tolerance). Include a
nonzero prescribed-force test with an independent constant-force analytic solution,
plus nontrivial two-mode virtual-work and mode-rescaling invariance checks.
For diagonal scaling S, H'=HS, q'=S^-1q, M'/C'/K'=S^2 times original and Q'=SQ;
physical motion and work must be invariant (including negative mode scaling).

Required negative checks: wrong units/frame/configuration/node order, malformed or
frequency-only modes, wrong normalization, nonfinite/bool numeric inputs, duplicate
IDs, nonincreasing timestamps, coefficient/pressure loads, invalid metadata, unknown
damping execution, and steady-only execution. Exercise the CLI from a clean copied
checkout outside the development directory; compare results and hashes. No absolute
paths may be required or serialized as dependencies. Preserve existing tests.

At work-machine handoff inspect actual versions/modules and representative exports
before implementing NX Nastran, FlightStream or STAR-CCM+ adapters. Correlate modes
using actual test configuration, support, mass and normalization. Keep calibration
and validation evidence distinct. First deliver this portable numerical fixture;
commercial integration, actual CFD point mapping and measurement fitting follow.
