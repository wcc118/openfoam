"""Explicit imperial/SI display and input boundaries; solver values remain SI.

Units: in/ft for length, lbf for force, lbf_in for moment or work, kn for speed.
Accept finite real scalars, numeric lists/tuples and numeric NumPy arrays.
Return a float for scalars and an owned array otherwise. Never infer units.
"""
import numpy as np

SI_PER_IMPERIAL = {'in': .0254, 'ft': .3048, 'lbf': 4.4482216152605,
                   'lbf_in': 4.4482216152605*.0254, 'kn': 1852/3600}
SUPPORTED_UNITS = set(SI_PER_IMPERIAL)


def _convert(value, unit, inverse):
    if not isinstance(unit, str) or unit not in SI_PER_IMPERIAL:
        raise ValueError(f'Unsupported unit: {unit!r}')
    def validate(v):
        if isinstance(v, np.ndarray):
            if v.dtype.kind not in 'iuf':
                raise ValueError('require real numeric arrays, not bool/complex/string')
        elif isinstance(v, (list, tuple)):
            for item in v:validate(item)
        elif isinstance(v, (bool, np.bool_)) or not isinstance(v, (int,float,np.integer,np.floating)):
            raise ValueError('require real numbers, not bool/complex/string')
    validate(value)
    try:
        a=np.array(value,dtype=float,copy=True)
        if not np.isfinite(a).all():raise ValueError('require finite values')
        with np.errstate(over='ignore',invalid='ignore'):
            result=a/SI_PER_IMPERIAL[unit] if inverse else a*SI_PER_IMPERIAL[unit]
        if not np.isfinite(result).all():raise ValueError('conversion overflow')
    except (TypeError,OverflowError) as error:
        raise ValueError('require finite real values') from error
    return float(result) if result.ndim==0 else result


def to_imperial(value, unit):
    """Convert SI values to explicitly named display units."""
    return _convert(value,unit,True)


def to_si(value, unit):
    """Convert explicitly named input units to SI."""
    return _convert(value,unit,False)
