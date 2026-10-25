#!/usr/bin/env python3
"""
Unit tests for qualify_runtime.py - runtime qualification launcher.

These tests validate the parser and validation logic without requiring Docker.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path


class TestOpenFOAMMeshParser(unittest.TestCase):
    """Test checkMesh log parsing."""
    
    def test_parse_mesh_ok(self):
        """Parse a checkMesh output with Mesh OK result."""
        from scripts.qualify_runtime import parse_openfoam_mesh_log
        
        log = """
Create cells

    cells:           1000
    faces:           3000
    boundary patches: 6

Mesh check OK
"""
        result = parse_openfoam_mesh_log(log)
        
        self.assertTrue(result["mesh_check_passed"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["cells"], 1000)
        self.assertEqual(result["faces"], 3000)
        self.assertEqual(result["boundary_patches"], 6)
    
    def test_parse_mesh_with_cells_faces(self):
        """Parse checkMesh output with cells and faces counts."""
        from scripts.qualify_runtime import parse_openfoam_mesh_log
        
        log = """
Creating mesh from blockMesh...
Creating block topology...
Creating polyMesh from blockMesh

Creating cells

    cells:           4000
    faces:           12000
    boundary patches: 6

Mesh check OK
"""
        result = parse_openfoam_mesh_log(log)
        
        self.assertTrue(result["ok"])
        self.assertEqual(result["cells"], 4000)
        self.assertEqual(result["faces"], 12000)


class TestOpenFOAMSolverParser(unittest.TestCase):
    """Test icoFoam solver log parsing."""
    
    def test_parse_solver_end(self):
        """Parse solver log with End marker."""
        from scripts.qualify_runtime import parse_openfoam_icofoam_log
        
        log = """
Time = 0.1

Courant Number mean: 0.01 max: 0.1

smoothSolver:  Solving for Ux, Initial residual = 0.01, Final residual = 1e-06, No Iterations 5
smoothSolver:  Solving for Uy, Initial residual = 0.02, Final residual = 2e-06, No Iterations 4

time step continuity errors : sum local = 1e-08, global = 1e-10, cumulative = 1e-10

End
"""
        result = parse_openfoam_icofoam_log(log)
        
        self.assertTrue(result["ended_successfully"])
        self.assertEqual(result["final_time"], 0.1)
    
    def test_parse_solver_time(self):
        """Parse solver log with final time."""
        from scripts.qualify_runtime import parse_openfoam_icofoam_log
        
        log = """
Starting time loop

Time = 0.1

Courant Number mean: 0.01 max: 0.1

Time = 0.2

Courant Number mean: 0.02 max: 0.2

Time = 0.3

Courant Number mean: 0.03 max: 0.3

Time = 0.4

Courant Number mean: 0.04 max: 0.4

Time = 0.5

Courant Number mean: 0.05 max: 0.5

Final time = 0.5

End
"""
        result = parse_openfoam_icofoam_log(log)
        
        self.assertTrue(result["ended_successfully"])
        self.assertEqual(result["final_time"], 0.5)
        self.assertLessEqual(result["max_courant"], 1.0)
    
    def test_parse_continuity_errors(self):
        """Parse continuity error messages."""
        from scripts.qualify_runtime import parse_openfoam_icofoam_log
        
        log = """
time step continuity errors : sum local = 9.66354e-09, global = 1e-11, cumulative = -4.19231e-18

End
"""
        result = parse_openfoam_icofoam_log(log)
        
        self.assertIsNotNone(result["local_continuity_final"])
        self.assertLessEqual(abs(result["local_continuity_final"]), 1e-6)
        
        self.assertIsNotNone(result["cumulative_continuity_abs_final"])
        self.assertLessEqual(abs(result["cumulative_continuity_abs_final"]), 1e-10)
    
    def test_parse_velocity_fields(self):
        """Parse velocity field information."""
        from scripts.qualify_runtime import parse_openfoam_icofoam_log
        
        log = """
volVectorField U
    U,min = -0.1
    U,max = 0.15
    Ux,min = -0.1
    Ux,max = 0.1
    Uy,min = -0.05
    Uy,max = 0.05

End
"""
        result = parse_openfoam_icofoam_log(log)
        
        # The parser now counts volVectorField/volScalarField, not parsing Ux ranges from this format
        self.assertEqual(result["velocity_vector_count"], 1)
        self.assertEqual(result["pressure_count"], 0)
        # Speed range defaults to [inf, -inf] when not parsed from actual solver output
        self.assertEqual(result["ux_signs"], set())


class TestFileHashing(unittest.TestCase):
    """Test SHA256 file hashing."""
    
    def test_sha256_empty_file(self):
        """Hash empty file produces consistent result."""
        from scripts.qualify_runtime import sha256_file
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
        
        try:
            hash1 = sha256_file(temp_path)
            hash2 = sha256_file(temp_path)
            self.assertEqual(hash1, hash2)
        finally:
            os.unlink(temp_path)
    
    def test_sha256_consistency(self):
        """Hash is deterministic for same content."""
        from scripts.qualify_runtime import sha256_file, sha256_string
        
        test_string = "OpenFOAM validation test"
        
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(test_string)
            temp_path = f.name
        
        try:
            file_hash = sha256_file(temp_path)
            string_hash = sha256_string(test_string)
            self.assertEqual(file_hash, string_hash)
        finally:
            os.unlink(temp_path)


class TestOutputPathValidation(unittest.TestCase):
    """Test output path validation."""
    
    def test_existing_empty_directory_allowed(self):
        """Empty directory is acceptable."""
        from scripts.qualify_runtime import ensure_output_path_empty
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not raise
            ensure_output_path_empty(tmpdir)
    
    def test_nonexistent_directory_allowed(self):
        """Non-existent path is acceptable (will be created)."""
        from scripts.qualify_runtime import ensure_output_path_empty
        
        with tempfile.TemporaryDirectory() as tmpdir:
            new_path = os.path.join(tmpdir, "new_dir")
            # Should not raise
            ensure_output_path_empty(new_path)
    
    def test_nonempty_directory_rejected(self):
        """Non-empty directory is rejected."""
        from scripts.qualify_runtime import ensure_output_path_empty
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file in the directory
            (Path(tmpdir) / "some_file.txt").write_text("content")
            
            with self.assertRaises(ValueError) as ctx:
                ensure_output_path_empty(tmpdir)
            
            self.assertIn("not empty", str(ctx.exception))
    
    def test_file_path_rejected(self):
        """Existing file path is rejected."""
        from scripts.qualify_runtime import ensure_output_path_empty
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
        
        try:
            with self.assertRaises(ValueError) as ctx:
                ensure_output_path_empty(temp_path)
            
            self.assertIn("not a directory", str(ctx.exception))
        finally:
            os.unlink(temp_path)


class TestArtifacts(unittest.TestCase):
    """Test artifact structure and content."""
    
    def test_report_json_structure(self):
        """Report JSON contains required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "qualify_report.json"
            
            report = {
                "status": "passed",
                "image": {
                    "reference": "opencfd/openfoam-default@sha256:abc123",
                    "version": "v2412",
                },
                "git": {
                    "revision": "abc123def",
                    "dirty": False,
                },
                "utc": "2026-10-25T00:00:00+00:00",
            }
            
            with open(report_path, "w") as f:
                json.dump(report, f)
            
            # Read back and verify
            with open(report_path) as f:
                loaded = json.load(f)
            
            self.assertEqual(loaded["status"], "passed")
            self.assertIn("image", loaded)
            self.assertIn("git", loaded)
            self.assertIn("utc", loaded)


class TestShellPayload(unittest.TestCase):
    """Test shell script generation."""
    
    def test_shell_script_contains_foam_sources(self):
        """Shell script sources OpenFOAM bashrc."""
        from scripts.qualify_runtime import SHELL_PAYLOAD, FOAM_BASHRC
        
        self.assertIn(FOAM_BASHRC, SHELL_PAYLOAD)
        self.assertIn("set +u", SHELL_PAYLOAD)
        self.assertIn("source", SHELL_PAYLOAD)
        self.assertIn("blockMesh", SHELL_PAYLOAD)
        self.assertIn("checkMesh", SHELL_PAYLOAD)
        self.assertIn("icoFoam", SHELL_PAYLOAD)
    
    def test_shell_script_sets_u_after_source(self):
        """Shell script enables nounset after sourcing."""
        from scripts.qualify_runtime import SHELL_PAYLOAD
        
        # Find the sequence
        lines = SHELL_PAYLOAD.split("\n")
        
        source_idx = None
        set_u_idx = None
        
        for i, line in enumerate(lines):
            if "source" in line and "bashrc" in line:
                source_idx = i
            if "set -u" in line:
                set_u_idx = i
        
        self.assertIsNotNone(source_idx, "Source command not found")
        self.assertIsNotNone(set_u_idx, "set -u not found")
        self.assertGreater(set_u_idx, source_idx, "set -u should come after source")


if __name__ == "__main__":
    unittest.main()
