#!/usr/bin/env python3
"""Validate and embed a native 3D flow package in a standalone vtk.js viewer."""
import argparse
import json
import math
from pathlib import Path

ASSETS = Path(__file__).with_name('flow_3d')


def numbers(values, name, length=None, minimum=None, integer=False):
    if not isinstance(values, list) or not values or (length is not None and len(values) != length):
        raise ValueError(f'{name}: invalid array length')
    for v in values:
        if type(v) not in (int, float) or not math.isfinite(v):
            raise ValueError(f'{name}: expected finite numbers')
        if integer and type(v) is not int:
            raise ValueError(f'{name}: expected integers')
        if minimum is not None and v < minimum:
            raise ValueError(f'{name}: value below minimum')
    return values


def geometry(obj, name, cell_kind, scalar_location=None):
    pts = numbers(obj['points'], f'{name}.points')
    if len(pts) % 3:
        raise ValueError(f'{name}: points must have three components')
    cells = numbers(obj[cell_kind], f'{name}.{cell_kind}', integer=True, minimum=0)
    pos, count = 0, 0
    while pos < len(cells):
        n = cells[pos]
        if n < 2 or (cell_kind == 'polys' and n != 3) or pos + n >= len(cells):
            raise ValueError(f'{name}: malformed cell connectivity')
        if any(i >= len(pts) // 3 for i in cells[pos + 1:pos + n + 1]):
            raise ValueError(f'{name}: cell index out of range')
        pos += n + 1
        count += 1
    if scalar_location:
        numbers(obj['speed'], f'{name}.speed', len(pts) // 3 if scalar_location == 'point' else count, 0)


def validate(data):
    try:
        if type(data['schema_version']) is not int or data['schema_version'] != 1 or data['kind'] != 'native-flow-3d':
            raise ValueError('Unsupported schema')
        meta = data['metadata']
        if not isinstance(meta['title'], str) or not meta['title'].strip():
            raise ValueError('metadata.title is required')
        numbers([meta['alpha_deg']], 'alpha_deg')
        numbers([meta['steady_iteration']], 'steady_iteration', integer=True, minimum=0)
        if not isinstance(meta['provenance'], dict) or not meta['provenance']:
            raise ValueError('provenance must be a nonempty object')
        if not isinstance(meta['limitations'], list) or not meta['limitations'] or any(not isinstance(s, str) or not s.strip() for s in meta['limitations']):
            raise ValueError('limitations must be nonempty strings')
        geometry(data['wing'], 'wing', 'polys')
        geometry(data['paths'], 'paths', 'lines', 'point')
        geometry(data['vortex'], 'vortex', 'polys', 'cell')
        v = data['volume']
        dims = numbers(v['dimensions'], 'dimensions', 3, 2, True)
        numbers(v['origin'], 'origin', 3)
        numbers(v['spacing'], 'spacing', 3)
        if any(s <= 0 for s in v['spacing']):
            raise ValueError('spacing must be positive')
        values = numbers(v['speed'], 'volume.speed', math.prod(dims))
        if any(s < 0 and s != -1 for s in values):
            raise ValueError('Only -1 is a valid missing-data sentinel')
        # Reject non-finite values anywhere, including provenance.
        json.dumps(data, allow_nan=False)
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError(f'Malformed flow package: {exc}') from exc
    return data


def build_html(data):
    validate(data)
    payload = json.dumps(data, separators=(',', ':'), allow_nan=False)
    for raw, escaped in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        payload = payload.replace(raw, escaped)
    template = (ASSETS / 'viewer.html').read_text()
    vendor = (ASSETS / 'vendor/vtk-35.5.1.js').read_text()
    viewer = (ASSETS / 'viewer.js').read_text()
    # Inline JS is trusted pinned source, but HTML still recognizes closing tags.
    vendor = vendor.replace('</script', '<\\/script')
    viewer = viewer.replace('</script', '<\\/script')
    return template.replace('/*__VENDOR__*/', vendor).replace('/*__VIEWER__*/', viewer).replace('/*__DATA__*/', payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        html = build_html(json.loads(args.input.read_text()))
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(args.output)


if __name__ == '__main__':
    main()
