#!/usr/bin/env python3
"""Build an offline diagnostic viewer from independently simulated steady angle-of-attack cases."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def number(x, name):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f'{name}: expected finite number')
    return x


def sequence(x, name, nonempty=True):
    if not isinstance(x, list) or (nonempty and not x):
        raise ValueError(f'{name}: expected {"nonempty " if nonempty else ""}array')
    return x


def vectors(values, name):
    for i, v in enumerate(sequence(values, name)):
        if not isinstance(v, list) or len(v) != 3:
            raise ValueError(f'{name}[{i}]: expected three components')
        for x in v:
            number(x, name)


def validate(data):
    try:
        if data['schema_version'] != 1 or isinstance(data['schema_version'], bool):
            raise ValueError('unsupported schema_version')
        if data['kind'] != 'steady_angle_cases':
            raise ValueError("only kind='steady_angle_cases' is supported")
        ref = data['reference']
        if number(ref['speed_m_s'], 'speed_m_s') <= 0:
            raise ValueError('reference.speed_m_s must be positive')
        if number(ref['chord_m'], 'chord_m') <= 0:
            raise ValueError('reference.chord_m must be positive')
        number(ref['reference_pressure_kinematic'], 'reference.reference_pressure_kinematic')
        number(ref['dynamic_pressure_kinematic'], 'reference.dynamic_pressure_kinematic')
        if ref['dynamic_pressure_kinematic'] <= 0:
            raise ValueError('reference.dynamic_pressure_kinematic must be positive')
        wing = data['wing']
        vectors(wing['points'], 'wing.points')
        for tri in sequence(wing['triangles'], 'triangles'):
            if not isinstance(tri, list) or len(tri) != 3 or len(set(tri)) != 3:
                raise ValueError('triangle must contain three distinct indices')
            if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= len(wing['points']) for i in tri):
                raise ValueError('triangle index out of bounds or not an integer')
        samples = data['samples']
        vectors(samples['points'], 'samples.points')
        n = len(samples['points'])
        if len(sequence(samples['groups'], 'groups')) != n or any(g not in ['midspan', 'tip', 'wake'] for g in samples['groups']):
            raise ValueError('sample groups must match points and be midspan/tip/wake')
        cases = sequence(data['cases'], 'cases', nonempty=True)
        seen_ids, seen_alphas = set(), set()
        for c in cases:
            if not isinstance(c['id'], str) or not c['id'].strip():
                raise ValueError('case.id must be a nonempty string')
            if c['id'] in seen_ids:
                raise ValueError(f'duplicate case.id: {c["id"]}')
            seen_ids.add(c['id'])
            alpha = number(c['alpha_deg'], 'case.alpha_deg')
            if alpha in seen_alphas:
                raise ValueError(f'duplicate case.alpha_deg: {alpha}')
            seen_alphas.add(alpha)
            iter_count = c['steady_iteration']
            if isinstance(iter_count, bool) or not isinstance(iter_count, int):
                raise ValueError(f"case '{c['id']}': steady_iteration must be a positive integer, not bool")
            if iter_count <= 0:
                raise ValueError(f"case '{c['id']}': steady_iteration must be positive")
            for k in ['solver', 'source_revision']:
                if not isinstance(c[k], str) or not c[k].strip():
                    raise ValueError(f"case '{c['id']}': {k} must be a nonempty string")
            if not isinstance(c['mesh_sha256'], str) or len(c['mesh_sha256']) != 64 or not all(ch in '0123456789abcdefABCDEF' for ch in c['mesh_sha256']):
                raise ValueError(f"case '{c['id']}': mesh_sha256 must be a 64-hex string")
            if not isinstance(c['field_sha256'], str) or len(c['field_sha256']) != 64 or not all(ch in '0123456789abcdefABCDEF' for ch in c['field_sha256']):
                raise ValueError(f"case '{c['id']}': field_sha256 must be a 64-hex string")
            if c['status'] != 'diagnostic_only':
                raise ValueError("case.status must be 'diagnostic_only'")
            if not isinstance(c['limitations'], list) or not c['limitations'] or any(not isinstance(v, str) or not v.strip() for v in c['limitations']):
                raise ValueError("case.limitations must be a nonempty array of nonempty strings")
            if not isinstance(c['freestream_velocity_m_s'], list) or len(c['freestream_velocity_m_s']) != 3:
                raise ValueError(f"case '{c['id']}': freestream_velocity_m_s must be a length-3 array")
            v_inf = c['freestream_velocity_m_s']
            alpha_rad = math.radians(alpha)
            expected = [ref['speed_m_s'] * math.cos(alpha_rad), 0, ref['speed_m_s'] * math.sin(alpha_rad)]
            for i, (actual, exp) in enumerate(zip(v_inf, expected)):
                if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
                    raise ValueError(f"case '{c['id']}': freestream_velocity_m_s[{i}] must be a finite number")
                if abs(actual - exp) > 1e-8:
                    raise ValueError(f"case '{c['id']}': freestream_velocity_m_s[{i}] mismatch")
            u_vecs = c['U']
            if not isinstance(u_vecs, list) or len(u_vecs) != n:
                raise ValueError(f"case '{c['id']}': U must be a length-{n} array")
            for u in u_vecs:
                if not isinstance(u, list) or len(u) != 3:
                    raise ValueError(f"case '{c['id']}': U vector must be a length-3 array")
                for x in u:
                    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
                        raise ValueError(f"case '{c['id']}': U vector components must be finite numbers")
                number(math.hypot(*u), f"case '{c['id']}': derived speed")
            p_vals = c['p']
            if not isinstance(p_vals, list) or len(p_vals) != n:
                raise ValueError(f"case '{c['id']}': p must have length {n}")
            for p in p_vals:
                number((number(p, f"case '{c['id']}': p") - ref['reference_pressure_kinematic']) / ref['dynamic_pressure_kinematic'], f"case '{c['id']}': derived Cp")
        # All mesh_sha256 must be identical
        mesh_hashes = {c['mesh_sha256'].lower() for c in cases}
        if len(mesh_hashes) != 1:
            raise ValueError('all cases must share the same mesh_sha256')
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError(f'malformed steady-angle data: {exc}') from exc
    return data


def derived_ranges(data):
    cases = data['cases']
    speeds = []
    cp_vals = []
    for c in cases:
        for u in c['U']:
            speeds.append(math.hypot(*u))
        for p in c['p']:
            cp_vals.append((p - data['reference']['reference_pressure_kinematic']) / data['reference']['dynamic_pressure_kinematic'])
    return {'speed': [min(speeds), max(speeds)], 'cp': [min(cp_vals), max(cp_vals)]}


def build_html(data):
    validate(data)
    payload = dict(data, color_ranges=derived_ranges(data))
    encoded = json.dumps(payload, separators=(',', ':'), allow_nan=False)
    for a, b in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        encoded = encoded.replace(a, b)
    assets = Path(__file__).with_name('angle_comparison')
    page = (assets / 'viewer.html').read_text()
    script = (assets / 'viewer.js').read_text()
    return page.replace('/*__VIEWER__*/', script).replace('/*__DATA__*/', encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        def reject(value):
            raise ValueError(f'nonfinite JSON constant: {value}')
        data = json.loads(raw, parse_constant=reject)
        page = build_html(data)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(page)
        print(json.dumps({'output': str(args.output), 'input_sha256': hashlib.sha256(raw).hexdigest(), 'cases': len(data['cases'])}))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Angle comparison build failed: {exc}\n')


if __name__ == '__main__':
    main()
