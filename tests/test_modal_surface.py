"""Tests for modal_surface module."""

import importlib.util
import math
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/modal_surface.py"
spec = importlib.util.spec_from_file_location("modal", SCRIPT)
modal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modal)


class DisplacementTests(unittest.TestCase):
    def test_single_mode_unit_displacement(self):
        # One mode, one point, displacement in x
        basis = [[[1.0, 0.0, 0.0]]]
        q = [2.0]
        u = modal.displacements(basis, q)
        self.assertEqual(len(u), 1)
        self.assertEqual(len(u[0]), 3)
        self.assertAlmostEqual(u[0][0], 2.0)
        self.assertAlmostEqual(u[0][1], 0.0)
        self.assertAlmostEqual(u[0][2], 0.0)

    def test_two_modes_two_points(self):
        # Two modes, two points: mode0=x, mode1=z
        basis = [
            [[1.0, 0.0, 0.0], [0.5, 0.0, 0.0]],  # mode 0: x displacement
            [[0.0, 0.0, 1.0], [0.0, 0.0, 0.5]],  # mode 1: z displacement
        ]
        q = [1.0, 2.0]
        u = modal.displacements(basis, q)
        # Point 0: 1*mode0 + 2*mode1 = [1,0,0] + [0,0,2] = [1,0,2]
        self.assertAlmostEqual(u[0][0], 1.0)
        self.assertAlmostEqual(u[0][1], 0.0)
        self.assertAlmostEqual(u[0][2], 2.0)
        # Point 1: 1*mode0 + 2*mode1 = [0.5,0,0] + [0,0,1] = [0.5,0,1]
        self.assertAlmostEqual(u[1][0], 0.5)
        self.assertAlmostEqual(u[1][1], 0.0)
        self.assertAlmostEqual(u[1][2], 1.0)

    def test_mixed_directions(self):
        # Mode with mixed x,y,z components
        basis = [[[1.0, 2.0, 3.0]]]
        q = [0.5]
        u = modal.displacements(basis, q)
        self.assertAlmostEqual(u[0][0], 0.5)
        self.assertAlmostEqual(u[0][1], 1.0)
        self.assertAlmostEqual(u[0][2], 1.5)

    def test_zero_q_gives_zero_u(self):
        basis = [
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[0.0, 0.0, 1.0], [1.0, 0.0, 0.0]],
        ]
        q = [0.0, 0.0]
        u = modal.displacements(basis, q)
        for pt in u:
            for comp in pt:
                self.assertEqual(comp, 0.0)

    def test_nonmutation(self):
        basis = [[[1.0, 0.0, 0.0]]]
        q = [1.0]
        q_orig = q.copy()
        u = modal.displacements(basis, q)
        self.assertEqual(q, q_orig)


class GeneralizedForceTests(unittest.TestCase):
    def test_single_force_one_mode(self):
        basis = [[[1.0, 0.0, 0.0]]]
        forces = [[5.0, 0.0, 0.0]]
        Q = modal.generalized_forces(basis, forces)
        self.assertEqual(len(Q), 1)
        self.assertAlmostEqual(Q[0], 5.0)

    def test_force_perpendicular_to_mode(self):
        basis = [[[1.0, 0.0, 0.0]]]
        forces = [[0.0, 5.0, 0.0]]  # force in y, mode in x
        Q = modal.generalized_forces(basis, forces)
        self.assertAlmostEqual(Q[0], 0.0)

    def test_two_points_work_contribution(self):
        # Two points with forces that do work via two modes
        basis = [
            [[1.0, 0.0, 0.0], [0.0, 0.0, 0.0]],  # mode 0: only point 0 moves in x
            [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],  # mode 1: only point 1 moves in z
        ]
        forces = [[10.0, 0.0, 0.0], [0.0, 0.0, 20.0]]  # point 0 gets fx=10, point 1 gets fz=20
        Q = modal.generalized_forces(basis, forces)
        # Q[0] = 1*10 + 0*0 = 10
        # Q[1] = 0*0 + 1*20 = 20
        self.assertAlmostEqual(Q[0], 10.0)
        self.assertAlmostEqual(Q[1], 20.0)

    def test_nonmutation(self):
        basis = [[[1.0, 0.0, 0.0]]]
        forces = [[5.0, 0.0, 0.0]]
        forces_orig = [pt.copy() for pt in forces]
        Q = modal.generalized_forces(basis, forces)
        self.assertEqual(forces, forces_orig)


class VirtualWorkTests(unittest.TestCase):
    def test_work_consistency(self):
        # Verify Hq dot f = q dot H^T f for random values
        import random
        random.seed(42)
        for _ in range(5):
            nmodes = random.randint(1, 3)
            npts = random.randint(1, 3)
            basis = []
            for _ in range(nmodes):
                mode = []
                for _ in range(npts):
                    pt = [random.uniform(-2, 2) for _ in range(3)]
                    mode.append(pt)
                basis.append(mode)
            q = [random.uniform(-1, 1) for _ in range(nmodes)]
            forces = [[random.uniform(-5, 5) for _ in range(3)] for _ in range(npts)]

            u = modal.displacements(basis, q)
            # u dot f
            work_u_f = 0.0
            for pt_u, pt_f in zip(u, forces):
                for k in range(3):
                    work_u_f += pt_u[k] * pt_f[k]

            Q = modal.generalized_forces(basis, forces)
            # q dot Q
            work_q_Q = sum(qi * Qi for qi, Qi in zip(q, Q))

            self.assertAlmostEqual(work_u_f, work_q_Q, places=10)

    def test_work_with_multiple_modes_nonorthogonal(self):
        # Non-orthogonal modes: both affect same point
        basis = [
            [[1.0, 0.5, 0.0], [0.0, 0.0, 0.0]],  # mode 0
            [[0.0, 0.0, 0.0], [0.5, 1.0, 0.0]],  # mode 1
        ]
        q = [2.0, 3.0]
        forces = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

        u = modal.displacements(basis, q)
        # Point 0: 2*[1,0.5,0] + 3*[0,0,0] = [2,1,0]
        # Point 1: 2*[0,0,0] + 3*[0.5,1,0] = [1.5,3,0]
        self.assertAlmostEqual(u[0][0], 2.0)
        self.assertAlmostEqual(u[0][1], 1.0)
        self.assertAlmostEqual(u[1][0], 1.5)
        self.assertAlmostEqual(u[1][1], 3.0)

        Q = modal.generalized_forces(basis, forces)
        # Q[0] = [1,0.5,0]·[1,0,0] + [0,0,0]·[0,1,0] = 1*1 + 0.5*0 = 1
        # Q[1] = [0,0,0]·[1,0,0] + [0.5,1,0]·[0,1,0] = 0.5*0 + 1*1 = 1
        self.assertAlmostEqual(Q[0], 1.0)
        self.assertAlmostEqual(Q[1], 1.0)

        work_u_f = u[0][0] * forces[0][0] + u[0][1] * forces[0][1]
        work_u_f += u[1][0] * forces[1][0] + u[1][1] * forces[1][1]
        work_q_Q = q[0] * Q[0] + q[1] * Q[1]
        self.assertAlmostEqual(work_u_f, work_q_Q, places=10)


class MassMatrixTests(unittest.TestCase):
    def test_single_mode_single_point(self):
        basis = [[[1.0, 0.0, 0.0]]]
        masses = [100.0]  # 100 grams
        M = modal.mass_gram(basis, masses)
        # M[0][0] = m * phi_x * phi_x = 100 * 1 * 1 = 100
        self.assertEqual(len(M), 1)
        self.assertEqual(len(M[0]), 1)
        self.assertAlmostEqual(M[0][0], 100.0)

    def test_two_modes_single_point_diagonal(self):
        # Independent x and z modes at one point
        basis = [
            [[1.0, 0.0, 0.0]],  # mode 0: x
            [[0.0, 0.0, 1.0]],  # mode 1: z
        ]
        masses = [100.0]
        M = modal.mass_gram(basis, masses)
        # M[0][0] = 100 * 1 * 1 = 100
        # M[1][1] = 100 * 1 * 1 = 100
        # M[0][1] = M[1][0] = 100 * 1 * 0 = 0
        self.assertAlmostEqual(M[0][0], 100.0)
        self.assertAlmostEqual(M[1][1], 100.0)
        self.assertAlmostEqual(M[0][1], 0.0)
        self.assertAlmostEqual(M[1][0], 0.0)

    def test_two_modes_two_points_offdiagonal(self):
        # Two points, modes couple via shared coordinates
        basis = [
            [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],  # mode 0: both points x
            [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],  # mode 1: both points z
        ]
        masses = [50.0, 50.0]  # 50g + 50g = 100g total
        M = modal.mass_gram(basis, masses)
        # M[0][0] = 50*1*1 + 50*1*1 = 100
        # M[1][1] = 50*1*1 + 50*1*1 = 100
        # M[0][1] = M[1][0] = 50*1*0 + 50*1*0 = 0
        self.assertAlmostEqual(M[0][0], 100.0)
        self.assertAlmostEqual(M[1][1], 100.0)
        self.assertAlmostEqual(M[0][1], 0.0)

    def test_coupled_modes_offdiagonal(self):
        # Modes share components -> offdiagonal mass terms
        basis = [
            [[1.0, 1.0, 0.0]],  # mode 0
            [[1.0, -1.0, 0.0]],  # mode 1
        ]
        masses = [100.0]
        M = modal.mass_gram(basis, masses)
        # M[0][0] = 100 * (1*1 + 1*1 + 0*0) = 200
        # M[1][1] = 100 * (1*1 + (-1)*(-1) + 0*0) = 200
        # M[0][1] = M[1][0] = 100 * (1*1 + 1*(-1) + 0*0) = 0
        self.assertAlmostEqual(M[0][0], 200.0)
        self.assertAlmostEqual(M[1][1], 200.0)
        self.assertAlmostEqual(M[0][1], 0.0)

    def test_mixed_components_coupling(self):
        # Modes with all components -> full coupling
        basis = [
            [[1.0, 0.5, 0.25]],  # mode 0
            [[0.5, 1.0, 0.5]],  # mode 1
        ]
        masses = [100.0]
        M = modal.mass_gram(basis, masses)
        # M[0][0] = 100 * (1 + 0.25 + 0.0625) = 131.25
        # M[1][1] = 100 * (0.25 + 1 + 0.25) = 150
        # M[0][1] = M[1][0] = 100 * (0.5 + 0.5 + 0.125) = 112.5
        self.assertAlmostEqual(M[0][0], 131.25)
        self.assertAlmostEqual(M[1][1], 150.0)
        self.assertAlmostEqual(M[0][1], 112.5)
        self.assertAlmostEqual(M[1][0], 112.5)

    def test_multiple_points_coupling(self):
        # Two points with different masses and mode shapes
        basis = [
            [[1.0, 0.0, 0.0], [0.0, 0.0, 0.0]],  # mode 0
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],  # mode 1
        ]
        masses = [40.0, 60.0]
        M = modal.mass_gram(basis, masses)
        # M[0][0] = 40*1 + 60*0 = 40
        # M[1][1] = 40*0 + 60*1 = 60
        # M[0][1] = M[1][0] = 40*0 + 60*0 = 0
        self.assertAlmostEqual(M[0][0], 40.0)
        self.assertAlmostEqual(M[1][1], 60.0)
        self.assertAlmostEqual(M[0][1], 0.0)

    def test_nonmutation(self):
        basis = [[[1.0, 0.0, 0.0]]]
        masses = [100.0]
        masses_orig = masses.copy()
        M = modal.mass_gram(basis, masses)
        self.assertEqual(masses, masses_orig)


class RescalingTests(unittest.TestCase):
    def test_column_rescaling_invariance(self):
        """Test that scaling columns of H with inverse q scaling leaves physical motion unchanged."""
        # Original basis: H[i][p][k] - mode i at point p in direction k
        # For a single point with 2 modes, each mode has 3 components
        basis1 = [
            [[1.0, 0.0, 0.0]],  # Mode 0: x direction
            [[0.0, 1.0, 0.0]],  # Mode 1: y direction
        ]
        q1 = [2.0, 3.0]
        u1 = modal.displacements(basis1, q1)
        # u = [2*1 + 3*0, 2*0 + 3*1, 2*0 + 3*0] = [2, 3, 0]

        # Rescale: H'[i][p][k] = H[i][p][k] / s[k], q'[i] = q[i] * s[k] for component k
        # This keeps physical motion invariant: u' = H' q' = H q
        s = [2.0, 0.5, 1.0]  # scale factors for x, y, z
        basis2 = []
        for mode in basis1:
            new_mode = []
            for pt in mode:
                new_pt = [pt[k] / s[k] for k in range(3)]
                new_mode.append(new_pt)
            basis2.append(new_mode)
        # q'[0] = q[0] * s[0] = 2 * 2 = 4 (for x component)
        # q'[1] = q[1] * s[1] = 3 * 0.5 = 1.5 (for y component)
        q2 = [q1[i] * s[i] for i in range(len(q1))]

        u2 = modal.displacements(basis2, q2)
        # u' = [4*0.5 + 1.5*0, 4*0 + 1.5*2, 0] = [2, 3, 0]

        for k in range(3):
            self.assertAlmostEqual(u1[0][k], u2[0][k], places=10)

    def test_work_invariance_under_rescaling(self):
        """Test that virtual work is invariant under column rescaling."""
        basis1 = [
            [[1.0, 0.0, 0.0]],  # Mode 0: x direction
            [[0.0, 1.0, 0.0]],  # Mode 1: y direction
        ]
        q1 = [2.0, 3.0]
        forces = [[10.0, 20.0, 30.0]]  # f = [10, 20, 30]

        u1 = modal.displacements(basis1, q1)
        # u = [2*1 + 3*0, 2*0 + 3*1, 0] = [2, 3, 0]
        work1 = sum(u1[0][k] * forces[0][k] for k in range(3))
        # work = 2*10 + 3*20 + 0*30 = 20 + 60 = 80

        s = [2.0, 0.5, 1.0]
        basis2 = []
        for mode in basis1:
            new_mode = []
            for pt in mode:
                new_pt = [pt[k] / s[k] for k in range(3)]
                new_mode.append(new_pt)
            basis2.append(new_mode)
        q2 = [q1[i] * s[i] for i in range(len(q1))]

        u2 = modal.displacements(basis2, q2)
        work2 = sum(u2[0][k] * forces[0][k] for k in range(3))

        self.assertAlmostEqual(work1, work2, places=10)


class ZeroBasisTests(unittest.TestCase):
    def test_empty_basis_rejected(self):
        with self.assertRaises(ValueError):
            modal.displacements([], [0.0])

    def test_empty_mode_rejected(self):
        with self.assertRaises(ValueError):
            modal.displacements([[]], [])

    def test_empty_point_rejected(self):
        with self.assertRaises(ValueError):
            modal.displacements([[[]]], [0.0])

    def test_zero_point_mass_rejected(self):
        basis = [[[1.0, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.mass_gram(basis, [0.0])

    def test_negative_point_mass_rejected(self):
        basis = [[[1.0, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.mass_gram(basis, [-1.0])

    def test_zero_q_with_valid_basis(self):
        """Zero modal coordinates with valid basis should work."""
        basis = [[[1.0, 0.0, 0.0]]]
        u = modal.displacements(basis, [0.0])
        self.assertAlmostEqual(u[0][0], 0.0)


class RaggedBasisTests(unittest.TestCase):
    def test_ragged_basis_rejected(self):
        basis = [
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[0.0, 0.0, 1.0]],  # Only one point
        ]
        with self.assertRaises(ValueError):
            modal.displacements(basis, [1.0, 2.0])

    def test_ragged_forces_rejected(self):
        basis = [[[1.0, 0.0, 0.0]]]
        forces = [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]  # Two points, need one
        with self.assertRaises(ValueError):
            modal.generalized_forces(basis, forces)

    def test_ragged_masses_rejected(self):
        basis = [[[1.0, 0.0, 0.0]]]
        masses = [100.0, 200.0]  # Two masses, need one
        with self.assertRaises(ValueError):
            modal.mass_gram(basis, masses)


class NonfiniteTests(unittest.TestCase):
    def test_nan_in_basis_rejected(self):
        basis = [[[math.nan, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.displacements(basis, [1.0])

    def test_inf_in_basis_rejected(self):
        basis = [[[math.inf, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.displacements(basis, [1.0])

    def test_nan_in_q_rejected(self):
        basis = [[[1.0, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.displacements(basis, [math.nan])

    def test_nan_in_forces_rejected(self):
        basis = [[[1.0, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.generalized_forces(basis, [[math.nan, 0.0, 0.0]])

    def test_nan_in_masses_rejected(self):
        basis = [[[1.0, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.mass_gram(basis, [math.nan])

    def test_inf_in_masses_rejected(self):
        basis = [[[1.0, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.mass_gram(basis, [math.inf])


class DimensionMismatchTests(unittest.TestCase):
    def test_q_length_mismatch(self):
        basis = [[[1.0, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.displacements(basis, [1.0, 2.0])  # 2 q's, need 1

    def test_forces_length_mismatch(self):
        basis = [[[1.0, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.generalized_forces(basis, [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])  # 2 forces, need 1

    def test_masses_length_mismatch(self):
        basis = [[[1.0, 0.0, 0.0]]]
        with self.assertRaises(ValueError):
            modal.mass_gram(basis, [100.0, 200.0])  # 2 masses, need 1


class SIConventionsTests(unittest.TestCase):
    def test_displacements_in_meters(self):
        """Physical displacements returned in meters (SI)."""
        basis = [[[1.0, 0.0, 0.0]]]
        # q in meters (modal coordinate for physical translation)
        q = [0.01]  # 1 cm
        u = modal.displacements(basis, q)
        self.assertAlmostEqual(u[0][0], 0.01)

    def test_forces_in_newtons(self):
        """Generalized forces returned in N (SI)."""
        basis = [[[1.0, 0.0, 0.0]]]
        forces = [[10.0, 0.0, 0.0]]  # 10 N
        Q = modal.generalized_forces(basis, forces)
        self.assertAlmostEqual(Q[0], 10.0)

    def test_mass_in_grams(self):
        """Modal mass matrix returned in grams (modal mass convention)."""
        basis = [[[1.0, 0.0, 0.0]]]
        masses = [100.0]  # 100 grams
        M = modal.mass_gram(basis, masses)
        self.assertAlmostEqual(M[0][0], 100.0)


class LargeBasisTests(unittest.TestCase):
    def test_10_modes_5_points(self):
        """Verify computation scales correctly."""
        nmodes, npts = 10, 5
        import random
        random.seed(123)
        basis = []
        for _ in range(nmodes):
            mode = []
            for _ in range(npts):
                pt = [random.uniform(-1, 1) for _ in range(3)]
                mode.append(pt)
            basis.append(mode)
        q = [random.uniform(-1, 1) for _ in range(nmodes)]
        forces = [[random.uniform(-5, 5) for _ in range(3)] for _ in range(npts)]
        masses = [random.uniform(10, 100) for _ in range(npts)]

        u = modal.displacements(basis, q)
        self.assertEqual(len(u), npts)
        self.assertEqual(len(u[0]), 3)

        Q = modal.generalized_forces(basis, forces)
        self.assertEqual(len(Q), nmodes)

        M = modal.mass_gram(basis, masses)
        self.assertEqual(len(M), nmodes)
        self.assertEqual(len(M[0]), nmodes)

        # Verify symmetry
        for i in range(nmodes):
            for j in range(nmodes):
                self.assertAlmostEqual(M[i][j], M[j][i])


if __name__ == "__main__":
    unittest.main()
