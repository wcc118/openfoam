# Native 3D flow viewer

Build a self-contained offline HTML from a validated native-data package:

```sh
python3 scripts/build_flow_3d.py native-flow-3d.json --output native-flow-3d.html
```

The schema and scalar associations are defined in
`scripts/flow_3d/CONTRACT.md`. The builder rejects malformed connectivity,
nonfinite numbers, wrong scalar counts and invalid volume masks. Metadata is
embedded with HTML-sensitive characters escaped and rendered as text.

The default view contains actual connected streamline tubes and Q surface
triangles around a wing. Controls toggle each layer, change surface/volume
opacity, select an overview or right-tip camera, and orbit/pan/zoom. All speed
colors share 0–45 m/s. Tube radius is an illustrative 1.2 mm, not a physical
streamtube boundary or discretization measure. Volume rendering uses the actual
supplied 3D grid, nearest-neighbor display interpolation, and zero opacity for
missing samples (-1). The default opacity transfer suppresses 29–31 m/s to make
departures from the nominal 30 m/s freestream visible; uncheck that option to
color the full valid volume. Opacity is a display choice, not a flow property.

## Renderer reuse

Pinned `vtk.js@35.5.1` supplies geometry and GPU volume rendering. Its UMD bundle
is embedded, so opening the generated HTML needs no network or local server.
WebGL2 is required. Kitware documents its volume renderer at
<https://kitware.github.io/vtk-js/api/Rendering_Core_Volume.html>.
The downloaded npm archive's SHA512 matches the registry integrity value in the
contract. Bundle SHA256:
`ff688c4d7e35a699857ffc6d6b72ca2bf362a1d489f383f7f3a0392656d3e9eb`.
BSD-3-Clause and bundled dependency notices remain in `scripts/flow_3d/vendor`.
This is a third-party dependency license, not a license choice for owner code.

## Native diagnostic export, 2026-10-25

Artifacts and full export/packaging/verification scripts are retained outside Git
under `runs/true-3d-flow-20261025` on the engineering host. The 4° trial30 case uses
6,235,838 cells, Uinf=30 m/s and saved steady iteration 100; x downstream, y span,
z up, all positions in metres. This is not a qualified flow solution.

- `simpleFoam -postProcess -func flowPaths100 -time 100` with native v2412
  streamLine exported 65 paths / 49,240 samples, from volume U. All reach x=1.2 m.
  These are steady streamlines, not physical-time particle trajectories.
- The saved Q*=0.1 cell-valued surface (Q=8718.767437534876 s^-2) has 4,614,608
  triangles. Display-only 1 mm vertex clustering retains 692,454 triangles;
  max vertex displacement 1.217 mm. Collapsed/duplicate triangles are removed;
  retained cells keep a representative original cell speed. This can change
  topology and thin features and must not be used for measurements.
- The regular 10 mm volume grid has dimensions 125×141×33. Native cellPoint U
  sampling yielded 580,415 samples; 1,210 absent coordinates remain transparent.
  This coarse display grid cannot resolve near-wall structure or add solver detail.
- Original U,p,controlDict hashes match before/after both exports. The streamline
  log has no solver iterations. Independent verification checks native coordinates,
  seed identity, speed equality and grid-coordinate mapping. Scalar values and
  cell associations are checked again at the vtk renderer input/output.

The earlier interpolated Q export with anomalous speeds is not used. The
cell-valued source speed maximum is 40.649 m/s. Convergence, wall resolution,
mesh/domain sensitivity and reference checks remain open under issues 4/5.
No resolved turbulent eddies, FSI, flutter or flight capability claim follows.

## Verification

```sh
python3 -m unittest discover -s tests
node tests/browser_flow_3d.cjs PATH_TO_PLAYWRIGHT_CORE PATH_TO_CHROMIUM \
  VIEWER.html INPUT.json ARTIFACT_DIRECTORY
```

The browser check verifies embedded data equality, actual rendered scalar values,
cell/point association, missing-value opacity, nearest volume interpolation,
layer/opacity pixel changes, camera controls, and no network/browser errors.
Use a fixture with at least one -1 masked voxel; native evidence is separate
from synthetic validation. Native screenshots and reports remain with the run.
