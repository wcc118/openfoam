# Wing behavior viewer

The offline viewer connects the original-stiffness 60–250 kn UVLM sweep to all eleven retained CFD diagnostic records. It includes unqualified results with their limitations visible.

```bash
python3 scripts/build_behavior_viewer.py \
  --original /path/to/original-stiffness-20261031 \
  --latest /path/to/overnight-20261106 \
  --output runs/behavior-preview
```

Open `runs/behavior-preview/index.html` directly. This single approximately 27 MB file contains all its data and can be copied to a work PC without OpenFOAM, a server or network access. Raw inputs and generated results remain outside Git. The builder also emits `data.json` and `provenance.json` for audit.

## Reading the viewer

Select any of the twenty speeds. The large wing view overlays gray undeformed geometry, blue UVLM equilibrium and orange **held CFD pose**. Toggle the overlays to inspect them separately. Drag to rotate, shift-drag to pan, scroll to zoom, or use the 3D/span/plan/reset buttons. The long, narrow wing has its actual geometric aspect ratio; magnification changes displacement, not wing dimensions. Colors identify methods, not pressure.

Both displacement scales default to 1×. Static magnification applies to all three components of modal displacement. The metrics always show actual tip deflection in inches, tip chord rotation in degrees (positive trailing edge up), angle and full-wing lift in lbf. Separate trend charts show bending, twist and angle across all speeds. Selecting speed is not an acceleration simulation.

CFD exists only at 60, 150 and 250 kn. The 60 kn cases have different pose and/or angle from the UVLM point, so their lift differences are not a matched-method error. The 150/250 kn cases match pose and angle but fail load balance. The displayed CFD shape is held during the force calculation, not a CFD-predicted equilibrium. Residual balance corrections are diagnostics and are never applied as shape deformation. A stationary force history and a passed historical balance gate do not resolve numerical sensitivity or establish physical accuracy.

Recorded first-bending releases are available only at 60, 150 and 250 kn. Enable the purple overlay, scrub time or play. Playback interpolates recorded modal samples for display, stops at the recorded end and never synthesizes a continuation. Playback rate (physical seconds per wall second) and perturbation magnification are independent. The response chart shows actual tip perturbation in inches versus physical seconds; the CFD force chart uses steady iteration, not time. Neither is an actual-wing experiment.

Runtime details preserve each task's scope: UVLM equilibrium timing is not a complete sweep/dynamics timing, and CFD runs are different workloads. No speedup or accuracy ranking is inferred. Source hashes, axes, normalization, assumptions and every CFD record remain accessible in the evidence section.

## Engineering limits

This is a clamped original-stiffness, symmetric, linear unprestressed shell with zero assumed structural damping and a constant 30 lbf full-wing lift target. UVLM uses an incompressible aligned fixed-wake surrogate, without viscous boundary-layer or separation modeling. The structural surface is sampled for display and is not a CFD volume mesh. CFD numerical sensitivity remains unresolved; CFD stability is unassessed. No modal-test or wind-tunnel correlation is supplied, so physical accuracy is unknown. Agreement is a consistency check, not validation.

## Verification

```bash
python3 -m unittest discover -s tests -p test_behavior_viewer.py
node tests/behavior_browser.mjs runs/behavior-preview runs/behavior-browser-audit
```

Browser verification requires Node with global WebSocket and Google Chrome at `/usr/bin/google-chrome`. It blocks HTTP(S), exercises all speeds/cases, checks rendered modal-coordinate reconstruction and scaled recorded motion against the embedded source arrays, verifies missing-data states, captures desktop/mobile screenshots, and fails on runtime exceptions or external requests. This checks implementation consistency, not physical truth. The separate issue-50 native-NPZ audit checked mirrored normalization, metrics and recorded samples against original inputs.
