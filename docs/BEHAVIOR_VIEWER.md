# Wing behavior viewer

This viewer provides an engineering tool to understand wing behavior across the 60–250 kn speed range using UVLM equilibrium solutions and CFD fixed-pose snapshots.

## Quick start

```bash
python3 scripts/build_behavior_viewer.py \
  --original /path/to/original-stiffness-20261031 \
  --latest /path/to/overnight-20261106 \
  --output runs/behavior-preview
```

Open `runs/behavior-preview/index.html` in a browser.

## Navigation and controls

### Speed selection

- **Speed dropdown**: Select from 20 speeds (60–250 kn in 10-kn steps)
- **Speed slider**: Interactive slider for quick speed changes
- **Current speed display**: Shows Mach number alongside knot value

### Method selection

- **UVLM equilibrium**: Full 20-mode equilibrium solution for the selected speed
- **CFD fixed-pose**: Available CFD snapshots with held geometry and angle of attack

### Deformation scales

- **Deformation scale**: Amplifies structural deformation (modal response) from the UVLM/CFD solution
- **Perturbation scale**: Amplifies transient perturbation (only available at 60/150/250 kn)

### Camera controls

- **Drag**: Orbit the wing
- **Shift-drag**: Pan the view
- **Wheel**: Zoom in/out
- **View dropdown**: Reset (isometric), Top, Side, Tip views

## Display elements

### Wing visualization

- **Blue**: Undeformed geometry (reference shape)
- **Cyan**: UVLM equilibrium deformation (deformation scale applies)
- **Yellow**: CFD held-pose (if selected, deformation scale applies)
- **Purple**: Transient perturbation (if available and perturbation scale > 0)

### Metrics panel

- **Tip deflection**: Mean vertical displacement of tip nodes (inches, relative to undeformed)
- **Tip twist**: Trailing edge rotation relative to undeformed chord (degrees, positive TE-up)
- **Lift**: Wind-axis lift force (lbf)
- **Alpha**: Angle of attack (degrees)

### Trend chart

- **Cyan line**: Tip deflection across all speeds
- **Orange line**: Twist across all speeds
- **Green line**: Lift across all speeds

## Method comparison

### UVLM

- **Source**: Incompressible VLM with aligned fixed straight wake
- **Speeds**: Full sweep 60–250 kn
- **Limitations**: No separation model, no viscous boundary layer

### CFD

- **Source**: OpenFOAM steady solver with fixed-pose assumption
- **Speeds**: Select snapshots only (not full sweep)
- **Limitations**: Numerical sensitivity unresolved; qualification pending

## CFD case diagnostics

Each CFD case displays:

- **Stationarity**: Force history stationary gate status
- **Loaded gate**: Loaded-reference gate status
- **Numerical sensitivity**: Settings sensitivity unresolved
- **Lift error**: Deviation from 30 lbf target
- **Balance correction**: Residual structural balance diagnostic
- **Pose match**: Whether CFD pose matches UVLM equilibrium

## Transient playback

Available only at 60, 150, and 250 kn:

- **Label**: Recorded UVLM small first-bending release about loaded equilibrium
- **Playback**: Original sample sequence, no interpolation
- **Perturbation**: 20-mode UVLM surrogate response
- **Limitations**: Zero assumed structural damping; no CFD motion or physical validation

## Scale interpretation

- **Deformation scale = 1**: True structural displacement (not exaggerated)
- **Deformation scale > 1**: Exaggerated for visibility
- **Perturbation scale = 1**: True transient perturbation

## Known limitations

1. **Clamped linear unprestressed shell**: Not whole-aircraft trim
2. **UVLM**: Incompressible with aligned fixed straight wake; no separation model
3. **CFD**: Fixed-pose results remain diagnostic; long coupled dynamics held pending numerical qualification
4. **No modal-test or wind-tunnel validation linked here**: Agreement is not experimental accuracy
5. **No pressure-field colors**: Surface colors identify methods, not flow features

## Interpretation guidance

- **Cheap UVLM sweep**: Indicates trends and where to inspect
- **Expensive CFD**: Earns value by resolving decision-relevant uncertainty, not by cost alone
- **Disagreement**: Useful evidence—stay visible; don't assume one method is correct
- **Stationarity**: CFD cases with failed stationarity/load-gates remain visible for diagnostic inspection

## Data provenance

See `runs/behavior-preview/provenance.json` for:
- Native SHA256 hash
- Source file hashes
- Scope/limitations applied

## Browser requirements

- Modern browser with Canvas API
- No external dependencies or network access required
- Offline capable after initial load
