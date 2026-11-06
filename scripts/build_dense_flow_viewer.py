#!/usr/bin/env python3
"""Create an offline 3D viewer of exported steady CFD slices."""
import argparse
import hashlib
import json
import math
from pathlib import Path
try:
    from build_angle_comparison import validate as validate_angles, number, sequence, derived_ranges as angle_ranges
except ModuleNotFoundError:
    from scripts.build_angle_comparison import validate as validate_angles, number, sequence, derived_ranges as angle_ranges


def validate(data):
    validate_angles(data)
    try:
        seen = set()
        for s in sequence(data['slices'], 'slices'):
            for key in ('id', 'label'):
                if not isinstance(s[key], str) or not s[key].strip():
                    raise ValueError(f'slice.{key} must be nonblank text')
            if s['id'] in seen:
                raise ValueError('duplicate slice id')
            seen.add(s['id'])
            axes = [s[k] for k in ('normal_axis', 'u_axis', 'v_axis')]
            if any(type(a) is not int for a in axes) or sorted(axes) != [0, 1, 2]:
                raise ValueError('slice axes must be a permutation of 0,1,2')
            number(s['position_m'], 'slice position')
            us, vs = s['u_values'], s['v_values']
            for values in (us, vs):
                sequence(values, 'slice coordinates')
                if len(values) < 2:
                    raise ValueError('slice requires at least two coordinates per axis')
                for v in values:
                    number(v, 'slice coordinate')
                if any(a >= b for a, b in zip(values, values[1:])):
                    raise ValueError('slice coordinates must strictly increase')
            indices = sequence(s['indices'], 'slice indices')
            if len(indices) != len(us) * len(vs):
                raise ValueError('slice index count mismatch')
            used = set()
            for j, idx in enumerate(indices):
                if type(idx) is not int or not -1 <= idx < len(data['samples']['points']):
                    raise ValueError('invalid slice index')
                if idx == -1:
                    continue
                if idx in used:
                    raise ValueError('duplicate slice index')
                used.add(idx)
                p = data['samples']['points'][idx]
                expected = [s['position_m'], us[j % len(us)], vs[j // len(us)]]
                if any(abs(p[axis] - value) > 1e-8 for axis, value in zip(axes, expected)):
                    raise ValueError('slice coordinate mismatch')
        for c in data['cases']:
            for u in c['U']:
                number(math.hypot(u[1]-c['freestream_velocity_m_s'][1], u[2]-c['freestream_velocity_m_s'][2]), 'derived crossflow')
    except (KeyError, TypeError, IndexError, OverflowError) as exc:
        raise ValueError(f'malformed slices: {exc}') from exc
    return data


def derived_ranges(data):
    ranges = angle_ranges(data)
    values = [math.hypot(u[1]-c['freestream_velocity_m_s'][1], u[2]-c['freestream_velocity_m_s'][2]) for c in data['cases'] for u in c['U']]
    ranges['crossflow'] = [0, max(values)]
    return ranges


def build_html(data):
    validate(data)
    encoded = json.dumps(dict(data, color_ranges=derived_ranges(data)), separators=(',', ':'), allow_nan=False)
    for a, b in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        encoded = encoded.replace(a, b)
    assets = Path(__file__).with_name('dense_flow')
    return (assets/'viewer.html').read_text().replace('/*__VIEWER__*/', (assets/'viewer.js').read_text()).replace('/*__DATA__*/', encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        def reject(value):
            raise ValueError(f'nonfinite JSON {value}')
        data = json.loads(raw, parse_constant=reject)
        html = build_html(data)
        with args.output.open('x') as f:
            f.write(html)
        print(json.dumps({'input_sha256': hashlib.sha256(raw).hexdigest(), 'cases': len(data['cases']), 'slices': len(data['slices'])}))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Dense viewer build failed: {exc}\n')

if __name__ == '__main__':
    main()
