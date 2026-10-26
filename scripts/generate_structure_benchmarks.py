"""Generate deterministic SI cantilever benchmark Nastran decks.

BDF deck generator for MYSTRAN 19.0.0 SOL101 (static) and SOL103 (modal) analysis.
Target: three cantilever benchmark cases - static transverse bending, static torsion,
and normal bending modes.

Reference: Euler-Bernoulli beam theory for slender uniform beams.
- Bending deflection: delta = FL³/(3EI)
- Bending rotation: theta = FL²/(2EI)
- Torsion angle: phi = TL/(GJ)
- Mass: m = rho * A * L
- Bending frequencies: f = beta²/(2pi) * sqrt(EI/(rho*A*L⁴))
  beta1=1.875104068711961, beta2=4.694091132974174, beta3=7.854757438237612

Circular beam section: r=0.005m, A=pi*r², I1=I2=pi*r⁴/4, J=pi*r⁴/2
Material: isotropic, E=70e9Pa, nu=0.3, rho=2700kg/m³, G=E/(2(1+nu))
Length: 1.0m, 20 equal elements, 21 nodes.
Beam lies along global x-axis, root at x=0, tip at x=1.
CBAR orientation vector: global y-direction (0,1,0).
SPC1 ID=1, root node (GRID 1) all DOFs fixed: 123456.

Output:
- bend_static.bdf: SOL101, tip load Fz=1N, DISPLACEMENT=ALL, SPCFORCES=ALL
- torsion_static.bdf: SOL101, tip moment Mx=1Nm, DISPLACEMENT=ALL, SPCFORCES=ALL
- modal_bend.bdf: SOL103, six modes via EIGRL METHOD=3, DISPLACEMENT=ALL

JSON reference file with SI values, formulas, and tolerances.
"""

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


# Constants
PI = math.pi
RADIUS = 0.005  # m
LENGTH = 1.0  # m
ELEMENTS = 20
NODES = ELEMENTS + 1

# Material properties
E = 70e9  # Pa
NU = 0.3
RHO = 2700  # kg/m³
G = E / (2 * (1 + NU))  # Pa

# Section properties (circular)
AREA = PI * RADIUS**2  # m²
I1 = I2 = PI * RADIUS**4 / 4  # m⁴ (bending about y and z axes)
J = PI * RADIUS**4 / 2  # m⁴ (torsional)

# Load magnitudes
FORCE_Z = 1.0  # N (transverse)
MOMENT_X = 1.0  # Nm (torsional)

# Analytic reference values
DELTA_STATIC_BEND = FORCE_Z * LENGTH**3 / (3 * E * I1)  # m
THETA_STATIC_BEND = FORCE_Z * LENGTH**2 / (2 * E * I1)  # rad
PHI_STATIC_TORSION = MOMENT_X * LENGTH / (G * J)  # rad
TOTAL_MASS = RHO * AREA * LENGTH  # kg

# Euler-Bernoulli bending frequencies (first three)
BETA1 = 1.875104068711961
BETA2 = 4.694091132974174
BETA3 = 7.854757438237612

FREQ1 = (BETA1**2 / (2 * PI)) * math.sqrt(E * I1 / (RHO * AREA * LENGTH**4))  # Hz
FREQ2 = (BETA2**2 / (2 * PI)) * math.sqrt(E * I1 / (RHO * AREA * LENGTH**4))  # Hz
FREQ3 = (BETA3**2 / (2 * PI)) * math.sqrt(E * I1 / (RHO * AREA * LENGTH**4))  # Hz


def format_decimal(val):
    """Format decimal with at most 1 decimal place, removing trailing zeros after decimal.

    0 -> '0.', 0.0 -> '0.', 0.1 -> '0.1', 1.0 -> '1.', 1.2 -> '1.2'
    """
    formatted = f'{val:.1f}'
    if formatted.endswith('.0'):
        return formatted[:-1]
    return formatted


def generate_grid_cards(num_nodes):
    """Generate GRID cards for nodes along x-axis."""
    cards = []
    for i in range(num_nodes):
        x = i * LENGTH / (num_nodes - 1)
        grid_id = i + 1
        # GRID, id, cid, x, y, z
        # Fixtures use comma-delimited free-field
        # cid blank (field 3 is empty), x has 8 decimal places, y/z use format_decimal
        cards.append(f"GRID,{grid_id},,{x:.8f},{format_decimal(0.)},{format_decimal(0.)}")
    return cards


def generate_cbar_cards(num_elements):
    """Generate CBAR cards for elements."""
    cards = []
    for i in range(num_elements):
        cbar_id = i + 1
        node1 = i + 1
        node2 = i + 2
        # CBAR, eid, pid, g1, g2, x1, x2, x3
        # g1 is first node, g2 is second node
        # orientation vector: global y (0, 1, 0)
        # Comma-delimited free-field format, format_decimal for coordinates
        cards.append(f"CBAR,{cbar_id},1,{node1},{node2},{format_decimal(0.)},{format_decimal(1.)},{format_decimal(0.)}")
    return cards


def generate_pbar_card(area, i1, i2, j):
    """Generate PBAR card with properties."""
    # PBAR, mid, pid, A, I1, I2, J, k, f
    # Comma-delimited free-field format, 10 significant digits for props
    # 8th field is optional (shear factor k), should be 0.
    return f"PBAR,1,1,{area:.9E},{i1:.9E},{i2:.9E},{j:.9E},{format_decimal(0.)}"


def generate_mat1_card(young_modulus, shear_modulus, poisson, density):
    """Generate MAT1 card."""
    # MAT1, mid, E, G, nu, rho, a, tref, ge
    # Comma-delimited free-field format
    # E and G use scientific notation, nu and rho as decimals with trailing dot for integers
    return f"MAT1,1,{young_modulus:.9E},{shear_modulus:.9E},{poisson:g},{format_decimal(density)}"


def generate_spc1_card():
    """Generate SPC1 card for root DOF constraint."""
    # SPC1, sid, dofs, node_ids - comma-delimited format matching fixture
    return "SPC1,1,123456,1"


def generate_force_card(force_z, num_nodes):
    """Generate FORCE card for static bending case."""
    # FORCE, sid, g, cid, f, x1, x2, x3
    # cid blank (empty field) means global coordinates
    # sid=2 (load case ID), node=num_nodes, force in z direction
    # 4th field (cid) is empty, values: f, x1, x2, x3
    return f"FORCE,2,{num_nodes},,{format_decimal(force_z)},{format_decimal(0.)},{format_decimal(0.)},{format_decimal(1.)}"


def generate_moment_card(moment_x, num_nodes):
    """Generate MOMENT card for static torsion case."""
    # MOMENT, sid, g, cid, m, x1, x2, x3
    # cid blank (empty field) means global coordinates
    # sid=2 (load case ID), node=num_nodes, moment about x axis
    # 4th field (cid) is empty, values: m, x1, x2, x3
    return f"MOMENT,2,{num_nodes},,{format_decimal(moment_x)},{format_decimal(1.)},{format_decimal(0.)},{format_decimal(0.)}"


def generate_eigrl_card():
    """Generate EIGRL card for modal analysis."""
    # EIGRL, sid, v1, v2, nd, mode, opt, maxset, shft
    # Minimal format matching fixture
    return "EIGRL,3,,,6"


def generate_deck_bend_static(
    num_elements=ELEMENTS,
    area=AREA,
    i1=I1,
    j=J,
    young_modulus=E,
    shear_modulus=G,
    poisson=NU,
    density=RHO,
    force_z=FORCE_Z,
    num_nodes=NODES
):
    """Generate SOL101 static bending deck."""
    lines = [
        "SOL 101",
        "CEND",
        "TITLE = INDEPENDENT CIRCULAR BEAM",
        "ECHO = NONE",
        "SPC = 1",
        "DISPLACEMENT = ALL",
        "SPCFORCE = ALL",
        "LOAD = 2",
        "BEGIN BULK",
    ]
    lines.extend(generate_grid_cards(num_nodes))
    lines.extend(generate_cbar_cards(num_elements))
    lines.append(generate_pbar_card(area, i1, i1, j))
    lines.append(generate_mat1_card(young_modulus, shear_modulus, poisson, density))
    lines.append(generate_spc1_card())
    lines.append(generate_force_card(force_z, num_nodes))
    lines.append("ENDDATA")
    return "\n".join(lines)


def generate_deck_torsion_static(
    num_elements=ELEMENTS,
    area=AREA,
    i1=I1,
    j=J,
    young_modulus=E,
    shear_modulus=G,
    poisson=NU,
    density=RHO,
    moment_x=MOMENT_X,
    num_nodes=NODES
):
    """Generate SOL101 static torsion deck."""
    lines = [
        "SOL 101",
        "CEND",
        "TITLE = INDEPENDENT CIRCULAR BEAM",
        "ECHO = NONE",
        "SPC = 1",
        "DISPLACEMENT = ALL",
        "SPCFORCE = ALL",
        "LOAD = 2",
        "BEGIN BULK",
    ]
    lines.extend(generate_grid_cards(num_nodes))
    lines.extend(generate_cbar_cards(num_elements))
    lines.append(generate_pbar_card(area, i1, i1, j))
    lines.append(generate_mat1_card(young_modulus, shear_modulus, poisson, density))
    lines.append(generate_spc1_card())
    lines.append(generate_moment_card(moment_x, num_nodes))
    lines.append("ENDDATA")
    return "\n".join(lines)


def generate_deck_modal(
    num_elements=ELEMENTS,
    area=AREA,
    i1=I1,
    j=J,
    young_modulus=E,
    shear_modulus=G,
    poisson=NU,
    density=RHO,
    num_modes=6,
    num_nodes=NODES
):
    """Generate SOL103 modal analysis deck."""
    lines = [
        "SOL 103",
        "CEND",
        "TITLE = INDEPENDENT CIRCULAR BEAM",
        "ECHO = NONE",
        "SPC = 1",
        "DISPLACEMENT = ALL",
        "SPCFORCE = ALL",
        "METHOD = 3",
        "BEGIN BULK",
    ]
    lines.extend(generate_grid_cards(num_nodes))
    lines.extend(generate_cbar_cards(num_elements))
    lines.append(generate_pbar_card(area, i1, i1, j))
    lines.append(generate_mat1_card(young_modulus, shear_modulus, poisson, density))
    lines.append(generate_spc1_card())
    lines.append(generate_eigrl_card())
    lines.append("ENDDATA")
    return "\n".join(lines)


def write_deck(deck_content, filename, output_dir):
    """Write deck to file and return SHA256 hash."""
    filepath = output_dir / filename
    filepath.write_text(deck_content + "\n")
    return hashlib.sha256(deck_content.encode()).hexdigest()


def generate_reference_json(
    output_dir,
    deck_hashes,
    length=LENGTH,
    radius=RADIUS,
    elements=ELEMENTS,
    nodes=NODES,
    young_modulus=E,
    poisson=NU,
    density=RHO,
    force_z=FORCE_Z,
    moment_x=MOMENT_X,
    total_mass=TOTAL_MASS,
    freq1=FREQ1,
    freq2=FREQ2,
    freq3=FREQ3
):
    """Generate JSON reference file with SI values and formulas."""
    ref = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "solver": "MYSTRAN 19.0.0",
        "solver_commit": "3a5913a904ee1adbda9fbcaf9c0a6af8e10f0f9f",
        "solver_url": "https://github.com/MystranSolver/MYSTRANSolver",
        "model": {
            "type": "circular_cantilever_beam",
            "length_m": length,
            "radius_m": radius,
            "elements": elements,
            "nodes": nodes,
            "material": {
                "type": "isotropic",
                "E_Pa": young_modulus,
                "nu": poisson,
                "rho_kg_m3": density,
                "G_Pa": young_modulus / (2 * (1 + poisson)),
            },
            "section": {
                "type": "circular",
                "area_m2": PI * radius**2,
                "I_y_m4": PI * radius**4 / 4,
                "I_z_m4": PI * radius**4 / 4,
                "J_m4": PI * radius**4 / 2,
            },
        },
        "static_bending": {
            "description": "Tip load in global z direction",
            "load_N": force_z,
            "analytic_delta_m": force_z * length**3 / (3 * young_modulus * PI * radius**4 / 4),
            "analytic_rotation_rad": force_z * length**2 / (2 * young_modulus * PI * radius**4 / 4),
            "tolerance_rel": 0.01,
            "tolerance_abs_delta_m": 0,
        },
        "static_torsion": {
            "description": "Tip moment about global x direction",
            "load_Nm": moment_x,
            "analytic_angle_rad": moment_x * length / (young_modulus / (2 * (1 + poisson)) * PI * radius**4 / 2),
            "tolerance_rel": 0.01,
            "tolerance_abs_rad": 0,
        },
        "modal_bending": {
            "description": "First three Euler-Bernoulli bending modes",
            "eigenvalue_method": "EIGRL",
            "eigenvalue_id": 3,
            "modes_requested": 6,
            "euler_beta_values": [BETA1, BETA2, BETA3],
            "analytic_frequencies_hz": [freq1, freq2, freq3],
            "note": "Circular beam has degenerate bending planes; first six solver modes include torsional/axial modes",
            "tolerance_first_bending_rel": 0.02,
        },
        "mass": {
            "total_kg": total_mass,
        },
        "output_files": {
            "bend_static": {
                "filename": "bend_static.bdf",
                "sha256": deck_hashes["bend_static"],
            },
            "torsion_static": {
                "filename": "torsion_static.bdf",
                "sha256": deck_hashes["torsion_static"],
            },
            "modal_bend": {
                "filename": "modal_bend.bdf",
                "sha256": deck_hashes["modal_bend"],
            },
        },
        "assumptions": {
            "beam_theory": "Euler-Bernoulli (slender beam, no shear/rotary inertia)",
            "material": "Isotropic linear elastic",
            "cross_section": "Perfect circular",
            "boundary": "Root node all DOFs fixed (SPC1 123456)",
            "solver_formulations": "MYSTRAN may differ in shear/rotary inertia/mass formulations",
            "verification": "Native execution required for physical validation",
        },
        "tolerances_prospective": {
            "static": 0.01,
            "first_bending_frequency": 0.02,
        },
    }
    filepath = output_dir / "reference.json"
    filepath.write_text(json.dumps(ref, indent=2) + "\n")
    return filepath


def validate_element_count(n):
    """Validate element count is positive integer >= 2."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise ValueError(f"element_count must be integer, got {type(n).__name__}")
    if n < 2:
        raise ValueError(f"element_count must be >= 2, got {n}")
    return True


def validate_nonnegative(name, value):
    """Validate nonnegative finite value."""
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative, got {value}")
    return True


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--output-directory",
        required=True,
        help="Output directory for decks and reference JSON",
    )
    p.add_argument(
        "--element-count",
        type=int,
        default=ELEMENTS,
        help=f"Number of elements (default: {ELEMENTS})",
    )
    p.add_argument(
        "--radius",
        type=float,
        default=RADIUS,
        help=f"Circular section radius in meters (default: {RADIUS})",
    )
    p.add_argument(
        "--length",
        type=float,
        default=LENGTH,
        help=f"Beam length in meters (default: {LENGTH})",
    )
    p.add_argument(
        "--young-modulus",
        type=float,
        default=E,
        help=f"Young's modulus in Pa (default: {E})",
    )
    p.add_argument(
        "--poisson",
        type=float,
        default=NU,
        help=f"Poisson's ratio (default: {NU})",
    )
    p.add_argument(
        "--density",
        type=float,
        default=RHO,
        help=f"Density in kg/m³ (default: {RHO})",
    )

    args = p.parse_args()

    # Validate inputs
    validate_element_count(args.element_count)
    validate_nonnegative("radius", args.radius)
    validate_nonnegative("length", args.length)
    validate_nonnegative("young_modulus", args.young_modulus)
    validate_nonnegative("poisson", args.poisson)
    validate_nonnegative("density", args.density)

    # Validate Poisson ratio bounds
    if args.poisson >= 0.5:
        p.error("Poisson's ratio must be < 0.5 for stability")

    # Create output directory
    output_dir = Path(args.output_directory).resolve()
    if output_dir.exists():
        if any(output_dir.iterdir()):
            p.error(f"Output directory exists and is not empty: {output_dir}")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Recalculate properties with user-provided values
    area = PI * args.radius**2
    i1 = i2 = PI * args.radius**4 / 4
    j = PI * args.radius**4 / 2
    g = args.young_modulus / (2 * (1 + args.poisson))

    num_nodes = args.element_count + 1

    # Generate decks with user parameters
    deck_bend = generate_deck_bend_static(
        args.element_count, area, i1, j,
        args.young_modulus, g, args.poisson, args.density,
        FORCE_Z, num_nodes
    )
    deck_torsion = generate_deck_torsion_static(
        args.element_count, area, i1, j,
        args.young_modulus, g, args.poisson, args.density,
        MOMENT_X, num_nodes
    )
    deck_modal = generate_deck_modal(
        args.element_count, area, i1, j,
        args.young_modulus, g, args.poisson, args.density,
        6, num_nodes
    )

    # Write decks and compute hashes
    hash_bend = write_deck(deck_bend, "bend_static.bdf", output_dir)
    hash_torsion = write_deck(deck_torsion, "torsion_static.bdf", output_dir)
    hash_modal = write_deck(deck_modal, "modal_bend.bdf", output_dir)

    deck_hashes = {
        "bend_static": hash_bend,
        "torsion_static": hash_torsion,
        "modal_bend": hash_modal,
    }

    # Calculate analytic values with user parameters
    total_mass = args.density * area * args.length
    freq1 = (BETA1**2 / (2 * PI)) * math.sqrt(args.young_modulus * i1 / (args.density * area * args.length**4))
    freq2 = (BETA2**2 / (2 * PI)) * math.sqrt(args.young_modulus * i1 / (args.density * area * args.length**4))
    freq3 = (BETA3**2 / (2 * PI)) * math.sqrt(args.young_modulus * i1 / (args.density * area * args.length**4))

    # Generate reference JSON with user parameters
    generate_reference_json(
        output_dir, deck_hashes,
        args.length, args.radius, args.element_count, num_nodes,
        args.young_modulus, args.poisson, args.density,
        FORCE_Z, MOMENT_X, total_mass, freq1, freq2, freq3
    )

    # Print summary
    print(f"Generated {output_dir}")
    print(f"  bend_static.bdf     (SHA256: {hash_bend[:16]}...)")
    print(f"  torsion_static.bdf  (SHA256: {hash_torsion[:16]}...)")
    print(f"  modal_bend.bdf      (SHA256: {hash_modal[:16]}...)")
    print(f"  reference.json      (static bending tolerance: 1%, first bending freq: 2%)")
    print(f"\nModel: {args.element_count} elements, {args.element_count + 1} nodes")
    print(f"       r={args.radius:.6f}m, L={args.length:.6f}m")
    print(f"       E={args.young_modulus:.3e}Pa, nu={args.poisson:.3f}, rho={args.density:.3e}kg/m³")


if __name__ == "__main__":
    main()
