# Downloadable wing viewers

These viewers are private repository downloads, not a GitHub Pages website.
Sign into GitHub with repository access, download an HTML file, then open it in
Chrome, Edge or Firefox. GitHub's file view displays source, not the interactive viewer.
Each HTML is standalone; no server or supporting data files are required.

## Structural viewer

Open [wing-structure.html](wing-structure.html), then use **Download raw file**.
The 1.6 MB file contains the quadrilateral shell mesh, unit bending and torsion,
and ten animated mode shapes from MYSTRAN. Deformation magnification and arbitrary
modal amplitudes are labeled; colors represent displacement, not stress.

This is the 48-inch rigid-root, 0.050-inch aluminum hollow-shell surrogate with
provisional four-inch chord/NACA4412 geometry, not the actual carbon structure.
Overlap, spars and joint behavior are omitted. Native result provenance and
numerical limitations are embedded. Related implementation: [PR #31](https://github.com/wcc118/openfoam/pull/31).

## CFD viewers

Download individual HTML files from the Assets section of
[Viewer snapshot — October 27, 2026](https://github.com/wcc118/openfoam/releases/tag/viewer-snapshot-2026-10-27):

- `native-flow-minus10-500.html`: −10°
- `native-flow-minus5-500.html`: −5°
- `native-flow-0-500.html`: 0°
- `native-flow-5-500.html`: +5°
- `native-flow-10-500.html`: +10°

Each is approximately 50–82 MB. Download all five into the same directory if you
want their angle-navigation links to work; any individual file works by itself.
They show saved iteration500 results for the earlier stubby isolated-wing CFD
configuration. These are unconverged steady diagnostics, not transient flow,
validated aerodynamics, or flutter results. They do not correspond to the extended
structural geometry. No additional CFD runs were performed for this publication.

The release also contains vtk.js license notices; preserve them when redistributing
the CFD bundle. [manifest.json](manifest.json) records sizes, SHA256 hashes and
provenance; [SHA256SUMS.txt](SHA256SUMS.txt) permits download verification.
