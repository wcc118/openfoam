# Dense 3D flow inspection

Build a self-contained HTML file from exported steady cases:

```sh
python3 scripts/build_dense_flow_viewer.py --input dense-slices.json --output dense-viewer.html
```

The output must not exist. The original angle viewer is unchanged. There are no
browser libraries, network requests or server requirements. This is a diagnostic
viewer, not a solver or an aerodynamic qualification step.

Use the angle selector to compare actual solved fields. Slice selection and the
position slider select only available exported planes. Drag to orbit, Shift-drag
to pan, and scroll to zoom. Focus slice shows a close-up; Fit wing provides context.
Face selected slice shows an orthographic section. Wing opacity can be reduced to
zero. Arrows are a display overlay through the wing, explicitly labeled as such.

Color choices are total speed, Cp, and induced crossflow magnitude. Induced vectors
are `(0, Uy - Uinf_y, Uz - Uinf_z)`; axial velocity is omitted. They are not total
velocity. Total arrows use 0.0007 m per m/s and crossflow arrows 0.003 m per m/s.
These fixed illustrative scales are not particle trajectories. Scalar ranges are
fixed over all samples and cases. Angle changes preserve camera and selected slice.
Arrow density controls only arrows; every valid scalar cell remains drawn.

The input retains the complete `steady_angle_cases` schema documented in
[ANGLE_COMPARISON.md](ANGLE_COMPARISON.md), including finite fields, shared mesh,
freestream convention, provenance, and diagnostic-only status. The builder reuses
that validator and requires a `slices` array. Each slice has:

- Unique nonblank `id` and nonblank `label`.
- `normal_axis`, `u_axis`, `v_axis`: a permutation of integer 0,1,2.
- Finite `position_m`: coordinate on the normal axis.
- `u_values`, `v_values`: finite strictly increasing coordinate arrays, length >=2.
- `indices`: row-major (v then u) sample indices, length len(u)*len(v).
  Each entry is -1 (masked) or a unique valid index within that slice.

Coordinates of every referenced sample must match the declared plane and grid
within 1e-8 m. Grid quads are drawn only when all four corners are valid; scalar
color is the average of those four sample values. This display interpolation does
not establish solver resolution. Missing cells remain masked. Angle or slice
interpolation is not performed. All text metadata is rendered as text.

The initial native delivery contains y=0 midspan at 1 mm spacing and right-tip wake
planes x=0.15,0.30,0.50 m at 2 mm spacing, for independent 0/4 degree steady
iteration100 fields. These are unconverged diagnostics at30m/s. No physical-time
animation, resolved turbulent eddies, flutter speed or flight clearance is implied.

Verification: Python tests cover slice and inherited data contracts, masks, axes,
analytical crossflow ranges, injection-safe embedding and no-overwrite behavior.
The browser test accepts existing Playwright/Chromium paths as positional arguments:

```sh
node tests/browser_dense_flow.cjs PATH_TO_PLAYWRIGHT_CORE PATH_TO_CHROMIUM
```

Optional third/fourth arguments supply a native HTML file and artifact directory
(containing dense-slices.json). That checks embedded native data equality and saves
screenshots/evidence. Browser checks exercise every main control, fixed camera on
angle roundtrip, scalar-fill invariance under arrow density and idempotent focus.
