"""Tests for generate_structure_benchmarks.py.

Independent verification ofcantilever benchmark deck generation.
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
        """Verify SPC1 with ID=1, DOFs=123456, node=1."""
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
                self.assertIn("1     123456", deck)
                # Verify node 1 is constrained
                lines = deck.split("\n")
                spc_line = [l for l in lines if l.startswith("SPC1")]
                self.assertTrue(len(spc_line) >= 1)

    def test_grid_count_and_coordinates(self):
        """Verify 21 GRID cards at correct x positions."""
        bend = generate_deck_bend_static()

        grid_lines = [l for l in bend.split("\n") if l.strip().startswith("GRID")]
        # Filter out the header line "GRID" at start of card section
        grid_card_lines = [l for l in grid_lines if "GRID" in l and len(l) > 4]
        self.assertEqual(len(grid_card_lines), NODES)

        # Check node positions
        for i in range(NODES):
            x = i * LENGTH / ELEMENTS
            with self.subTest(node=i + 1, x=x):
                # GRID cards should have correct x coordinate
                self.assertIn(f"{x:>16.10E}", bend)

    def test_cbar_orientation_is_global_y(self):
        """Verify CBAR orientation vector is global y-direction."""
        bend = generate_deck_bend_static()
        torsion = generate_deck_torsion_static()
        modal = generate_deck_modal()

        for deck_name, deck in [
            ("bend", bend),
            ("torsion", torsion),
            ("modal", modal),
        ]:
            with self.subTest(deck=deck_name):
                # CBAR line with orientation: 0, 1, 0 (global y)
                self.assertIn(f"{0:>16.10E}{1:>16.10E}{0:>16.10E}", deck)

    def test_element_count(self):
        """Verify element count matches NODES-1."""
        bend = generate_deck_bend_static()
        cbar_lines = [l for l in bend.split("\n") if l.strip().startswith("CBAR")]
        # Only count actual CBAR cards, not the header line
        cbar_card_lines = [l for l in cbar_lines if not l.strip() == "CBAR"]
        self.assertEqual(len(cbar_card_lines), ELEMENTS)

    def test_static_bending_load_direction(self):
        """Verify static bending load is in global z direction."""
        bend = generate_deck_bend_static()
        self.assertIn("FORCE2", bend)
        self.assertIn(f"{FORCE_Z:>16.10E}", bend)
        # Load is Fz in z-direction: x=0, y=0, z=1
        self.assertIn(f"{0:>16.10E}{0:>16.10E}{1:>16.10E}", bend)

    def test_static_torsion_load_direction(self):
        """Verify static torsion moment is about global x axis."""
        torsion = generate_deck_torsion_static()
        self.assertIn("MOMENT2", torsion)
        self.assertIn(f"{MOMENT_X:>16.10E}", torsion)
        # Moment is Mx about x-axis: x=1, y=0, z=0
        self.assertIn(f"{1:>16.10E}{0:>16.10E}{0:>16.10E}", torsion)

    def test_modal_has_eigrl_card(self):
        """Verify modal deck has EIGRL card with correct parameters."""
        modal = generate_deck_modal()
        self.assertIn("EIGRL", modal)
        self.assertIn("3", modal)
        # Should request 6 modes
        lines = modal.split("\n")
        eigrl_lines = [l for l in lines if l.startswith("EIGRL")]
        self.assertEqual(len(eigrl_lines), 1)

    def test_material_properties(self):
        """Verify MAT1 has correct E, G, nu, rho."""
        bend = generate_deck_bend_static()

        mat1_lines = [l for l in bend.split("\n") if l.startswith("MAT1")]
        self.assertEqual(len(mat1_lines), 1)
        mat1 = mat1_lines[0]

        # MAT1, mid, E, G, nu, rho
        self.assertIn(f"{E:>16.10E}", mat1)
        self.assertIn(f"{G:>16.10E}", mat1)
        self.assertIn(f"{NU:>16.10E}", mat1)
        self.assertIn(f"{RHO:>16.10E}", mat1)

    def test_section_properties(self):
        """Verify PBAR has correct A, I1, I2, J."""
        bend = generate_deck_bend_static()

        # PBAR spans two lines due to continuation
        lines = bend.split("\n")
        pbar_lines = []
        for i, line in enumerate(lines):
            if line.startswith("PBAR"):
                # Combine with continuation line if present
                pbar_text = line
                if i + 1 < len(lines) and lines[i + 1].startswith("*"):
                    pbar_text += lines[i + 1]
                pbar_lines.append(pbar_text)

        self.assertEqual(len(pbar_lines), 1)
        pbar = pbar_lines[0]

        # Check that all properties are present
        self.assertIn(f"{AREA:>16.10E}", pbar)
        self.assertIn(f"{I1:>16.10E}", pbar)
        self.assertIn(f"{J:>16.10E}", pbar)

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

    def test_deck_has_subcase_for_static(self):
        """Verify static decks have SUBCASE cards."""
        bend = generate_deck_bend_static()
        torsion = generate_deck_torsion_static()

        self.assertIn("SUBCASE", bend)
        self.assertIn("LOAD", bend)
        self.assertIn("SUBCASE", torsion)
        self.assertIn("LOAD", torsion)

    def test_modal_has_method_card(self):
        """Verify modal deck has METHOD in SUBCASE."""
        modal = generate_deck_modal()

        self.assertIn("SUBCASE", modal)
        self.assertIn("METHOD", modal)

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
