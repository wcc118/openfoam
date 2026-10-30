"""Imperial/SI unit conversion for display/input boundary only.

This module provides conversion factors and functions to convert between SI
(International System of Units) and imperial measurement systems. All solver
inputs and internal calculations remain in SI units. This module is strictly
for converting values for human display or input in imperial units.

SI_PER_IMPERIAL defines the mapping from imperial unit names to their SI
equivalent values (multipliers to convert imperial to SI).

Functions:
  to_imperial(value, unit): Convert SI value to imperial units for display
  to_si(value, unit): Convert imperial value to SI for solver input

Supported units:
  'in': inches (0.0254 m)
  'ft': feet (0.3048 m)
  'lbf': pounds-force (4.4482216152605 N)
  'lbf_in': pound-force inches (0.11325421642761635 N m)
  'kn': knots (1852/3600 m/s)

Input validation:
  - Accepts finite real scalars and numeric lists/tuples (including nested)
  - Accepts numeric NumPy arrays
  - Preserves scalar as float, nonscalar as numpy ndarray copy
  - Rejects bool, complex, nonfinite, nonnumeric values with ValueError
  - Rejects unsupported unit names with ValueError
  - Never mutates caller arrays

No automatic unit inference is performed; unit names must be explicitly specified.
"""

import numpy as np


# Conversion factors: multiply imperial values by these to get SI
SI_PER_IMPERIAL = {
    'in': 0.0254,
    'ft': 0.3048,
    'lbf': 4.4482216152605,
    'lbf_in': 4.4482216152605 * 0.0254,
    'kn': 1852 / 3600,
}

# Valid unit names
SUPPORTED_UNITS = set(SI_PER_IMPERIAL.keys())


def _validate_unit(unit):
    """Validate unit name and return normalized form."""
    if not isinstance(unit, str) or unit not in SUPPORTED_UNITS:
        raise ValueError(f"Unsupported unit '{unit}'. Supported units: {sorted(SUPPORTED_UNITS)}")
    return unit


def _validate_and_convert_value(value, unit):
    """Validate value and convert to numpy array. Returns (is_scalar, result_array).

    Accepts finite real scalar and JSON-style numeric lists/tuples (including nested)
    and numeric NumPy arrays. Rejects bool, complex, nonfinite, nonnumeric values.
    Never mutates caller arrays.
    """
    # Reject booleans at top level (before int/float check)
    if isinstance(value, bool):
        raise ValueError(f"Value must be numeric, not boolean")

    # Reject strings at top level
    if isinstance(value, str):
        raise ValueError(f"Value must be numeric, not string")

    # Check if it's a finite numeric scalar
    if isinstance(value, (int, float, np.integer, np.floating)):
        # Check for inf/nan
        if isinstance(value, (float, np.floating)) and (np.isinf(value) or np.isnan(value)):
            raise ValueError(f"Value must be finite")
        # Scalar path
        return True, float(value)

    # Not a scalar - try to convert to numpy array
    try:
        arr = np.array(value, dtype=float, copy=True)
    except (ValueError, TypeError):
        raise ValueError(f"Value contains non-numeric data")

    # Check for bool type in numpy array
    if arr.dtype == bool:
        raise ValueError(f"Value contains boolean")

    # Check for complex
    if np.issubdtype(arr.dtype, np.complexfloating):
        raise ValueError(f"Value contains complex number")

    # Check for inf/nan
    if not np.isfinite(arr).all():
        raise ValueError(f"Value contains non-finite numeric")

    is_scalar = arr.shape == ()
    if is_scalar:
        return True, float(arr.item())
    else:
        return False, arr


def to_imperial(value, unit):
    """Convert SI value to imperial units for display.

    Args:
        value: SI value (scalar or array-like of finite numerics)
        unit: imperial unit name ('in', 'ft', 'lbf', 'lbf_in', 'kn')

    Returns:
        Imperial value as float for scalars, numpy ndarray for arrays.
        Arrays are copies, never the original.

    Raises:
        ValueError: If value contains invalid data or unit is unsupported.

    Examples:
        >>> to_imperial(0.0254, 'in')
        1.0
        >>> to_imperial(1.0, 'lbf')
        0.22499999999999998
        >>> to_imperial([0.0254, 0.3048], 'ft')
        array([0.08333333, 1.        ])
    """
    _validate_unit(unit)
    is_scalar, arr = _validate_and_convert_value(value, unit)
    result = arr / SI_PER_IMPERIAL[unit]
    return float(result) if is_scalar else result


def to_si(value, unit):
    """Convert imperial value to SI for solver input.

    Args:
        value: Imperial value (scalar or array-like of finite numerics)
        unit: imperial unit name ('in', 'ft', 'lbf', 'lbf_in', 'kn')

    Returns:
        SI value as float for scalars, numpy ndarray for arrays.
        Arrays are copies, never the original.

    Raises:
        ValueError: If value contains invalid data or unit is unsupported.

    Examples:
        >>> to_si(1.0, 'in')
        0.0254
        >>> to_si(1.0, 'lbf')
        4.4482216152605
        >>> to_si([1.0, 1.0], 'ft')
        array([0.0254 , 0.3048])
    """
    _validate_unit(unit)
    is_scalar, arr = _validate_and_convert_value(value, unit)
    result = arr * SI_PER_IMPERIAL[unit]
    return float(result) if is_scalar else result
