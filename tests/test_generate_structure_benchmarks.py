"""Tests for generate_structure_benchmarks.py.

Independent verification ofcantilever benchmark deck generation.
Tests verify output matches native reference fixtures with comma-delimited format.
"""

import json
import math
import tempfile
import unittest
from pathlib import Path
from scripts.generate_structure_benchmarks import (
    generate_deck_bend_static,
    generate_deck_torsion_static,
    generate_deck_modal,
    generate_reference_json,
    write_deck,
    ELEMENTS,
    NODES,
    RADIUS,
    LENGTH,
    E,
    NU,
    RHO,
    G,
    AREA,
    I1,
    J,
    FORCE_Z,
    MOMENT_X,
    DELTA_STATIC_BEND,
    THETA_STATIC_BEND,
    PHI_STATIC_TORSION,
    TOTAL_MASS,
    FREQ1,
    FREQ2,
    FREQ3,
    BETA1,
    BETA2,
    BETA3,
    validate_element_count,
    validate_nonnegative,
)


def format_decimal(val):
    """Format decimal with at most 1 decimal place, removing trailing zeros after decimal."""
    formatted = f"{val:.1f}"
    if formatted.endswith(".0"):
        return formatted[:-1]
    return formatted


class StructureBenchTests(unittest.TestCase):
    """Test deck content, geometry, load direction, mass, reference scaling."""

    def test_deck_contains_required_cards(self):
        """Verify decks contain all required Nastran cards."""
        bend = generate_deck_bend_static()
        torsion = generate_deck_torsion_static()
        modal = generate_deck_modal()

        required_cards = ["GRID", "CBAR", "PBAR", "MAT1", "SPC1", "ENDDATA"]

        for card in required_cards:
            with self.subTest(card=card):
                self.assertIn(card, bend)
                self.assertIn(card, torsion)
                self.assertIn(card, modal)

    def test_deck_has_correct_solution(self):
        """Verify SOL101 for static cases, SOL103 for modal."""
        bend = generate_deck_bend_static()
        torsion = generate_deck_torsion_static()
        modal = generate_deck_modal()

        self.assertIn("SOL 101", bend)
        self.assertIn("SOL 101", torsion)
        self.assertIn("SOL 103", modal)

    def test_deck_has_spcl_1_dof_constraint(self):
        """Verify SPC1 with ID=1, DOFs=123456, node=1 in comma-delimited format."""
        bend = generate_deck_bend_static()
        torsion = generate_deck_torsion_static()
        modal = generate_deck_modal()

        for deck_name, deck in [
            ("bend", bend),
            ("torsion", torsion),
            ("modal", modal),
        ]:
            with self.subTest(deck=deck_name):
                self.assertIn("SPC1", deck)
                # Check comma-delimited format: SPC1,1,123456,1
                self.assertIn("SPC1,1,123456,1", deck)
                # Verify node 1 is constrained
                lines = deck.split("\n")
                spc_line = [l for l in lines if l.startswith("SPC1")]
                self.assertTrue(len(spc_line) >= 1)

    def test_grid_count_and_coordinates(self):
        """Verify 21 GRID cards at correct x positions with comma-delimited format."""
        bend = generate_deck_bend_static()

        # GRID cards are comma-delimited: GRID,id,,x,y,z
        grid_lines = [l for l in bend.split("\n") if l.startswith("GRID,")]
        self.assertEqual(len(grid_lines), NODES)

        # Check node positions with 8 decimal places for x
        for i in range(NODES):
            x = i * LENGTH / ELEMENTS
            with self.subTest(node=i + 1, x=x):
                # GRID cards should have correct x coordinate with 8 decimal places
                self.assertIn(f",{x:.8f},", bend)

    def test_cbar_orientation_is_global_y(self):
        """Verify CBAR orientation vector is global y-direction with comma-delimited format."""
        bend = generate_deck_bend_static()
        torsion = generate_deck_torsion_static()
        modal = generate_deck_modal()

        for deck_name, deck in [
            ("bend", bend),
            ("torsion", torsion),
            ("modal", modal),
        ]:
            with self.subTest(deck=deck_name):
                # CBAR cards are comma-delimited: CBAR,eid,pid,g1,g2,x1,x2,x3
                # orientation: 0., 1., 0. (global y)
                self.assertIn("CBAR,1,1,1,2,0.,1.,0.", deck)

    def test_element_count(self):
        """Verify element count matches NODES-1."""
        bend = generate_deck_bend_static()
        # CBAR cards are comma-delimited: CBAR,eid,pid,g1,g2,x1,x2,x3
        cbar_lines = [l for l in bend.split("\n") if l.startswith("CBAR,")]
        self.assertEqual(len(cbar_lines), ELEMENTS)

    def test_static_bending_load_direction(self):
        """Verify static bending load is in global z direction using FORCE card."""
        bend = generate_deck_bend_static()
        # Check for FORCE card (not FORCE2) with correct format
        expected_force = f"FORCE,2,{NODES},,{format_decimal(FORCE_Z)},{format_decimal(0.)},{format_decimal(0.)},{format_decimal(1.)}"
        self.assertIn("FORCE,", bend)
        self.assertIn(expected_force, bend)
        # Check load set ID 2 is selected in case control
        self.assertIn("LOAD = 2", bend)

    def test_static_torsion_load_direction(self):
        """Verify static torsion moment is about global x axis using MOMENT card."""
        torsion = generate_deck_torsion_static()
        # Check for MOMENT card (not MOMENT2) with correct format
        expected_moment = f"MOMENT,2,{NODES},,{format_decimal(MOMENT_X)},{format_decimal(1.)},{format_decimal(0.)},{format_decimal(0.)}"
        self.assertIn("MOMENT,", torsion)
        self.assertIn(expected_moment, torsion)
        # Check load set ID 2 is selected in case control
        self.assertIn("LOAD = 2", torsion)

    def test_modal_has_eigrl_card(self):
        """Verify modal deck has EIGRL card with correct parameters."""
        modal = generate_deck_modal()
        self.assertIn("EIGRL", modal)
        # Check for minimal format: EIGRL,3,,,6
        self.assertIn("EIGRL,3,,,6", modal)

    def test_material_properties(self):
        """Verify MAT1 has correct E, G, nu, rho with comma-delimited format."""
        bend = generate_deck_bend_static()

        mat1_lines = [l for l in bend.split("\n") if l.startswith("MAT1,")]
        self.assertEqual(len(mat1_lines), 1)
        mat1 = mat1_lines[0]

        # MAT1, mid, E, G, nu, rho
        self.assertIn("MAT1,1,", mat1)
        self.assertIn(f"{E:.9E}", mat1)
        self.assertIn(f"{G:.9E}", mat1)
        # nu and rho use format_decimal for trailing zeros removal
        self.assertIn(f"{NU:g}", mat1)
        self.assertIn(f"{format_decimal(RHO)}", mat1)

    def test_section_properties(self):
        """Verify PBAR has correct A, I1, I2, J with comma-delimited format."""
        bend = generate_deck_bend_static()

        # PBAR is single-line comma-delimited
        lines = bend.split("\n")
        pbar_lines = [l for l in lines if l.startswith("PBAR,")]

        self.assertEqual(len(pbar_lines), 1)
        pbar = pbar_lines[0]

        # Check that all properties are present with 9 significant digits
        self.assertIn(f"{AREA:.9E}", pbar)
        self.assertIn(f"{I1:.9E}", pbar)
        self.assertIn(f"{J:.9E}", pbar)

    def test_sha256_hash_in_json(self):
        """Verify reference JSON contains SHA256 hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            hashes = {
                "bend_static": "a" * 64,
                "torsion_static": "b" * 64,
                "modal_bend": "c" * 64,
            }
            json_path = generate_reference_json(output_dir, hashes)

            with open(json_path) as f:
                ref = json.load(f)

            self.assertIn("output_files", ref)
            self.assertIn("bend_static", ref["output_files"])
            self.assertEqual(ref["output_files"]["bend_static"]["sha256"], "a" * 64)

    def test_reference_json_has_analytic_values(self):
        """Verify reference JSON has correct analytic values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            hashes = {"bend_static": "a" * 64, "torsion_static": "b" * 64, "modal_bend": "c" * 64}
            json_path = generate_reference_json(output_dir, hashes)

            with open(json_path) as f:
                ref = json.load(f)

            # Check static bending values
            self.assertAlmostEqual(ref["static_bending"]["analytic_delta_m"], DELTA_STATIC_BEND)
            self.assertAlmostEqual(ref["static_bending"]["analytic_rotation_rad"], THETA_STATIC_BEND)
            self.assertEqual(ref["static_bending"]["load_N"], FORCE_Z)

            # Check static torsion values
            self.assertAlmostEqual(ref["static_torsion"]["analytic_angle_rad"], PHI_STATIC_TORSION)
            self.assertEqual(ref["static_torsion"]["load_Nm"], MOMENT_X)

            # Check modal values
            self.assertAlmostEqual(ref["modal_bending"]["analytic_frequencies_hz"][0], FREQ1)
            self.assertAlmostEqual(ref["modal_bending"]["analytic_frequencies_hz"][1], FREQ2)
            self.assertAlmostEqual(ref["modal_bending"]["analytic_frequencies_hz"][2], FREQ3)
            self.assertEqual(ref["modal_bending"]["euler_beta_values"][0], BETA1)
            self.assertEqual(ref["modal_bending"]["euler_beta_values"][1], BETA2)
            self.assertEqual(ref["modal_bending"]["euler_beta_values"][2], BETA3)

            # Check mass
            self.assertAlmostEqual(ref["mass"]["total_kg"], TOTAL_MASS)

    def test_reference_json_has_tolerances(self):
        """Verify reference JSON has prospective tolerances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            hashes = {"bend_static": "a" * 64, "torsion_static": "b" * 64, "modal_bend": "c" * 64}
            json_path = generate_reference_json(output_dir, hashes)

            with open(json_path) as f:
                ref = json.load(f)

            self.assertEqual(ref["static_bending"]["tolerance_rel"], 0.01)
            self.assertEqual(ref["modal_bending"]["tolerance_first_bending_rel"], 0.02)
            self.assertEqual(ref["tolerances_prospective"]["static"], 0.01)
            self.assertEqual(ref["tolerances_prospective"]["first_bending_frequency"], 0.02)

    def test_reference_json_has_solver_info(self):
        """Verify reference JSON has solver provenance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            hashes = {"bend_static": "a" * 64, "torsion_static": "b" * 64, "modal_bend": "c" * 64}
            generate_reference_json(output_dir, hashes)

            with open(output_dir / "reference.json") as f:
                ref = json.load(f)

            self.assertIn("solver", ref)
            self.assertEqual(ref["solver"], "MYSTRAN 19.0.0")
            self.assertIn("solver_commit", ref)
            self.assertEqual(
                ref["solver_commit"], "3a5913a904ee1adbda9fbcaf9c0a6af8e10f0f9f"
            )
            self.assertIn("solver_url", ref)
            self.assertIn("mystransolver", ref["solver_url"].lower())

    def test_reference_json_has_assumptions(self):
        """Verify reference JSON documents assumptions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            hashes = {"bend_static": "a" * 64, "torsion_static": "b" * 64, "modal_bend": "c" * 64}
            generate_reference_json(output_dir, hashes)

            with open(output_dir / "reference.json") as f:
                ref = json.load(f)

            self.assertIn("assumptions", ref)
            self.assertIn("beam_theory", ref["assumptions"])
            self.assertEqual(ref["assumptions"]["beam_theory"], "Euler-Bernoulli (slender beam, no shear/rotary inertia)")
            self.assertIn("solver_formulations", ref["assumptions"])
            self.assertIn("verification", ref["assumptions"])

    def test_cli_refuses_existing_nonempty_output(self):
        """Verify CLI refuses to overwrite existing non-empty output directory."""
        from scripts.generate_structure_benchmarks import main
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create non-empty directory
            (output_dir / "dummy.txt").write_text("test")

            # Save original argv
            orig_argv = sys.argv

            try:
                # Should raise SystemExit with error
                sys.argv = [
                    "generate_structure_benchmarks.py",
                    "--output-directory",
                    str(output_dir),
                ]
                with self.assertRaises(SystemExit):
                    main()
            finally:
                sys.argv = orig_argv

    def test_cli_creates_output_directory(self):
        """Verify CLI creates output directory if it doesn't exist."""
        from scripts.generate_structure_benchmarks import main
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "new_subdir"

            # Should not exist yet
            self.assertFalse(output_dir.exists())

            orig_argv = sys.argv
            try:
                sys.argv = [
                    "generate_structure_benchmarks.py",
                    "--output-directory",
                    str(output_dir),
                ]
                main()

                # Directory should exist and contain files
                self.assertTrue(output_dir.exists())
                self.assertTrue((output_dir / "bend_static.bdf").exists())
                self.assertTrue((output_dir / "torsion_static.bdf").exists())
                self.assertTrue((output_dir / "modal_bend.bdf").exists())
                self.assertTrue((output_dir / "reference.json").exists())
            finally:
                sys.argv = orig_argv

    def test_cli_output_is_deterministic(self):
        """Verify multiple runs produce identical decks."""
        from scripts.generate_structure_benchmarks import main
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            output1 = Path(tmpdir) / "output1"
            output2 = Path(tmpdir) / "output2"

            orig_argv = sys.argv
            try:
                sys.argv = ["generate_structure_benchmarks.py", "--output-directory", str(output1)]
                main()

                sys.argv = ["generate_structure_benchmarks.py", "--output-directory", str(output2)]
                main()

                # Compare files
                self.assertEqual(
                    (output1 / "bend_static.bdf").read_text(),
                    (output2 / "bend_static.bdf").read_text(),
                )
                self.assertEqual(
                    (output1 / "torsion_static.bdf").read_text(),
                    (output2 / "torsion_static.bdf").read_text(),
                )
                self.assertEqual(
                    (output1 / "modal_bend.bdf").read_text(),
                    (output2 / "modal_bend.bdf").read_text(),
                )
            finally:
                sys.argv = orig_argv

    def test_invalid_element_count_rejected(self):
        """Validate function rejects invalid element counts."""
        # Non-integer
        with self.assertRaises(ValueError):
            validate_element_count(10.5)
        # Boolean (should be rejected)
        with self.assertRaises(ValueError):
            validate_element_count(True)
        # Too small
        with self.assertRaises(ValueError):
            validate_element_count(1)
        # Negative
        with self.assertRaises(ValueError):
            validate_element_count(-5)
        # Zero
        with self.assertRaises(ValueError):
            validate_element_count(0)

    def test_invalid_nonnegative_rejected(self):
        """Validate function rejects nonfinite or negative values."""
        with self.assertRaises(ValueError):
            validate_nonnegative("test", math.nan)
        with self.assertRaises(ValueError):
            validate_nonnegative("test", math.inf)
        with self.assertRaises(ValueError):
            validate_nonnegative("test", -1.0)

    def test_custom_parameters_accepted(self):
        """Verify custom parameters are accepted without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.generate_structure_benchmarks import main
            import sys

            output = Path(tmpdir) / "custom"
            orig_argv = sys.argv
            try:
                sys.argv = [
                    "generate_structure_benchmarks.py",
                    "--output-directory",
                    str(output),
                    "--element-count",
                    "30",  # Different from default 20
                    "--radius",
                    "0.01",  # Different from default 0.005
                ]
                main()

                # Directory should exist and contain files
                self.assertTrue(output.exists())
                self.assertTrue((output / "bend_static.bdf").exists())
                self.assertTrue((output / "reference.json").exists())
            finally:
                sys.argv = orig_argv

    def test_static_decks_have_cend_case_control(self):
        """Verify static decks have direct CEND case control (no SUBCASE)."""
        bend = generate_deck_bend_static()
        torsion = generate_deck_torsion_static()

        # No SUBCASE in the decks
        self.assertNotIn("SUBCASE", bend)
        self.assertNotIn("SUBCASE", torsion)

        # But have direct case control
        self.assertIn("LOAD = 2", bend)
        self.assertIn("LOAD = 2", torsion)
        self.assertIn("SPC = 1", bend)
        self.assertIn("SPC = 1", torsion)

    def test_modal_has_method_card(self):
        """Verify modal deck has METHOD in CEND (no SUBCASE)."""
        modal = generate_deck_modal()

        # No SUBCASE in the deck
        self.assertNotIn("SUBCASE", modal)

        # But has METHOD in CEND
        self.assertIn("METHOD = 3", modal)

    def test_empty_output_directory_accepted(self):
        """Verify CLI accepts empty output directory."""
        from scripts.generate_structure_benchmarks import main
        import sys

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "empty"

            # Create empty directory
            output_dir.mkdir()

            orig_argv = sys.argv
            try:
                sys.argv = ["generate_structure_benchmarks.py", "--output-directory", str(output_dir)]
                main()

                self.assertTrue((output_dir / "bend_static.bdf").exists())
            finally:
                sys.argv = orig_argv


if __name__ == "__main__":
    unittest.main()
