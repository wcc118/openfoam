# Steady angle-of-attack comparison viewer

`scripts/build_angle_comparison.py` creates a single offline HTML file from independently
simulated steady angle-of-attack cases. It does not solve flow, validate aerodynamics,
or manufacture particle trajectories. Opening the file needs no server or external JavaScript.

```bash
python3 scripts/build_angle_comparison.py --input angle-data.json --output angle-comparison.html
```

The output must not already exist. The builder rejects non-finite fields, duplicate
case IDs or angles, inconsistent array lengths, invalid triangles, invalid derived
speed/Cp, and mismatched freestream velocity vectors. All cases must share the same
mesh_sha256. Only `kind: steady_angle_cases` and `status: diagnostic_only` are supported.

Controls provide orbit/zoom, preset views, section filters, speed/Cp coloring,
optional velocity arrows, and case selection by angle. Shift-drag pans the view.
Colors use fixed ranges computed from all cases. Section filters refit the camera;
the source wing may extend outside the viewport when examining a local section.
Arrows use an illustrative length scale (0.0007× velocity magnitude), not integrated
particle paths. Case switching preserves camera pose.

## Input contract

JSON schema version 1 contains:

- `schema_version: 1`, `kind: "steady_angle_cases"`.
- `reference`: positive `speed_m_s`, `chord_m`, `reference_pressure_kinematic`,
  `dynamic_pressure_kinematic`; finite values in SI units.
- `wing`: `points` as metre coordinates `[x,y,z]`; `triangles` as three distinct,
  valid integer point indices. This can represent source geometry, not necessarily
  the final mesh surface; identify that distinction in case limitations.
- `samples`: fixed `points` in metres and one `groups` entry per point, selected
  from `midspan`, `tip`, `wake`.
- `cases`: nonempty array. Each case has:
  - `id`: unique nonempty string.
  - `alpha_deg`: unique finite number.
  - `steady_iteration`: positive integer (bool rejected).
  - `solver`, `source_revision`: nonempty strings.
  - `mesh_sha256`, `field_sha256`: 64-hex strings; all cases must share `mesh_sha256`.
  - `status: "diagnostic_only"`.
  - `limitations`: nonempty array of nonempty strings describing provenance and bounds.
  - `freestream_velocity_m_s`: length-3 array equal to `speed*(cos(alpha),0,sin(alpha))`
    within 1e-8 absolute; defines the coordinate frame.
  - `U`: array of velocity vectors (m/s), one per sample point.
  - `p`: array of kinematic pressure scalars (m²/s²), one per sample point.

Cp is `(p-reference_pressure_kinematic)/dynamic_pressure_kinematic`. Axes are
x downstream, y span, z up; load references/signs belong to the source case contract.
The builder preserves case values and metadata. It escapes embedded JSON and displays
metadata as text, not executable markup.

## UI display

Each case shows: alpha (degrees), steady iteration count, freestream velocity vector,
and provenance/limitations. The common wing/mesh/body frame is shared across cases.
No play button, animation, fake time frames, angle interpolation, rotated copies of U,
optimizer, solver loop, or simulated pitching trajectory is present or implied.

## Evidence limits

An attractive visualization does not establish mesh quality, iteration independence,
convergence, turbulence-model validity, or flutter. Independent solution convergence
must be demonstrated before trusting steady iteration counts. Initial-state adjustment
must be distinguished from developed steady flow. Partial runs can be viewed only
with explicit limitations and complete finite exported cases. Preserve the raw sample
files, solver logs, case manifests, execution outcomes, and conversion hashes alongside
the viewer. The JSON itself does not prove source provenance.

Synthetic fixtures in `tests/test_angle_comparison.py` test the data contract and
known unit conversions; they are not CFD. Native case setup and OpenFOAM case conversion
remain separate, primary-owned engineering work.

## Limitations for all cases

This viewer is a static comparison tool. It does not:

- Run solvers or perform optimization.
- Estimate convergence, turbulence resolution, or flutter.
- Interpolate between angles or cases.
- Generate particle paths or time-series animations.
- Qualify flight capability or structural loads.

Results are diagnostic only and must not be interpreted as validated performance or
flight clearance without independent engineering review and physical substantiation.
