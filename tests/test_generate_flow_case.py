"""Tests for generate_flow_case.py first-flow case setup generator.

Tests cover:
- Command-line argument validation (mesh-dir, output, alpha-deg, iterations)
- Required mesh file validation
- Output directory rejection (existing, including empty)
- Mesh file copying with hash verification
- OpenFOAM dictionary generation correctness
- Manifest generation with source metadata
- Boundary patch checking
- Flow quantity computation
- Error handling with failure manifest
"""

import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path
from scripts.generate_flow_case import (
    check_boundary_patches,
    check_mesh_directory,
    compute_flow_quantities,
    copy_mesh_files,
    generate_manifest,
    main,
    sha256_file,
    EXPECTED_PATCHES,
    REQUIRED_MESH_FILES,
    V_INF,
    RHO,
    NU,
    REYNOLDS,
    MACH,
    SPAN,
    CHORD,
    AREA,
    COFR,
    TURBULENCE_INTENSITY,
    TURBULENCE_LENGTH_SCALE,
)


class FlowQuantityTests(unittest.TestCase):
    """Test flow quantity computations."""

    def test_zero_alpha_flow(self):
        """Alpha=0: U=(V,0,0), drag=(1,0,0), lift=(0,0,1)."""
        flow = compute_flow_quantities(0.0)
        self.assertAlmostEqual(flow["alpha_rad"], 0.0)
        self.assertAlmostEqual(flow["cos_alpha"], 1.0)
        self.assertAlmostEqual(flow["sin_alpha"], 0.0)
        self.assertAlmostEqual(flow["u_inf"], V_INF)
        self.assertAlmostEqual(flow["v_inf"], 0.0)
        self.assertAlmostEqual(flow["w_inf"], 0.0)
        self.assertAlmostEqual(flow["q_inf"], 0.5 * RHO * V_INF * V_INF)

        # Turbulence k and omega
        expected_k = 1.5 * (V_INF * TURBULENCE_INTENSITY) ** 2
        self.assertAlmostEqual(flow["k_inf"], expected_k)
        expected_omega = math.sqrt(expected_k) / (
            0.09 ** 0.25 * TURBULENCE_LENGTH_SCALE
        )
        self.assertAlmostEqual(flow["omega_inf"], expected_omega)

    def test_positive_alpha_flow(self):
        """Alpha=4 deg: U has z component upward."""
        flow = compute_flow_quantities(4.0)
        self.assertAlmostEqual(flow["cos_alpha"], math.cos(math.radians(4)))
        self.assertAlmostEqual(flow["sin_alpha"], math.sin(math.radians(4)))
        self.assertAlmostEqual(flow["u_inf"], V_INF * math.cos(math.radians(4)))
        self.assertAlmostEqual(flow["w_inf"], V_INF * math.sin(math.radians(4)))

    def test_negative_alpha_flow(self):
        """Alpha=-4 deg: U has z component downward."""
        flow = compute_flow_quantities(-4.0)
        self.assertAlmostEqual(flow["sin_alpha"], math.sin(math.radians(-4)))
        self.assertLess(flow["w_inf"], 0.0)


class MeshDirectoryValidationTests(unittest.TestCase):
    """Test mesh directory validation."""

    def test_missing_directory(self):
        """Non-existent mesh directory raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = Path(tmpdir) / "nonexistent"
            with self.assertRaises(FileNotFoundError):
                check_mesh_directory(bad_path)

    def test_not_a_directory(self):
        """File path instead of directory raises NotADirectoryError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "file"
            f.write_text("test")
            with self.assertRaises(NotADirectoryError):
                check_mesh_directory(f)

    def test_missing_required_file(self):
        """Missing required mesh file raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()
            # Create only some files
            (mesh_dir / "points").write_text("test")
            (mesh_dir / "faces").write_text("test")
            (mesh_dir / "owner").write_text("test")
            # neighbour missing

            with self.assertRaises(ValueError) as cm:
                check_mesh_directory(mesh_dir)
            self.assertIn("neighbour", str(cm.exception))

    def test_all_required_files_present(self):
        """All required files present returns True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()
            for f in REQUIRED_MESH_FILES:
                (mesh_dir / f).write_text("test")

            result = check_mesh_directory(mesh_dir)
            self.assertTrue(result)


class MeshFileCopyingTests(unittest.TestCase):
    """Test mesh file copying functionality."""

    def test_copy_required_files(self):
        """Copy all required mesh files with hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()
            for f in REQUIRED_MESH_FILES:
                (mesh_dir / f).write_text(f"content of {f}")

            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()

            hashes = copy_mesh_files(mesh_dir, output_dir)

            self.assertEqual(len(hashes), len(REQUIRED_MESH_FILES))
            for f in REQUIRED_MESH_FILES:
                self.assertIn(f, hashes)
                expected_hash = sha256_file(mesh_dir / f)
                self.assertEqual(hashes[f], expected_hash)

    def test_copy_optional_files(self):
        """Copy optional files if they exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()
            for f in REQUIRED_MESH_FILES:
                (mesh_dir / f).write_text(f"content of {f}")
            # Add optional files
            (mesh_dir / "cellZones").write_text("cellZones")
            (mesh_dir / "faceZones").write_text("faceZones")
            (mesh_dir / "pointZones").write_text("pointZones")

            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()

            hashes = copy_mesh_files(mesh_dir, output_dir)

            for f in REQUIRED_MESH_FILES + ("cellZones", "faceZones", "pointZones"):
                self.assertIn(f, hashes)


class ManifestGenerationTests(unittest.TestCase):
    """Test manifest generation."""

    def test_manifest_structure(self):
        """Manifest has required structure and status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()

            flow = compute_flow_quantities(4.0)
            mesh_hash = {"points": "abc123", "faces": "def456"}
            source_revision = "abc1234"
            source_dirty = False

            manifest = generate_manifest(
                output_dir, flow, mesh_hash, source_revision, source_dirty
            )

            # Check structure
            self.assertEqual(manifest["schema_version"], 1)
            self.assertIn("generated_utc", manifest)
            self.assertEqual(manifest["source_revision"], source_revision)
            self.assertEqual(manifest["source_dirty"], source_dirty)
            self.assertEqual(manifest["status"], "unqualified_setup")

            # Check mesh section
            self.assertIn("mesh", manifest)
            self.assertEqual(manifest["mesh"]["source_hash"], mesh_hash)
            self.assertEqual(manifest["mesh"]["copied_files"], mesh_hash)

            # Check flow section
            self.assertIn("flow", manifest)
            self.assertEqual(manifest["flow"]["reynolds_number"], REYNOLDS)
            self.assertEqual(manifest["flow"]["mach_number"], MACH)
            self.assertEqual(manifest["flow"]["freestream_velocity_m_s"], V_INF)

            # Check geometry section
            self.assertIn("geometry", manifest)
            self.assertEqual(manifest["geometry"]["span_m"], SPAN)
            self.assertEqual(manifest["geometry"]["chord_m"], CHORD)
            self.assertEqual(manifest["geometry"]["reference_area_m2"], AREA)
            self.assertEqual(manifest["geometry"]["moment_origin_m"], list(COFR))

    def test_manifest_status_unqualified(self):
        """Manifest explicitly sets status as unqualified_setup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()

            flow = compute_flow_quantities(0.0)
            manifest = generate_manifest(
                output_dir, flow, {}, "rev123", False
            )
            self.assertEqual(manifest["status"], "unqualified_setup")


class OpenFOAMDictionaryTests(unittest.TestCase):
    """Test OpenFOAM dictionary generation."""

    def test_transportProperties(self):
        """transportProperties has Newtonian model and correct nu."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "constant").mkdir()

            from scripts.generate_flow_case import write_constant_transportProperties

            write_constant_transportProperties(output_dir)

            content = (output_dir / "constant" / "transportProperties").read_text()
            self.assertIn("transportModel  Newtonian", content)
            self.assertIn(f"nu              [ 0 2 -1 0 0 0 0 ] {NU}", content)

    def test_turbulenceProperties(self):
        """turbulenceProperties has RAS kOmegaSST."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "constant").mkdir()

            from scripts.generate_flow_case import write_constant_turbulenceProperties

            write_constant_turbulenceProperties(output_dir)

            content = (output_dir / "constant" / "turbulenceProperties").read_text()
            self.assertIn("simulationType  RAS", content)
            self.assertIn("RASModel        kOmegaSST", content)
            self.assertIn("turbulence      on", content)
            self.assertIn("printCoeffs     on", content)

    def test_controlDict(self):
        """controlDict has simpleFoam, iterations, and functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "system").mkdir()

            from scripts.generate_flow_case import write_system_controlDict

            write_system_controlDict(output_dir, 500)

            content = (output_dir / "system" / "controlDict").read_text()
            self.assertIn("application     simpleFoam", content)
            self.assertIn("endTime         500", content)
            self.assertIn("writeInterval   100", content)

            # Check functions section
            self.assertIn("functions", content)
            self.assertIn("forces", content)
            self.assertIn("forceCoeffs", content)
            self.assertIn("solverInfo", content)
            self.assertIn("yPlus", content)
            self.assertIn("wallShearStress", content)

            # Check forceCoeffs reference values
            self.assertIn(f"rhoInf          {RHO}", content)
            self.assertIn(f"magUInf         {V_INF}", content)
            self.assertIn(f"lRef            {CHORD}", content)
            self.assertIn(f"Aref            {AREA}", content)

    def test_fvSchemes(self):
        """fvSchemes has correct schemes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "system").mkdir()

            from scripts.generate_flow_case import write_system_fvSchemes

            write_system_fvSchemes(output_dir)

            content = (output_dir / "system" / "fvSchemes").read_text()
            self.assertIn("ddt", content)
            self.assertIn("gradSchemes", content)
            self.assertIn("divSchemes", content)
            self.assertIn("laplacianSchemes", content)

            # Check specific schemes
            self.assertIn("grad(U)         cellLimited Gauss linear 1", content)
            self.assertIn("div(phi,U)      bounded Gauss linearUpwind grad(U)", content)
            self.assertIn("div(phi,k)      bounded Gauss upwind", content)
            self.assertIn("div(phi,omega)  bounded Gauss upwind", content)

    def test_fvSolution(self):
        """fvSolution has correct solvers and SIMPLE settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "system").mkdir()

            from scripts.generate_flow_case import write_system_fvSolution

            write_system_fvSolution(output_dir)

            content = (output_dir / "system" / "fvSolution").read_text()
            self.assertIn("solvers", content)
            self.assertIn("p", content)
            self.assertIn("GAMG", content)
            self.assertIn("tolerance       1e-8", content)
            self.assertIn("relTol          0.05", content)

            self.assertIn("SIMPLE", content)
            self.assertIn("nNonOrthogonalCorrectors 1", content)
            self.assertIn("consistent      true", content)

            self.assertIn("relaxationFactors", content)
            self.assertIn("p               0.3", content)
            self.assertIn("U               0.7", content)
            self.assertIn("k               0.7", content)
            self.assertIn("omega           0.7", content)

    def test_zero_U(self):
        """0/U has correct boundary conditions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "0").mkdir()

            from scripts.generate_flow_case import write_0_U

            flow = compute_flow_quantities(0.0)
            write_0_U(output_dir, flow)

            content = (output_dir / "0" / "U").read_text()
            self.assertIn("dimensions      [0 1 -1 0 0 0 0]", content)
            # Note: values are formatted as floats (30.0 0.0 0.0)
            self.assertIn("internalField   uniform", content)
            self.assertIn("30.0 0.0 0.0", content)

            # Check boundary conditions
            self.assertIn("inlet", content)
            self.assertIn("fixedValue", content)
            self.assertIn("outlet", content)
            self.assertIn("inletOutlet", content)
            self.assertIn("farfield", content)
            self.assertIn("freestream", content)
            self.assertIn("wing", content)
            self.assertIn("noSlip", content)

    def test_zero_p(self):
        """0_p has correct boundary conditions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "0").mkdir()

            from scripts.generate_flow_case import write_0_p

            flow = compute_flow_quantities(0.0)
            write_0_p(output_dir, flow)

            content = (output_dir / "0" / "p").read_text()
            self.assertIn("dimensions      [0 2 -2 0 0 0 0]", content)
            self.assertIn("inlet", content)
            self.assertIn("zeroGradient", content)
            self.assertIn("outlet", content)
            self.assertIn("fixedValue", content)
            self.assertIn("farfield", content)
            self.assertIn("freestreamPressure", content)
            self.assertIn("wing", content)
            self.assertIn("zeroGradient", content)

    def test_zero_k(self):
        """0_k has correct boundary conditions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "0").mkdir()

            from scripts.generate_flow_case import write_0_k

            flow = compute_flow_quantities(0.0)
            write_0_k(output_dir, flow)

            content = (output_dir / "0" / "k").read_text()
            self.assertIn("dimensions      [0 2 -2 0 0 0 0]", content)
            self.assertIn("inlet", content)
            self.assertIn("fixedValue", content)
            self.assertIn("outlet", content)
            self.assertIn("inletOutlet", content)
            self.assertIn("farfield", content)
            self.assertIn("freestream", content)
            self.assertIn("wing", content)
            self.assertIn("kqRWallFunction", content)

    def test_zero_omega(self):
        """0_omega has correct boundary conditions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "0").mkdir()

            from scripts.generate_flow_case import write_0_omega

            flow = compute_flow_quantities(0.0)
            write_0_omega(output_dir, flow)

            content = (output_dir / "0" / "omega").read_text()
            self.assertIn("dimensions      [0 0 -1 0 0 0 0]", content)
            self.assertIn("inlet", content)
            self.assertIn("fixedValue", content)
            self.assertIn("outlet", content)
            self.assertIn("inletOutlet", content)
            self.assertIn("farfield", content)
            self.assertIn("freestream", content)
            self.assertIn("wing", content)
            self.assertIn("omegaWallFunction", content)

    def test_zero_nut(self):
        """0_nut has correct boundary conditions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "0").mkdir()

            from scripts.generate_flow_case import write_0_nut

            flow = compute_flow_quantities(0.0)
            write_0_nut(output_dir, flow)

            content = (output_dir / "0" / "nut").read_text()
            self.assertIn("dimensions      [0 2 -1 0 0 0 0]", content)
            self.assertIn("inlet", content)
            self.assertIn("calculated", content)
            self.assertIn("outlet", content)
            self.assertIn("farfield", content)
            self.assertIn("wing", content)
            self.assertIn("nutLowReWallFunction", content)


class CommandLineTests(unittest.TestCase):
    """Test command-line argument handling."""

    def test_missing_mesh_dir(self):
        """Missing --mesh-dir raises SystemExit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            with self.assertRaises(SystemExit):
                main()

    def test_missing_output(self):
        """Missing --output raises SystemExit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()
            for f in REQUIRED_MESH_FILES:
                (mesh_dir / f).write_text("test")

            with self.assertRaises(SystemExit):
                main()

    def test_existing_output_rejected(self):
        """Existing output directory is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()
            for f in REQUIRED_MESH_FILES:
                (mesh_dir / f).write_text("test")

            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()

            # Simulate CLI args
            import sys
            old_args = sys.argv
            try:
                sys.argv = [
                    "generate_flow_case.py",
                    "--mesh-dir",
                    str(mesh_dir),
                    "--output",
                    str(output_dir),
                ]
                with self.assertRaises(SystemExit):
                    main()
            finally:
                sys.argv = old_args

    def test_empty_output_directory_rejected(self):
        """Empty output directory is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()
            for f in REQUIRED_MESH_FILES:
                (mesh_dir / f).write_text("test")

            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()  # Empty directory

            import sys
            old_args = sys.argv
            try:
                sys.argv = [
                    "generate_flow_case.py",
                    "--mesh-dir",
                    str(mesh_dir),
                    "--output",
                    str(output_dir),
                ]
                with self.assertRaises(SystemExit):
                    main()
            finally:
                sys.argv = old_args

    def test_invalid_alpha_range(self):
        """Alpha outside [-15, 15] raises SystemExit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()
            for f in REQUIRED_MESH_FILES:
                (mesh_dir / f).write_text("test")

            output_dir = Path(tmpdir) / "case"

            import sys
            old_args = sys.argv
            try:
                sys.argv = [
                    "generate_flow_case.py",
                    "--mesh-dir",
                    str(mesh_dir),
                    "--output",
                    str(output_dir),
                    "--alpha-deg",
                    "20",
                ]
                with self.assertRaises(SystemExit):
                    main()
            finally:
                sys.argv = old_args

    def test_invalid_iterations_range(self):
        """Iterations outside [500, 5000] raises SystemExit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()
            for f in REQUIRED_MESH_FILES:
                (mesh_dir / f).write_text("test")

            output_dir = Path(tmpdir) / "case"

            import sys
            old_args = sys.argv
            try:
                sys.argv = [
                    "generate_flow_case.py",
                    "--mesh-dir",
                    str(mesh_dir),
                    "--output",
                    str(output_dir),
                    "--iterations",
                    "100",
                ]
                with self.assertRaises(SystemExit):
                    main()
            finally:
                sys.argv = old_args

    def test_valid_generation(self):
        """Valid arguments produce case directory with all files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()

            # Create valid mesh files
            (mesh_dir / "points").write_text("30\n(0 0 0)\n(1 0 0)\n(0 1 0)\n")
            (mesh_dir / "faces").write_text("6\n(3 0 1 2)\n" * 6)
            (mesh_dir / "owner").write_text("0\n" * 6)
            (mesh_dir / "neighbour").write_text("0\n" * 6)
            (mesh_dir / "boundary").write_text(
                """3
(
    inlet
    {{
        type            patch;
        nFaces          1;
        startFace       0;
    }}
    outlet
    {{
        type            patch;
        nFaces          1;
        startFace       1;
    }}
    farfield
    {{
        type            patch;
        nFaces          1;
        startFace       2;
    }}
    wing
    {{
        type            patch;
        nFaces          3;
        startFace       3;
    }}
)
"""
            )

            output_dir = Path(tmpdir) / "case"
            # Note: output_dir must NOT exist before calling main()

            import sys
            old_args = sys.argv
            try:
                sys.argv = [
                    "generate_flow_case.py",
                    "--mesh-dir",
                    str(mesh_dir),
                    "--output",
                    str(output_dir),
                    "--alpha-deg",
                    "4",
                    "--iterations",
                    "500",
                ]
                main()
            finally:
                sys.argv = old_args

            # Verify output structure
            self.assertTrue((output_dir / "0" / "U").exists())
            self.assertTrue((output_dir / "0" / "p").exists())
            self.assertTrue((output_dir / "0" / "k").exists())
            self.assertTrue((output_dir / "0" / "omega").exists())
            self.assertTrue((output_dir / "0" / "nut").exists())
            self.assertTrue((output_dir / "constant" / "polyMesh" / "points").exists())
            self.assertTrue((output_dir / "constant" / "polyMesh" / "faces").exists())
            self.assertTrue((output_dir / "constant" / "polyMesh" / "owner").exists())
            self.assertTrue((output_dir / "constant" / "polyMesh" / "neighbour").exists())
            self.assertTrue((output_dir / "constant" / "polyMesh" / "boundary").exists())
            self.assertTrue((output_dir / "constant" / "transportProperties").exists())
            self.assertTrue((output_dir / "constant" / "turbulenceProperties").exists())
            self.assertTrue((output_dir / "system" / "controlDict").exists())
            self.assertTrue((output_dir / "system" / "fvSchemes").exists())
            self.assertTrue((output_dir / "system" / "fvSolution").exists())
            self.assertTrue((output_dir / "manifest.json").exists())

            # Verify manifest
            manifest = json.loads((output_dir / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "unqualified_setup")
            self.assertEqual(manifest["flow"]["alpha_deg"], 4.0)


class FailureHandlingTests(unittest.TestCase):
    """Test failure handling with manifest generation."""

    def test_mesh_copy_failure_creates_manifest(self):
        """Copy failure creates failure manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()
            for f in REQUIRED_MESH_FILES:
                (mesh_dir / f).write_text("test")

            output_dir = Path(tmpdir) / "case"

            import sys
            old_args = sys.argv
            try:
                sys.argv = [
                    "generate_flow_case.py",
                    "--mesh-dir",
                    str(mesh_dir),
                    "--output",
                    str(output_dir),
                ]

                # Simulate failure by patching copy_mesh_files
                import scripts.generate_flow_case as module

                original_copy = module.copy_mesh_files

                def failing_copy(*args, **kwargs):
                    raise OSError("Simulated copy failure")

                module.copy_mesh_files = failing_copy

                try:
                    with self.assertRaises(SystemExit):
                        main()
                finally:
                    module.copy_mesh_files = original_copy

                # Verify failure manifest exists
                self.assertTrue((output_dir / "manifest.json").exists())
                manifest = json.loads((output_dir / "manifest.json").read_text())
                self.assertEqual(manifest["status"], "unqualified_setup")
                self.assertIn("failure", manifest)
                self.assertEqual(manifest["failure"]["stage"], "mesh_copy")
                self.assertIn("error", manifest["failure"])

            finally:
                sys.argv = old_args


class BoundaryPatchTests(unittest.TestCase):
    """Test boundary patch checking."""

    def test_check_boundary_patches(self):
        """Check boundary patches extracts names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()

            boundary_content = """3
(
    inlet
    {{
        type            patch;
        nFaces          10;
        startFace       0;
    }}
    outlet
    {{
        type            patch;
        nFaces          10;
        startFace       10;
    }}
    wing
    {{
        type            wall;
        nFaces          100;
        startFace       20;
    }}
)
"""
            (mesh_dir / "boundary").write_text(boundary_content)

            patches = check_boundary_patches(mesh_dir)

            self.assertIn("inlet", patches)
            self.assertIn("outlet", patches)
            self.assertIn("wing", patches)

    def test_expected_patches_warning(self):
        """Warning for missing expected patches printed to stderr."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_dir = Path(tmpdir) / "mesh"
            mesh_dir.mkdir()

            # Only some patches
            boundary_content = """1
(
    wing
    {{
        type            wall;
        nFaces          100;
        startFace       0;
    }}
)
"""
            (mesh_dir / "boundary").write_text(boundary_content)

            import sys
            from io import StringIO

            old_stderr = sys.stderr
            sys.stderr = StringIO()

            try:
                patches = check_boundary_patches(mesh_dir)
                stderr_output = sys.stderr.getvalue()

                self.assertIn("Warning", stderr_output)
                self.assertIn("inlet", stderr_output)
                self.assertIn("outlet", stderr_output)
                self.assertIn("farfield", stderr_output)
            finally:
                sys.stderr = old_stderr


class ReferenceValuesTests(unittest.TestCase):
    """Test reference values in dictionaries."""

    def test_forceCoeffs_reference_values(self):
        """forceCoeffs uses correct reference values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "system").mkdir()

            from scripts.generate_flow_case import write_system_controlDict

            write_system_controlDict(output_dir, 500)

            content = (output_dir / "system" / "controlDict").read_text()

            # Check forceCoeffs section
            self.assertIn("forceCoeffs", content)
            self.assertIn(f"rhoInf          {RHO}", content)
            self.assertIn(f"magUInf         {V_INF}", content)
            self.assertIn(f"lRef            {CHORD}", content)
            self.assertIn(f"Aref            {AREA}", content)

            # Check lift/drag/pitch axis
            self.assertIn("liftDir", content)
            self.assertIn("dragDir", content)
            self.assertIn("pitchAxis", content)

    def test_forces_cofr(self):
        """forces function uses correct CofR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "system").mkdir()

            from scripts.generate_flow_case import write_system_controlDict

            write_system_controlDict(output_dir, 500)

            content = (output_dir / "system" / "controlDict").read_text()

            # Check CofR
            self.assertIn(f"CofR            ({COFR[0]} {COFR[1]} {COFR[2]})", content)

    def test_dimensional_consistency(self):
        """All dimension sets are correct."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case"
            output_dir.mkdir()
            (output_dir / "0").mkdir()
            (output_dir / "constant").mkdir()
            (output_dir / "system").mkdir()

            from scripts.generate_flow_case import (
                write_0_U,
                write_0_p,
                write_0_k,
                write_0_omega,
                write_0_nut,
                write_constant_transportProperties,
            )

            flow = compute_flow_quantities(0.0)

            write_0_U(output_dir, flow)
            write_0_p(output_dir, flow)
            write_0_k(output_dir, flow)
            write_0_omega(output_dir, flow)
            write_0_nut(output_dir, flow)
            write_constant_transportProperties(output_dir)

            # Verify dimensions in files
            u_content = (output_dir / "0" / "U").read_text()
            self.assertIn("dimensions      [0 1 -1 0 0 0 0]", u_content)  # [0 1 -1 0 0 0 0]

            p_content = (output_dir / "0" / "p").read_text()
            self.assertIn("dimensions      [0 2 -2 0 0 0 0]", p_content)  # [0 2 -2 0 0 0 0]

            k_content = (output_dir / "0" / "k").read_text()
            self.assertIn("dimensions      [0 2 -2 0 0 0 0]", k_content)  # [0 2 -2 0 0 0 0]

            omega_content = (output_dir / "0" / "omega").read_text()
            self.assertIn("dimensions      [0 0 -1 0 0 0 0]", omega_content)  # [0 0 -1 0 0 0 0]

            nut_content = (output_dir / "0" / "nut").read_text()
            self.assertIn("dimensions      [0 2 -1 0 0 0 0]", nut_content)  # [0 2 -1 0 0 0 0]

            trans_content = (output_dir / "constant" / "transportProperties").read_text()
            self.assertIn("nu              [ 0 2 -1 0 0 0 0 ]", trans_content)  # [0 2 -1 0 0 0 0]


if __name__ == "__main__":
    unittest.main()
