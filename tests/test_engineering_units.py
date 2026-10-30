"""Tests for engineering_units module: imperial/SI conversion boundary only."""
import copy
import unittest

import numpy as np
from scripts.engineering_units import SI_PER_IMPERIAL, to_imperial, to_si


class ImperialReferenceTests(unittest.TestCase):
    """Independent known reference conversions."""

    def test_inch_to_meter_reference(self):
        """1 inch = 0.0254 m exactly (definition)."""
        # to_si: 1 inch -> 0.0254 m
        self.assertAlmostEqual(to_si(1.0, 'in'), 0.0254, places=15)
        # to_imperial: 0.0254 m -> 1 inch
        self.assertAlmostEqual(to_imperial(0.0254, 'in'), 1.0, places=15)

    def test_foot_to_meter_reference(self):
        """1 foot = 0.3048 m exactly (definition)."""
        self.assertAlmostEqual(to_si(1.0, 'ft'), 0.3048, places=15)
        self.assertAlmostEqual(to_imperial(0.3048, 'ft'), 1.0, places=15)

    def test_lbf_to_newton_reference(self):
        """1 lbf = 4.4482216152605 N exactly (NIST definition)."""
        expected = 4.4482216152605
        self.assertAlmostEqual(to_si(1.0, 'lbf'), expected, places=15)
        self.assertAlmostEqual(to_imperial(expected, 'lbf'), 1.0, places=15)

    def test_lbf_in_to_n_m_reference(self):
        """1 lbf·in = 4.4482216152605 * 0.0254 N·m."""
        expected = 4.4482216152605 * 0.0254
        self.assertAlmostEqual(to_si(1.0, 'lbf_in'), expected, places=15)
        self.assertAlmostEqual(to_imperial(expected, 'lbf_in'), 1.0, places=15)

    def test_knot_to_m_per_s_reference(self):
        """1 kn = 1852/3600 m/s exactly (nautical mile definition)."""
        expected = 1852 / 3600
        self.assertAlmostEqual(to_si(1.0, 'kn'), expected, places=15)
        self.assertAlmostEqual(to_imperial(expected, 'kn'), 1.0, places=15)


class RoundtripTests(unittest.TestCase):
    """Signed vector roundtrip and owned output."""

    def test_positive_scalar_roundtrip(self):
        """Roundtrip preserves value for positive scalars."""
        for unit in SI_PER_IMPERIAL.keys():
            for val in [0.1, 1.0, 10.5, 100.0]:
                si_val = to_si(val, unit)
                back = to_imperial(si_val, unit)
                self.assertAlmostEqual(back, val, places=14,
                                       msg=f"Failed roundtrip for {unit}")

    def test_negative_scalar_roundtrip(self):
        """Roundtrip preserves value for negative scalars."""
        for unit in SI_PER_IMPERIAL.keys():
            for val in [-0.1, -1.0, -10.5]:
                si_val = to_si(val, unit)
                back = to_imperial(si_val, unit)
                self.assertAlmostEqual(back, val, places=14,
                                       msg=f"Failed roundtrip for {unit}")

    def test_signed_vector_roundtrip(self):
        """Roundtrip preserves vector values."""
        for unit in SI_PER_IMPERIAL.keys():
            val = [1.0, -2.0, 3.5, -4.5]
            si_val = to_si(val, unit)
            back = to_imperial(si_val, unit)
            self.assertIsInstance(back, np.ndarray)
            np.testing.assert_allclose(back, val, atol=1e-14)

    def test_owned_output_copy(self):
        """Output arrays are copies, not originals."""
        for unit in SI_PER_IMPERIAL.keys():
            val = [1.0, 2.0, 3.0]
            original = copy.deepcopy(val)
            result = to_si(val, unit)
            result[0] = 999.0
            # Original should be unchanged
            self.assertEqual(val, original)

    def test_numpy_input_owned_output(self):
        """NumPy array input yields owned ndarray output."""
        for unit in SI_PER_IMPERIAL.keys():
            val = np.array([1.0, 2.0, 3.0])
            original = val.copy()
            result = to_si(val, unit)
            # Result should be ndarray
            self.assertIsInstance(result, np.ndarray)
            # Result should be a copy
            self.assertIsNot(result, val)
            # Original unchanged
            np.testing.assert_array_equal(val, original)

    def test_scalar_preserved_as_float(self):
        """Scalar input yields float output, not ndarray."""
        for unit in SI_PER_IMPERIAL.keys():
            val = 1.5
            result = to_si(val, unit)
            self.assertIsInstance(result, float)
            self.assertNotIsInstance(result, np.floating)
            # Float has no shape, that's the point
            self.assertFalse(hasattr(result, 'shape'))

    def test_nested_list_handling(self):
        """Nested lists are converted correctly."""
        val = [[1.0, 2.0], [3.0, 4.0]]
        result = to_si(val, 'in')
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, (2, 2))
        expected = np.array(val) * 0.0254
        np.testing.assert_allclose(result, expected, atol=1e-15)


class InvalidValueRejectionTests(unittest.TestCase):
    """Invalid values and unit names rejected with ValueError."""

    def test_reject_boolean_values(self):
        """Boolean values are rejected."""
        for unit in SI_PER_IMPERIAL.keys():
            with self.assertRaises(ValueError):
                to_si(True, unit)
            with self.assertRaises(ValueError):
                to_imperial(False, unit)

    def test_reject_complex_numbers(self):
        """Complex numbers are rejected."""
        for unit in SI_PER_IMPERIAL.keys():
            with self.assertRaises(ValueError):
                to_si(1+2j, unit)
            with self.assertRaises(ValueError):
                to_imperial(3-4j, unit)

    def test_reject_complex_numbers_in_list(self):
        """Lists containing complex numbers are rejected."""
        for unit in SI_PER_IMPERIAL.keys():
            with self.assertRaises(ValueError):
                to_si([1.0, 2+3j], unit)
            with self.assertRaises(ValueError):
                to_imperial([1.0, 2.0, 3+4j], unit)

    def test_reject_infinity(self):
        """Infinity values are rejected."""
        for unit in SI_PER_IMPERIAL.keys():
            with self.assertRaises(ValueError):
                to_si(float('inf'), unit)
            with self.assertRaises(ValueError):
                to_imperial(float('-inf'), unit)

    def test_reject_nan(self):
        """NaN values are rejected."""
        for unit in SI_PER_IMPERIAL.keys():
            with self.assertRaises(ValueError):
                to_si(float('nan'), unit)
            with self.assertRaises(ValueError):
                to_imperial(float('nan'), unit)

    def test_reject_infinity_in_array(self):
        """Arrays containing infinity are rejected."""
        for unit in SI_PER_IMPERIAL.keys():
            with self.assertRaises(ValueError):
                to_si(np.array([1.0, np.inf]), unit)
            with self.assertRaises(ValueError):
                to_imperial(np.array([1.0, -np.inf]), unit)

    def test_reject_nan_in_array(self):
        """Arrays containing NaN are rejected."""
        for unit in SI_PER_IMPERIAL.keys():
            with self.assertRaises(ValueError):
                to_si(np.array([1.0, np.nan]), unit)
            with self.assertRaises(ValueError):
                to_imperial(np.array([1.0, np.nan]), unit)

    def test_reject_nonnumeric_string(self):
        """String values are rejected."""
        for unit in SI_PER_IMPERIAL.keys():
            with self.assertRaises(ValueError):
                to_si("1.0", unit)
            with self.assertRaises(ValueError):
                to_imperial("2.0", unit)

    def test_reject_nonfinite_nested(self):
        """Nested structures with nonfinite values rejected."""
        for unit in SI_PER_IMPERIAL.keys():
            with self.assertRaises(ValueError):
                to_si([[1.0, 2.0], [3.0, float('inf')]], unit)
            with self.assertRaises(ValueError):
                to_imperial([[1.0, 2.0], [3.0, float('nan')]], unit)


class InvalidUnitRejectionTests(unittest.TestCase):
    """Unsupported unit names rejected with ValueError."""

    def test_reject_unknown_unit(self):
        """Unknown unit names raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            to_si(1.0, 'unknown')
        self.assertIn('unknown', str(ctx.exception).lower())

        with self.assertRaises(ValueError) as ctx:
            to_imperial(1.0, 'meters')
        self.assertIn('meters', str(ctx.exception).lower())

    def test_reject_empty_unit(self):
        """Empty string unit rejected."""
        with self.assertRaises(ValueError):
            to_si(1.0, '')

    def test_reject_none_unit(self):
        """None unit rejected."""
        with self.assertRaises(ValueError):
            to_si(1.0, None)

    def test_reject_numeric_unit(self):
        """Numeric unit rejected."""
        with self.assertRaises(ValueError):
            to_si(1.0, 123)


class NumpyArrayTests(unittest.TestCase):
    """NumPy array-specific behavior."""

    def test_numpy_input_returns_numpy_output(self):
        """NumPy input yields ndarray output."""
        for unit in SI_PER_IMPERIAL.keys():
            val = np.array([1.0, 2.0, 3.0])
            result_si = to_si(val, unit)
            result_imperial = to_imperial(result_si, unit)
            self.assertIsInstance(result_si, np.ndarray)
            self.assertIsInstance(result_imperial, np.ndarray)

    def test_numpy_2d_array(self):
        """2D numpy arrays handled correctly."""
        val = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = to_si(val, 'ft')
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, (2, 2))
        expected = val * 0.3048
        np.testing.assert_allclose(result, expected, atol=1e-15)

    def test_numpy_scalar_0d(self):
        """0D numpy arrays (scalars) handled correctly."""
        val = np.array(1.5)
        result = to_si(val, 'in')
        # 0D array should become float
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, 1.5 * 0.0254, places=15)

    def test_numpy_integer_array(self):
        """Integer numpy arrays converted correctly."""
        val = np.array([1, 2, 3], dtype=int)
        result = to_si(val, 'lbf')
        self.assertIsInstance(result, np.ndarray)
        np.testing.assert_allclose(result, [4.4482216152605, 8.896443230521, 13.3446648457815], atol=1e-15)

    def test_numpy_output_not_writeable_input(self):
        """Output is writable copy even if input was read-only."""
        val = np.array([1.0, 2.0, 3.0])
        val.flags.writeable = False
        result = to_si(val, 'kn')
        self.assertTrue(result.flags.writeable)


class ConversionFactorTests(unittest.TestCase):
    """SI_PER_IMPERIAL mapping values."""

    def test_all_units_have_factors(self):
        """All supported units have conversion factors."""
        for unit in ['in', 'ft', 'lbf', 'lbf_in', 'kn']:
            self.assertIn(unit, SI_PER_IMPERIAL)
            factor = SI_PER_IMPERIAL[unit]
            self.assertIsInstance(factor, (int, float))
            self.assertGreater(factor, 0)

    def test_inch_factor(self):
        """inch factor is exactly 0.0254."""
        self.assertAlmostEqual(SI_PER_IMPERIAL['in'], 0.0254, places=15)

    def test_foot_factor(self):
        """foot factor is exactly 0.3048."""
        self.assertAlmostEqual(SI_PER_IMPERIAL['ft'], 0.3048, places=15)

    def test_lbf_factor(self):
        """lbf factor is exactly 4.4482216152605."""
        self.assertAlmostEqual(SI_PER_IMPERIAL['lbf'], 4.4482216152605, places=15)

    def test_lbf_in_factor(self):
        """lbf_in factor is lbf * in."""
        expected = SI_PER_IMPERIAL['lbf'] * SI_PER_IMPERIAL['in']
        self.assertAlmostEqual(SI_PER_IMPERIAL['lbf_in'], expected, places=15)

    def test_knot_factor(self):
        """kn factor is 1852/3600."""
        expected = 1852 / 3600
        self.assertAlmostEqual(SI_PER_IMPERIAL['kn'], expected, places=15)


class EdgeCaseTests(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def test_zero_value(self):
        """Zero values handled correctly."""
        for unit in SI_PER_IMPERIAL.keys():
            self.assertEqual(to_si(0.0, unit), 0.0)
            self.assertEqual(to_imperial(0.0, unit), 0.0)
            self.assertEqual(to_si(0, unit), 0.0)

    def test_very_small_values(self):
        """Very small values preserved."""
        for unit in SI_PER_IMPERIAL.keys():
            small = 1e-10
            result = to_si(small, unit)
            self.assertAlmostEqual(result, small * SI_PER_IMPERIAL[unit], places=20)

    def test_very_large_values(self):
        """Very large values preserved."""
        for unit in SI_PER_IMPERIAL.keys():
            large = 1e10
            result = to_si(large, unit)
            self.assertAlmostEqual(result, large * SI_PER_IMPERIAL[unit], places=5)

    def test_single_element_list(self):
        """Single element list handled as array."""
        val = [1.0]
        result = to_si(val, 'in')
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, (1,))
        self.assertAlmostEqual(result[0], 0.0254, places=15)

    def test_numpy_preserves_type(self):
        """NumPy float types preserved in conversion."""
        for dtype in [np.float32, np.float64]:
            val = np.array([1.0, 2.0], dtype=dtype)
            result = to_si(val, 'ft')
            self.assertEqual(result.dtype, float)


class CoercionRegressionTests(unittest.TestCase):
    def test_mixed_nested_and_numpy_nonreal_rejected(self):
        for value in ([1, True], [[1], ['2']], np.array([True]), np.array([1+2j]), np.complex128(1+2j)):
            for conversion in (to_si, to_imperial):
                with self.subTest(value=repr(value), conversion=conversion.__name__):
                    with self.assertRaises(ValueError): conversion(value, 'in')

    def test_overflow_rejected(self):
        with self.assertRaises(ValueError): to_imperial(1e308, 'in')
        with self.assertRaises(ValueError): to_si(10**400, 'in')


if __name__ == '__main__':
    unittest.main()
