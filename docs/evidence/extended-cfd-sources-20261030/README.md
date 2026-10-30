# Frozen extended-wing CFD experiments, 2026-10-30

These are the exact primary-owned experiment drivers and checkers retained with
[the overnight report](../../OVERNIGHT_FSI_20261030.md). They describe the observed
Spark/Windows-WSL environment and dated artifact directories; they are not a
portable command-line interface or an automated design loop. Several scripts
intentionally target existing checkpoints and must not be blindly rerun.

The manifest records source hashes, runtime pins and the native modal input hash.
The repository supplies the pinned wing/shell geometry and rigid-flow generators;
large native inputs, meshes, fields and logs remain in the reported run directories.
Earlier failures and later controls are distinct experiments. Native checkMesh
exit0 is not sufficient: inspect failed-check text and the applicable mesh gate.
The analytic control is prescribed parabolic wall motion, not native structural FSI.

The cycle comparison can be repeated on exported text evidence without running a
solver:

```sh
python3 analyze_cycle_comparison.py COARSE_EVIDENCE_DIR HALFSTEP_EVIDENCE_DIR NEW_OUTPUT_DIR
```

It checks native force agreement, finite uniformly spaced samples and restart
overlap, then integrates actual wall power. The output retains incomplete cycles,
failed sampled mesh checks and startup extrema; it never classifies CFD flutter.
The plot labels the analytic/no-layer/no-feedback scope and failed mesh quality.
`complete_analytic_cycle_pc.py` is a one-use checkpoint continuation driver for the
recorded cases, not a general scheduler. It preserves the original timeout,
checks the saved states and returns failure if sampled mesh quality fails, even
when native OpenFOAM commands return zero.
