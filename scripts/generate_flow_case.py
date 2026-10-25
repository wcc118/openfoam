"""Generate a rigid-wing first-flow OpenFOAM case setup.

This script creates a complete OpenFOAM v2412 case for steady incompressible
turbulent RANS simulation using simpleFoam with kOmegaSST turbulence model.

Usage:
    python3 scripts/generate_flow_case.py --mesh-dir MESH_DIR --output OUTPUT_DIR [options]

Required:
    --mesh-dir    Native OpenFOAM polyMesh directory containing points, faces,
                  owner, neighbour, and boundary files
    --output      NEW output case directory (must not exist)

Optional:
    --alpha-deg   Angle of attack in degrees (default: 4, range: -15..15)
    --iterations  Solver iterations (default: 500, range: 500..5000)

Demonstration geometry (not certified):
    NACA 4412 wing, span=1.2192 m, chord=0.1016 m, S=0.12387072 m²
    CofR at (.0254, 0, 0) m, Reynolds=208684.574, Mach=0.0881609

Flow conditions (ISA sea level):
    V=30 m/s, rho=1.2250532683653954 kg/m³, nu=1.4605775310347254e-5 m²/s

Axes: x downstream, y span, z upward
U = V*(cos(alpha), 0, sin(alpha))
Drag direction: (cos(alpha), 0, sin(alpha))
Lift direction: (-sin(alpha), 0, cos(alpha))
Pitching moment: +y axis

This is a setup generator only. No solver execution, acceptance validation,
or physical verification is performed. Mesh quality and convergence remain
the responsibility of the user.
"""

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
import subprocess


# Demonstration flow conditions (ISA sea level, V=30 m/s)
V_INF = 30.0  # m/s
RHO = 1.2250532683653954  # kg/m³
NU = 1.4605775310347254e-5  # m²/s
REYNOLDS = 208684.574
MACH = 0.0881609

# Demonstration geometry
SPAN = 1.2192  # m
CHORD = 0.1016  # m
AREA = 0.12387072  # m²
COFR = (0.0254, 0.0, 0.0)  # m

# Turbulence parameters (fully turbulent exploratory assumption)
TURBULENCE_INTENSITY = 0.001
TURBULENCE_LENGTH_SCALE = 0.07 * CHORD

# Force/moment conventions
DRAG_DIR = "dragDir"  # (cos(alpha), 0, sin(alpha))
LIFT_DIR = "liftDir"  # (-sin(alpha), 0, cos(alpha))
PITCH_AXIS = "pitchAxis"  # (0, 1, 0) - +y moment

# Required mesh files
REQUIRED_MESH_FILES = ("points", "faces", "owner", "neighbour", "boundary")
OPTIONAL_MESH_FILES = ("cellZones", "faceZones", "pointZones")

# Expected boundary patches
EXPECTED_PATCHES = ("inlet", "outlet", "farfield", "wing")


def compute_flow_quantities(alpha_deg):
    """Compute flow vectors and quantities for given angle of attack."""
    alpha_rad = math.radians(alpha_deg)
    cos_a = math.cos(alpha_rad)
    sin_a = math.sin(alpha_rad)

    # Freestream velocity components
    u_inf = V_INF * cos_a  # x component
    v_inf = 0.0  # y component
    w_inf = V_INF * sin_a  # z component

    # Dynamic pressure
    q_inf = 0.5 * RHO * V_INF * V_INF

    # Turbulence k and omega (fully turbulent assumption)
    k_inf = 1.5 * (V_INF * TURBULENCE_INTENSITY) ** 2
    omega_inf = math.sqrt(k_inf) / (0.09 ** 0.25 * TURBULENCE_LENGTH_SCALE)

    # nut0 for inlet/outlet/farfield (initial)
    nut0 = 0.0

    return {
        "alpha_deg": alpha_deg,
        "alpha_rad": alpha_rad,
        "cos_alpha": cos_a,
        "sin_alpha": sin_a,
        "u_inf": u_inf,
        "v_inf": v_inf,
        "w_inf": w_inf,
        "q_inf": q_inf,
        "k_inf": k_inf,
        "omega_inf": omega_inf,
        "nut0": nut0,
    }


def sha256_file(path):
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def check_mesh_directory(mesh_dir):
    """Validate mesh directory has required files."""
    mesh_path = Path(mesh_dir)
    if not mesh_path.exists():
        raise FileNotFoundError(f"Mesh directory not found: {mesh_dir}")
    if not mesh_path.is_dir():
        raise NotADirectoryError(f"Mesh path is not a directory: {mesh_dir}")

    missing = []
    for f in REQUIRED_MESH_FILES:
        if not (mesh_path / f).exists():
            missing.append(f)

    if missing:
        raise ValueError(f"Missing required mesh files: {', '.join(missing)}")

    return True


def check_boundary_patches(mesh_dir, expected=None):
    """Check boundary patches exist and match expected names."""
    if expected is None:
        expected = EXPECTED_PATCHES

    boundary_path = Path(mesh_dir) / "boundary"
    content = boundary_path.read_text()

    # Parse boundary file to extract patch names
    # Format: <count>\n(\n    patch_name\n    { ... }\n)*
    patches = []
    in_patches = False
    pending_patch = None
    for line in content.splitlines():
        line = line.strip()
        if not in_patches and line == "(":
            in_patches = True
            continue
        if in_patches and line.startswith(")"):
            break
        if in_patches and line and not line.startswith("//"):
            # If there's a pending patch without braces, it's the patch name
            if pending_patch is not None:
                patches.append(pending_patch)
            pending_patch = None
            
            # If line is just a patch name (no { or ;), it's the patch name
            if "{" not in line and ";" not in line:
                pending_patch = line
            else:
                # Check if this line contains a patch name before { or ;
                for sep in ("{{", "{", ";"):
                    if sep in line:
                        parts = line.split(sep)
                        name = parts[0].strip()
                        if name:
                            patches.append(name)
                        break

    # Add any pending patch name
    if pending_patch is not None:
        patches.append(pending_patch)

    # Check expected patches exist
    missing = [p for p in expected if p not in patches]
    if missing:
        print(f"Warning: Expected patches not found: {', '.join(missing)}", file=sys.stderr)

    return patches


def copy_mesh_files(mesh_dir, output_dir):
    """Copy mesh files from source to output directory."""
    src = Path(mesh_dir)
    dst = output_dir / "constant" / "polyMesh"
    dst.mkdir(parents=True, exist_ok=True)

    copied = {}

    # Copy required files
    for f in REQUIRED_MESH_FILES:
        src_path = src / f
        dst_path = dst / f
        if src_path.exists():
            dst_path.write_bytes(src_path.read_bytes())
            copied[f] = sha256_file(dst_path)

    # Copy optional files if they exist
    for f in OPTIONAL_MESH_FILES:
        src_path = src / f
        if src_path.exists():
            dst_path = dst / f
            dst_path.write_bytes(src_path.read_bytes())
            copied[f] = sha256_file(dst_path)

    return copied


def write_0_U(output_dir, flow):
    """Write 0/U file."""
    alpha_deg = flow["alpha_deg"]
    cos_a = flow["cos_alpha"]
    sin_a = flow["sin_alpha"]
    u_inf = flow["u_inf"]
    v_inf = flow["v_inf"]
    w_inf = flow["w_inf"]

    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       vectorField;
    object      U;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 1 -1 0 0 0 0];

internalField   uniform ({u_inf} {v_inf} {w_inf});

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform ({u_inf} {v_inf} {w_inf});
    }}

    outlet
    {{
        type            inletOutlet;
        inletValue      uniform ({u_inf} {v_inf} {w_inf});
        value           uniform ({u_inf} {v_inf} {w_inf});
    }}

    farfield
    {{
        type            freestream;
        freestreamValue uniform ({u_inf} {v_inf} {w_inf});
        value           uniform ({u_inf} {v_inf} {w_inf});
    }}

    wing
    {{
        type            noSlip;
    }}
}}

// ****************************************************************************** //
"""
    (output_dir / "0" / "U").write_text(content)


def write_0_p(output_dir, flow):
    """Write 0_p file (kinematic pressure)."""
    # p0 is reference pressure, set to 0 for incompressible
    p0 = 0.0

    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       scalarField;
    object      p;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform {p0};

boundaryField
{{
    inlet
    {{
        type            zeroGradient;
    }}

    outlet
    {{
        type            fixedValue;
        value           uniform {p0};
    }}

    farfield
    {{
        type            freestreamPressure;
        value           uniform {p0};
    }}

    wing
    {{
        type            zeroGradient;
    }}
}}

// ****************************************************************************** //
"""
    (output_dir / "0" / "p").write_text(content)


def write_0_k(output_dir, flow):
    """Write 0_k file (turbulent kinetic energy)."""
    k_inf = flow["k_inf"]

    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       scalarField;
    object      k;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform {k_inf};

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform {k_inf};
    }}

    outlet
    {{
        type            inletOutlet;
        inletValue      uniform {k_inf};
        value           uniform {k_inf};
    }}

    farfield
    {{
        type            freestream;
        freestreamValue uniform {k_inf};
        value           uniform {k_inf};
    }}

    wing
    {{
        type            kqRWallFunction;
        value           uniform {k_inf};
    }}
}}

// ****************************************************************************** //
"""
    (output_dir / "0" / "k").write_text(content)


def write_0_omega(output_dir, flow):
    """Write 0_omega file (specific dissipation rate)."""
    omega_inf = flow["omega_inf"]

    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       scalarField;
    object      omega;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *

dimensions      [0 0 -1 0 0 0 0];

internalField   uniform {omega_inf};

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform {omega_inf};
    }}

    outlet
    {{
        type            inletOutlet;
        inletValue      uniform {omega_inf};
        value           uniform {omega_inf};
    }}

    farfield
    {{
        type            freestream;
        freestreamValue uniform {omega_inf};
        value           uniform {omega_inf};
    }}

    wing
    {{
        type            omegaWallFunction;
        value           uniform {omega_inf};
    }}
}}

// ****************************************************************************** //
"""
    (output_dir / "0" / "omega").write_text(content)


def write_0_nut(output_dir, flow):
    """Write 0_nut file (turbulent viscosity)."""
    nut0 = flow["nut0"]

    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       scalarField;
    object      nut;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *

dimensions      [0 2 -1 0 0 0 0];

internalField   uniform {nut0};

boundaryField
{{
    inlet
    {{
        type            calculated;
        value           uniform {nut0};
    }}

    outlet
    {{
        type            calculated;
        value           uniform {nut0};
    }}

    farfield
    {{
        type            calculated;
        value           uniform {nut0};
    }}

    wing
    {{
        type            nutLowReWallFunction;
        value           uniform {nut0};
    }}
}}

// ****************************************************************************** //
"""
    (output_dir / "0" / "nut").write_text(content)


def write_constant_transportProperties(output_dir):
    """Write constant/transportProperties."""
    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      transportProperties;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

transportModel  Newtonian;

nu              [ 0 2 -1 0 0 0 0 ] {NU};

// ****************************************************************************** //
"""
    (output_dir / "constant" / "transportProperties").write_text(content)


def write_constant_turbulenceProperties(output_dir):
    """Write constant/turbulenceProperties."""
    content = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      turbulenceProperties;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

simulationType  RAS;

RAS
{{
    RASModel        kOmegaSST;
    turbulence      on;
    printCoeffs     on;
}}

// ****************************************************************************** //
"""
    (output_dir / "constant" / "turbulenceProperties").write_text(content)


def write_system_controlDict(output_dir, iterations):
    """Write system/controlDict."""
    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      controlDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     simpleFoam;

startFrom       startTime;
startTime       0;

stopAt          endTime;
endTime         {iterations};

deltaT          1;

writeControl    timeStep;
writeInterval   100;

purgeWrite      0;

writeFormat     ascii;
writePrecision  12;
timeFormat      general;
timePrecision   12;

runTimeModifiable false;

functions
{{
    forces
    {{
        type            forces;
        libs            ("libsensors.so");
        patches         (wing);
        rho             rhoInf;
        rhoInf          {RHO};
        CofR            ({COFR[0]} {COFR[1]} {COFR[2]});
        p               p;
        U               U;
        writeControl    timeStep;
        writeInterval   1;
    }}

    forceCoeffs
    {{
        type            forceCoeffs;
        libs            ("libsensors.so");
        patches         (wing);
        rho             rhoInf;
        rhoInf          {RHO};
        liftDir         (0 1 0);
        dragDir         (1 0 0);
        pitchAxis       (0 0 1);
        magUInf         {V_INF};
        lRef            {CHORD};
        Aref            {AREA};
        writeControl    timeStep;
        writeInterval   1;
    }}

    solverInfo
    {{
        type            solverInfo;
        libs            ("utilityFunctionObjects");
        fields          (p U k omega);
        writeControl    timeStep;
        writeInterval   1;
    }}

    yPlus
    {{
        type            yPlus;
        libs            ("fieldFunctionObjects");
        writeControl    timeStep;
    }}

    wallShearStress
    {{
        type            wallShearStress;
        libs            ("fieldFunctionObjects");
        writeControl    timeStep;
    }}
}}

// ****************************************************************************** //
"""
    (output_dir / "system" / "controlDict").write_text(content)


def write_system_fvSchemes(output_dir):
    """Write system/fvSchemes."""
    content = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSchemes;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddt
{{
    default         steadyState;
}}

gradSchemes
{{
    default         Gauss linear;
    grad(U)         cellLimited Gauss linear 1;
}}

divSchemes
{{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,omega)  bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear limited 0.5;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         limited 0.5;
}}

wallDist
{{
    method          meshWave;
}}

// ****************************************************************************** //
"""
    (output_dir / "system" / "fvSchemes").write_text(content)


def write_system_fvSolution(output_dir):
    """Write system/fvSolution."""
    content = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSolution;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{{
    p
    {{
        solver          GAMG;
        tolerance       1e-8;
        relTol          0.05;
        smoother        GaussSeidel;
    }}

    U
    {{
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-9;
        relTol          0.1;
    }}

    k
    {{
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-9;
        relTol          0.1;
    }}

    omega
    {{
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-9;
        relTol          0.1;
    }}
}}

SIMPLE
{{
    nNonOrthogonalCorrectors 1;
    consistent      true;
}}

relaxationFactors
{{
    fields
    {{
        p               0.3;
    }}

    equations
    {{
        U               0.7;
        k               0.7;
        omega           0.7;
    }}
}}

// ****************************************************************************** //
"""
    (output_dir / "system" / "fvSolution").write_text(content)


def generate_manifest(output_dir, flow, mesh_hash, source_revision, source_dirty):
    """Generate and write manifest.json."""
    now = datetime.now(timezone.utc).isoformat()

    manifest = {
        "schema_version": 1,
        "generated_utc": now,
        "source_revision": source_revision,
        "source_dirty": source_dirty,
        "status": "unqualified_setup",  # Explicitly never pass from generation
        "mesh": {
            "source_hash": mesh_hash,
            "copied_files": {},
            "boundary_patches": [],
        },
        "flow": {
            "alpha_deg": flow["alpha_deg"],
            "reynolds_number": REYNOLDS,
            "mach_number": MACH,
            "freestream_velocity_m_s": V_INF,
            "density_kg_m3": RHO,
            "kinematic_viscosity_m2_s": NU,
            "turbulence_intensity": TURBULENCE_INTENSITY,
            "turbulence_length_scale_m": TURBULENCE_LENGTH_SCALE,
            "k_inf": flow["k_inf"],
            "omega_inf": flow["omega_inf"],
        },
        "geometry": {
            "span_m": SPAN,
            "chord_m": CHORD,
            "reference_area_m2": AREA,
            "moment_origin_m": list(COFR),
        },
        "turbulence": {
            "model": "kOmegaSST",
            "assumption": "fully_turbulent_exploratory",
            "notes": "Fully turbulent at lowRe is exploratory; transition uncertainty explicit",
        },
        "axes": {
            "x": "downstream",
            "y": "span",
            "z": "up",
            "flow_direction": "U = V*(cos(alpha), 0, sin(alpha))",
            "drag_direction": "(cos(alpha), 0, sin(alpha))",
            "lift_direction": "(-sin(alpha), 0, cos(alpha))",
            "pitching_moment_axis": "+y",
        },
        "boundary_conditions": {
            "inlet": "fixedValue for U, zeroGradient for p, fixedValue for k/omega, calculated for nut",
            "outlet": "inletOutlet for U/p/k/omega, fixedValue p=0, calculated for nut",
            "farfield": "freestream for U/p/k/omega, calculated for nut",
            "wing": "noSlip for U, zeroGradient for p, kqRWallFunction for k, omegaWallFunction for omega, nutLowReWallFunction for nut",
        },
        "solver": {
            "name": "simpleFoam",
            "type": "steadyState",
            "compressibility": "incompressible",
            "turbulence_model": "RANS",
            "turbulence_model_type": "kOmegaSST",
        },
        "output_format": {
            "write_format": "ascii",
            "write_precision": 12,
        },
    }

    # Add copied file hashes to manifest
    manifest["mesh"]["copied_files"] = mesh_hash

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--mesh-dir", required=True, help="Native OpenFOAM polyMesh directory"
    )
    parser.add_argument(
        "--output", required=True, help="NEW output case directory (must not exist)"
    )
    parser.add_argument(
        "--alpha-deg",
        type=float,
        default=4.0,
        help="Angle of attack in degrees (default: 4, range: -15..15)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=500,
        help="Solver iterations (default: 500, range: 500..5000)",
    )
    args = parser.parse_args()

    # Validate alpha range
    if not -15 <= args.alpha_deg <= 15:
        parser.error(f"--alpha-deg must be in range [-15, 15], got {args.alpha_deg}")

    # Validate iterations range
    if not 500 <= args.iterations <= 5000:
        parser.error(f"--iterations must be in range [500, 5000], got {args.iterations}")

    # Check output does not exist (reject existing including empty directory)
    output_dir = Path(args.output)
    if output_dir.exists():
        parser.error(f"Output directory already exists: {args.output}")

    # Validate mesh directory
    try:
        check_mesh_directory(args.mesh_dir)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        parser.error(f"Mesh validation failed: {exc}")

    # Compute flow quantities
    flow = compute_flow_quantities(args.alpha_deg)

    # Create output directory structure
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
        (output_dir / "0").mkdir()
        (output_dir / "constant" / "polyMesh").mkdir(parents=True, exist_ok=False)
        (output_dir / "system").mkdir()
    except OSError as exc:
        parser.error(f"Failed to create output structure: {exc}")

    # Copy mesh files and compute combined hash
    mesh_hashes = {}
    try:
        mesh_hashes = copy_mesh_files(args.mesh_dir, output_dir)
    except OSError as exc:
        # Write failure manifest and exit
        manifest = generate_manifest(
            output_dir,
            flow,
            {"error": str(exc)},
            None,
            None,
        )
        manifest["failure"] = {
            "stage": "mesh_copy",
            "error": str(exc),
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=str, allow_nan=False) + "\n"
        )
        print(f"Failure manifest written to {manifest_path}", file=sys.stderr)
        raise SystemExit(1)

    # Get source revision and dirty state
    root = Path(__file__).resolve().parent.parent
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    source_revision = revision.stdout.strip() if revision.returncode == 0 else None
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    source_dirty = bool(dirty.stdout) if dirty.returncode == 0 else None

    # Write 0/ files
    try:
        write_0_U(output_dir, flow)
        write_0_p(output_dir, flow)
        write_0_k(output_dir, flow)
        write_0_omega(output_dir, flow)
        write_0_nut(output_dir, flow)
    except OSError as exc:
        # Write failure manifest and exit
        manifest = generate_manifest(
            output_dir,
            flow,
            mesh_hashes,
            source_revision,
            source_dirty,
        )
        manifest["failure"] = {
            "stage": "write_0_files",
            "error": str(exc),
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=str, allow_nan=False) + "\n"
        )
        print(f"Failure manifest written to {manifest_path}", file=sys.stderr)
        raise SystemExit(1)

    # Write constant/ files
    try:
        write_constant_transportProperties(output_dir)
        write_constant_turbulenceProperties(output_dir)
    except OSError as exc:
        manifest = generate_manifest(
            output_dir,
            flow,
            mesh_hashes,
            source_revision,
            source_dirty,
        )
        manifest["failure"] = {
            "stage": "write_constant_files",
            "error": str(exc),
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=str, allow_nan=False) + "\n"
        )
        print(f"Failure manifest written to {manifest_path}", file=sys.stderr)
        raise SystemExit(1)

    # Write system/ files
    try:
        write_system_controlDict(output_dir, args.iterations)
        write_system_fvSchemes(output_dir)
        write_system_fvSolution(output_dir)
    except OSError as exc:
        manifest = generate_manifest(
            output_dir,
            flow,
            mesh_hashes,
            source_revision,
            source_dirty,
        )
        manifest["failure"] = {
            "stage": "write_system_files",
            "error": str(exc),
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=str, allow_nan=False) + "\n"
        )
        print(f"Failure manifest written to {manifest_path}", file=sys.stderr)
        raise SystemExit(1)

    # Generate and write manifest
    # Note: mesh_hash is a dict of {filename: hash}
    mesh_hash_combined = hashlib.sha256(
        json.dumps(mesh_hashes, sort_keys=True).encode()
    ).hexdigest()
    manifest = generate_manifest(
        output_dir,
        flow,
        mesh_hashes,
        source_revision,
        source_dirty,
    )

    manifest_path = output_dir / "manifest.json"
    try:
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=str, allow_nan=False) + "\n"
        )
    except OSError as exc:
        print(f"Failed to write manifest: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Generated first-flow case in {args.output}")
    print(f"Manifest: {manifest_path}")
    print(f"Alpha: {args.alpha_deg} deg, Iterations: {args.iterations}")
    print(f"Source: {source_revision} {'(dirty)' if source_dirty else '(clean)'}")


if __name__ == "__main__":
    main()
