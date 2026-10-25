# Physical-time flow playback

`scripts/build_flow_playback.py` creates a single offline HTML file from sampled
transient CFD JSON. It does not solve flow, validate aerodynamics, or manufacture
particle trajectories. Opening the file needs no server or external JavaScript.

```bash
python3 scripts/build_flow_playback.py --input playback-data.json --output flow-time-history.html
```

The output must not already exist. The builder rejects non-finite fields,
inconsistent array lengths, invalid triangles and non-increasing timestamps.
Only `time_kind: physical_seconds` and `run.status: diagnostic_only` are supported.
Steady solver iterations must not be converted to seconds to use this viewer.

Controls provide orbit/zoom, preset views, section filters, speed/Cp coloring,
optional velocity arrows, play/pause, frame steps, scrubbing and replay. Shift-drag
pans the view. Colors use fixed ranges over all frames. Section filters refit the
camera; the source wing may extend outside the viewport when examining a local
section. Arrows use an illustrative length scale, not integrated particle paths.

Normal playback maps the full saved physical interval to ten wall-clock seconds;
frame selection follows the actual, possibly irregular timestamps without field
interpolation. The UI reports the slowdown, physical milliseconds and tU/c.
Replay repeats the saved interval and does not imply periodic flow. Load plots
use physical milliseconds and a cursor at the selected frame; the text identifies
the nearest saved load sample rather than inventing an interpolated coefficient.

## Input contract

JSON schema version 1 contains:

- `schema_version: 1`, `time_kind: "physical_seconds"`.
- `run`: nonempty `id`, `solver`, `source_revision`; `status: "diagnostic_only"`;
  nonempty string array `limitations`; positive `speed_m_s`, `chord_m`, and
  `dynamic_pressure_kinematic`; finite `reference_pressure_kinematic`.
- `wing`: `points` as metre coordinates `[x,y,z]`; `triangles` as three distinct,
  valid integer point indices. This can represent source geometry, not necessarily
  the final mesh surface; identify that distinction in limitations.
- `samples`: fixed `points` in metres and one `groups` entry per point, selected
  from `midspan`, `tip`, `wake`.
- `frames`: at least two entries with increasing nonnegative `time_s`, velocity
  vectors `U` in m/s and kinematic pressure scalars `p` in m²/s², one per sample.
- `loads`: increasing nonnegative `time_s`, dimensionless `CL`, `CD`, `Cm`.
  An empty array is allowed and displayed explicitly as unavailable.

Cp is `(p-reference_pressure_kinematic)/dynamic_pressure_kinematic`; for 30 m/s,
`dynamic_pressure_kinematic` is 450 m²/s². Do not supply pressure in Pa under this
contract. Axes are x downstream, y span, z up; load references/signs belong to the
source case contract. The builder preserves frame values and timestamps. It
escapes embedded JSON and displays metadata as text, not executable markup.

## Evidence limits

An attractive animation does not establish mesh quality, time-step independence,
convergence, turbulence-model validity or flutter. Initial-state adjustment must
be distinguished from developed unsteadiness. Partial runs can be viewed only
with explicit limitations and complete finite exported frames. Preserve the raw
sample files, solver log, case manifest, execution outcome and conversion hashes
alongside the viewer. The JSON itself does not prove source provenance.

Synthetic fixtures in `tests/test_flow_playback.py` test the data contract and
known unit conversions; they are not CFD. Native case setup and OpenFOAM sample
conversion remain separate, primary-owned engineering work.
