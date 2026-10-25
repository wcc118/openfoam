# First-Flow Case Setup

This directory contains the `generate_flow_case.py` script for generating a complete OpenFOAM v2412 case setup for rigid-wing first-flow analysis.

## Overview

This script creates a complete OpenFOAM case structure with:

- Mesh files copied from a source polyMesh directory
- Initial field files (0/U, 0/p, 0/k, 0/omega, 0/nut)
- Transport properties (constant/transportProperties)
- Turbulence properties (constant/turbulenceProperties)
- Solver control settings (system/controlDict)
- Numerical schemes (system/fvSchemes)
- Solver settings (system/fvSolution)
- Sensor functions for forces, force coefficients, and wall quantities
- A manifest.json with metadata and hashes

The generated case is ready for `simpleFoam` execution with kOmegaSST turbulence model.

## Usage

```bash
python3 scripts/generate_flow_case.py --mesh-dir MESH_DIR --output OUTPUT_DIR [options]
```

### Required Arguments

- `--mesh-dir`: Native OpenFOAM polyMesh directory containing required mesh files
- `--output`: NEW output case directory (must not exist)

### Optional Arguments

- `--alpha-deg`: Angle of attack in degrees (default: 4, range: -15 to 15)
- `--iterations`: Solver iterations (default: 500, range: 500 to 5000)

## Required Mesh Files

The source mesh directory must contain:

- `points`: Mesh vertex coordinates
- `faces`: Face definitions
- `owner`: Cell owner addressing
- `neighbour`: Cell neighbour addressing
- `boundary`: Boundary patch definitions

Optional files (copied if present):

- `cellZones`: Cell zone definitions
- `faceZones`: Face zone definitions
- `pointZones`: Point zone definitions

## Expected Boundary Patches

The boundary file should contain patches with these names:

- `inlet`: Flow inlet boundary
- `outlet`: Flow outlet boundary
- `farfield`: Far-field boundary
- `wing`: Wing surface (wall)

A warning is printed if expected patches are missing, but generation continues.

## Demonstration Geometry

The script uses these demonstration values (not certified engineering):

- Airfoil: NACA 4412
- Span: 1.2192 m
- Chord: 0.1016 m
- Reference area: 0.12387072 m²
- Moment origin (CofR): (.0254, 0, 0) m
- Reynolds number: 208684.574
- Mach number: 0.0881609

## Flow Conditions (ISA Sea Level)

- Velocity: 30 m/s
- Density: 1.2250532683653954 kg/m³
- Kinematic viscosity: 1.4605775310347254e-5 m²/s
- Turbulence intensity: 0.001
- Turbulence length scale: 0.07 × chord

## Coordinate System

- **x**: downstream (leading to trailing edge)
- **y**: span (left to right)
- **z**: upward

## Angle of Attack Convention

Positive alpha means upward flow direction:

```
U = V × (cos(α), 0, sin(α))
```

- Drag direction: (cos(α), 0, sin(α))
- Lift direction: (-sin(α), 0, cos(α))
- Pitching moment axis: +y

## Boundary Conditions

### 0/U (Velocity)

- **inlet**: `fixedValue` - U = freestream
- **outlet**: `inletOutlet` - inletValue = freestream
- **farfield**: `freestream` - freestreamValue = freestream
- **wing**: `noSlip`

### 0/p (Pressure - Kinematic)

- **inlet**: `zeroGradient`
- **outlet**: `fixedValue` - p = 0
- **farfield**: `freestreamPressure` - value = 0
- **wing**: `zeroGradient`

### 0/k (Turbulent Kinetic Energy)

- **inlet**: `fixedValue` - k = k∞
- **outlet**: `inletOutlet` - inletValue = k∞
- **farfield**: `freestream` - freestreamValue = k∞
- **wing**: `kqRWallFunction`

### 0/omega (Specific Dissipation Rate)

- **inlet**: `fixedValue` - ω = ω∞
- **outlet**: `inletOutlet` - inletValue = ω∞
- **farfield**: `freestream` - freestreamValue = ω∞
- **wing**: `omegaWallFunction`

### 0/nut (Turbulent Viscosity)

- **inlet**: `calculated` - value = 0
- **outlet**: `calculated` - value = 0
- **farfield**: `calculated` - value = 0
- **wing**: `nutLowReWallFunction`

## Example Commands

### Generate a default case (alpha=4°, 500 iterations)

```bash
python3 scripts/generate_flow_case.py \
  --mesh-dir runs/mesh-polyMesh \
  --output runs/case-001
```

### Generate a negative angle of attack case

```bash
python3 scripts/generate_flow_case.py \
  --mesh-dir runs/mesh-polyMesh \
  --output runs/case-alpha-neg4 \
  --alpha-deg -4 \
  --iterations 1000
```

### Generate a high-iteration case

```bash
python3 scripts/generate_flow_case.py \
  --mesh-dir runs/mesh-polyMesh \
  --output runs/case-high-iter \
  --iterations 2000
```

## Post-Generation Steps

After generating the case:

1. **Inspect the manifest.json** for mesh hashes and metadata
2. **Verify mesh files** in `constant/polyMesh/`
3. **Check field files** in `0/` directory
4. **Run checkMesh** on the copied mesh before solving:
   ```bash
   checkMesh -allTopology -allGeometry
   ```
5. **Run the solver**:
   ```bash
   simpleFoam
   ```

## Output Files

The script generates:

```
OUTPUT_DIR/
├── 0/
│   ├── U          # Velocity field
│   ├── p          # Kinematic pressure
│   ├── k          # Turbulent kinetic energy
│   ├── omega      # Specific dissipation rate
│   └── nut        # Turbulent viscosity
├── constant/
│   ├── polyMesh/  # Mesh files (copied from source)
│   ├── transportProperties
│   └── turbulenceProperties
├── system/
│   ├── controlDict
│   ├── fvSchemes
│   └── fvSolution
└── manifest.json  # Metadata and hashes
```

## Manifest Contents

The `manifest.json` includes:

- Schema version and generation timestamp
- Source revision (git HEAD) and dirty state
- **Status: "unqualified_setup"** - explicitly indicates no flow validation
- Mesh source hash and copied file hashes
- Flow parameters (alpha, Re, Ma, V, rho, nu)
- Geometry parameters (span, chord, area, CofR)
- Turbulence model info (kOmegaSST, fully turbulent assumption)
- Coordinate system definition
- Boundary condition specifications
- Solver configuration

## Important Notes

1. **No flow execution**: This script generates setup only. No solver execution is performed.

2. **Mesh quality remains user responsibility**: Passing mesh checks is required before flow, but mesh quality does not guarantee flow convergence or physical validity.

3. **Fully turbulent assumption**: The kOmegaSST setup assumes fully turbulent flow. Transition effects are not modeled. This is an exploratory assumption for low-Re cases.

4. **No auto-acceptance**: The manifest status is explicitly "unqualified_setup". No flow validation or acceptance is performed.

5. **No physical verification**: Force coefficients, residuals, mass balance, and convergence remain the responsibility of the user post-generation.

6. **Reference values**: Force coefficients use:
   - Reference area: S = 0.12387072 m²
   - Reference length: c = 0.1016 m
   - Freestream velocity: V = 30 m/s
   - Density: ρ = 1.2250532683653954 kg/m³

7. **Iterative setup**: Iterations are NOT physical time. Use ≥500 iterations; monitor convergence histories.

## Integration with Other Tools

- **Wing generation**: Use `scripts/generate_wing.py` for surface geometry
- **Mesh evidence**: Use `scripts/summarize_mesh.py` for wall-layer verification
- **Runtime qualification**: Use `scripts/qualify_runtime.py` for runtime checks

## See Also

- [README.md](../README.md): Project overview
- [docs/RIGID_WING_MVP.md](RIGID_WING_MVP.md): Rigid-wing MVP contract
- [docs/WING_GEOMETRY.md](WING_GEOMETRY.md): Geometry documentation
- [docs/ENGINEERING_PLAN.md](ENGINEERING_PLAN.md): Engineering roadmap
- [docs/MESH_ACCEPTANCE.md](MESH_ACCEPTANCE.md): Mesh acceptance criteria

## Tests

Run the test suite:

```bash
python3 -m unittest discover -s tests -v
```

Tests cover:
- Command-line argument validation
- Mesh directory validation
- File copying with hash verification
- OpenFOAM dictionary generation
- Manifest generation
- Boundary patch checking
- Flow quantity computation
- Error handling and failure manifests

## License

This is an engineering analysis tool. See repository LICENSE for terms.
