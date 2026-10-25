"""Summarize OpenFOAM mesh evidence from VTK surface files and checkMesh logs.

Parses OpenFOAM legacy ASCII VTK POLYDATA format with nSurfaceLayers field.
Produces bounded metrics for gate evaluation. No external dependencies.
"""

import argparse
import hashlib
import json
import re
import struct
import sys
import zlib


def parse_vtk_polydata(data: bytes, max_size: int = 64 * 1024 * 1024,
                       max_points: int = 1000000, max_polygons: int = 1000000):
    """Parse OpenFOAM legacy ASCII VTK POLYDATA with nSurfaceLayers field.

    Returns dict with points, polygons, nSurfaceLayers array, or raises ValueError.
    """
    if len(data) > max_size:
        raise ValueError(f"Input size {len(data)} exceeds {max_size} byte limit")

    text = data.decode('utf-8', errors='strict')
    lines = text.splitlines()
    idx = 0

    # Header: DataFile Version 2.0, title, ASCII/_binary, DATASET POLYDATA
    while idx < len(lines) and not lines[idx].strip().startswith('DATASET'):
        idx += 1
    if idx >= len(lines) or not lines[idx].strip().startswith('DATASET POLYDATA'):
        raise ValueError("Not a VTK POLYDATA file")
    idx += 1

    points = []
    polygons = []
    n_surface_layers = None

    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue

        if line.startswith('POINTS'):
            parts = line.split()
            if len(parts) != 3:
                raise ValueError(f"Invalid POINTS header: {line}")
            count = int(parts[1])
            dtype = parts[2]
            if dtype != 'float':
                raise ValueError(f"Unsupported POINTS type: {dtype}")
            if count > max_points:
                raise ValueError(f"POINTS count {count} exceeds {max_points} limit")
            points = []
            for _ in range(count):
                if idx + 1 >= len(lines):
                    raise ValueError("Truncated POINTS data")
                idx += 1
                parts = lines[idx].strip().split()
                if len(parts) != 3:
                    raise ValueError(f"Invalid POINT entry: {lines[idx]}")
                try:
                    x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                except ValueError:
                    raise ValueError(f"Nonfinite coordinate in POINTS: {lines[idx]}")
                if not (all(map(lambda v: v == v, (x, y, z)))):
                    raise ValueError(f"Nonfinite coordinate in POINTS: {lines[idx]}")
                points.append((x, y, z))
            continue

        if line.startswith('POLYGONS'):
            parts = line.split()
            if len(parts) != 3:
                raise ValueError(f"Invalid POLYGONS header: {line}")
            count = int(parts[1])
            indices_count = int(parts[2])
            if count > max_polygons:
                raise ValueError(f"POLYGONS count {count} exceeds {max_polygons} limit")
            polygons = []
            expected_indices = 0
            for i in range(count):
                if idx + 1 >= len(lines):
                    raise ValueError("Truncated POLYGONS data")
                idx += 1
                parts = lines[idx].strip().split()
                if len(parts) < 1:
                    raise ValueError(f"Empty POLYGON entry: {lines[idx]}")
                num_vertices = int(parts[0])
                expected_indices += num_vertices + 1
                if len(parts) - 1 != num_vertices:
                    raise ValueError(f"POLYGON {i} declares {num_vertices} but has {len(parts)-1} vertices")
                indices = []
                for j in range(1, len(parts)):
                    v = int(parts[j])
                    if v < 0 or v >= len(points):
                        raise ValueError(f"Invalid polygon index {v} at polygon {i}")
                    indices.append(v)
                polygons.append(tuple(indices))
            if expected_indices != indices_count:
                raise ValueError(f"POLYGONS header declares {indices_count} indices, actual {expected_indices}")
            continue

        if line.startswith('CELL_DATA'):
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(f"Invalid CELL_DATA header: {line}")
            cell_count = int(parts[1])
            if cell_count != len(polygons):
                raise ValueError(f"CELL_DATA count {cell_count} != POLYGONS count {len(polygons)}")
            idx += 1
            # Expect FIELD FieldData N
            while idx < len(lines):
                field_line = lines[idx].strip()
                if field_line.startswith('FIELD FieldData'):
                    break
                idx += 1
            if idx >= len(lines):
                break
            # Parse field definitions
            field_count = int(field_line.split()[-1])
            for _ in range(field_count):
                idx += 1
                if idx >= len(lines):
                    break
                field_header = lines[idx].strip().split()
                if len(field_header) < 3:
                    continue
                field_name = field_header[0]
                field_size = int(field_header[1])
                field_tuple_size = int(field_header[2])

                if field_name == 'nSurfaceLayers':
                    # nSurfaceLayers is scalar per cell
                    # OpenFOAM VTK format: size is number of values (cells)
                    num_values = field_size
                    if num_values != cell_count:
                        # Try alternate interpretation: size is number of arrays
                        num_values = cell_count
                    values = []
                    for _ in range(num_values):
                        if idx + 1 >= len(lines):
                            raise ValueError("Truncated nSurfaceLayers data")
                        idx += 1
                        parts = lines[idx].strip().split()
                        if len(parts) < 1:
                            raise ValueError(f"Invalid nSurfaceLayers value line: {lines[idx]}")
                        v = int(parts[0])
                        values.append(v)
                    n_surface_layers = tuple(values)
                else:
                    # Skip other fields
                    for _ in range(field_size):
                        if idx + 1 >= len(lines):
                            break
                        idx += 1
            continue

        if line.startswith('FIELD'):
            # Top-level FIELD TimeValue, skip
            idx += 1
            continue

        idx += 1

    return {'points': points, 'polygons': polygons, 'nSurfaceLayers': n_surface_layers}


def polygon_area_3d(points, polygon):
    """Compute 3D polygon area using cross product sum method.

    Area = 0.5 * |sum_{i} (v_i x v_{i+1})|
    """
    if len(polygon) < 3:
        return 0.0
    v0 = points[polygon[0]]
    sum_cross = [0.0, 0.0, 0.0]
    for i in range(len(polygon)):
        vi = points[polygon[i]]
        vj = points[polygon[(i + 1) % len(polygon)]]
        sum_cross[0] += vi[1] * vj[2] - vi[2] * vj[1]
        sum_cross[1] += vi[2] * vj[0] - vi[0] * vj[2]
        sum_cross[2] += vi[0] * vj[1] - vi[1] * vj[0]
    magnitude = (sum_cross[0]**2 + sum_cross[1]**2 + sum_cross[2]**2) ** 0.5
    return 0.5 * magnitude


def compute_metrics(points, polygons, n_surface_layers, requested_layers: int, min_coverage: float):
    """Compute coverage metrics from parsed mesh data.

    Returns dict with area coverage, face coverage, weighted layer count, etc.
    """
    if not polygons or not points:
        return {
            'total_faces': 0,
            'total_area': 0.0,
            'faces_with_layers': 0,
            'area_with_layers': 0.0,
            'face_coverage': 0.0,
            'area_coverage': 0.0,
            'weighted_layer_count': 0.0,
            'max_layer': 0,
            'full_area': 0.0,
        }

    total_area = 0.0
    area_with_layers = 0.0
    faces_with_layers = 0
    weighted_sum = 0.0
    max_layer = 0

    for i, polygon in enumerate(polygons):
        area = polygon_area_3d(points, polygon)
        total_area += area
        if n_surface_layers is not None and i < len(n_surface_layers):
            layer = n_surface_layers[i]
            if layer > 0:
                faces_with_layers += 1
                area_with_layers += area
                weighted_sum += layer * area
            if layer > max_layer:
                max_layer = layer
        else:
            # No layer data means 0 layers for this face
            pass

    full_area = total_area
    if n_surface_layers is not None:
        for i, polygon in enumerate(polygons):
            if i < len(n_surface_layers) and n_surface_layers[i] >= requested_layers:
                pass

    face_coverage = faces_with_layers / len(polygons) if polygons else 0.0
    area_coverage = area_with_layers / total_area if total_area > 0 else 0.0
    weighted_layer_count = weighted_sum / total_area if total_area > 0 else 0.0

    return {
        'total_faces': len(polygons),
        'total_area': total_area,
        'faces_with_layers': faces_with_layers,
        'area_with_layers': area_with_layers,
        'face_coverage': face_coverage,
        'area_coverage': area_coverage,
        'weighted_layer_count': weighted_layer_count,
        'max_layer': max_layer,
        'full_area': full_area,
        'requested_layers': requested_layers,
        'min_coverage': min_coverage,
    }


def parse_checkmesh_log(text: str):
    """Parse checkMesh output for mesh check result.

    Returns dict with 'mesh_ok' boolean and 'failed_checks' int.
    """
    result = {'mesh_ok': None, 'failed_checks': None, 'raw_status': 'unknown'}

    # Look for explicit failure message
    fail_match = re.search(r'Failed\s+(\d+)\s+mesh\s+checks?', text, re.IGNORECASE)
    if fail_match:
        failed = int(fail_match.group(1))
        result['mesh_ok'] = False
        result['failed_checks'] = failed
        result['raw_status'] = 'failed'
        return result

    # Look for "Mesh OK."
    if re.search(r'Mesh\s+OK\.', text, re.IGNORECASE):
        result['mesh_ok'] = True
        result['failed_checks'] = 0
        result['raw_status'] = 'ok'
        return result

    # No conclusive result
    result['mesh_ok'] = None
    result['failed_checks'] = None
    result['raw_status'] = 'unknown'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wall-surface', required=True, help='VTK POLYDATA surface file')
    parser.add_argument('--mesh-log', required=True, help='checkMesh log file')
    parser.add_argument('--requested-layers', type=int, default=18, help='Requested wall layers (default: 18)')
    parser.add_argument('--minimum-coverage', type=float, default=0.9, help='Minimum area coverage (default: 0.9)')
    parser.add_argument('--output', required=True, help='Output JSON file')
    args = parser.parse_args()

    try:
        # Read inputs
        surface_path = args.wall_surface
        log_path = args.mesh_log

        with open(surface_path, 'rb') as f:
            surface_data = f.read()

        with open(log_path, 'r', encoding='utf-8', errors='strict') as f:
            log_data = f.read()

        # Hash inputs
        surface_hash = hashlib.sha256(surface_data).hexdigest()
        log_hash = hashlib.sha256(log_data.encode('utf-8')).hexdigest()

        # Parse VTK
        try:
            mesh = parse_vtk_polydata(surface_data)
        except ValueError as e:
            output = {
                'input': {
                    'wall_surface': surface_path,
                    'wall_surface_hash': surface_hash,
                    'mesh_log': log_path,
                    'mesh_log_hash': log_hash,
                },
                'parameters': {
                    'requested_layers': args.requested_layers,
                    'minimum_coverage': args.minimum_coverage,
                },
                'mesh_check': {
                    'result': parse_checkmesh_log(log_data),
                },
                'coverage': {
                    'result': None,
                    'error': str(e),
                },
                'overall': {
                    'status': 'input_error',
                    'gate_passed': False,
                },
            }
            with open(args.output, 'x') as f:
                json.dump(output, f, indent=2)
            sys.exit(2)

        # Compute coverage metrics
        metrics = compute_metrics(
            mesh['points'],
            mesh['polygons'],
            mesh['nSurfaceLayers'],
            args.requested_layers,
            args.minimum_coverage,
        )

        # Check coverage gate
        area_coverage = metrics['area_coverage']
        gate_passed = area_coverage >= args.minimum_coverage

        # Parse checkMesh log
        mesh_result = parse_checkmesh_log(log_data)

        # Determine overall status
        # pass only if both mesh_check passes and coverage gate passes
        if mesh_result['mesh_ok'] is True and gate_passed:
            overall_status = 'pass'
        elif mesh_result['mesh_ok'] is False:
            overall_status = 'gate_failure'
        elif mesh_result['mesh_ok'] is None and mesh_result['raw_status'] == 'failed':
            overall_status = 'gate_failure'
        else:
            overall_status = 'gate_failure'

        output = {
            'input': {
                'wall_surface': surface_path,
                'wall_surface_hash': surface_hash,
                'mesh_log': log_path,
                'mesh_log_hash': log_hash,
            },
            'parameters': {
                'requested_layers': args.requested_layers,
                'minimum_coverage': args.minimum_coverage,
            },
            'metrics': metrics,
            'mesh_check': {
                'result': mesh_result,
            },
            'coverage': {
                'gate_passed': gate_passed,
                'minimum_coverage': args.minimum_coverage,
                'actual_coverage': area_coverage,
            },
            'overall': {
                'status': overall_status,
                'gate_passed': gate_passed and (mesh_result['mesh_ok'] is True),
            },
        }

        with open(args.output, 'x') as f:
            json.dump(output, f, indent=2)

        if overall_status == 'pass':
            sys.exit(0)
        else:
            sys.exit(1)

    except FileExistsError:
        print(f"Output file already exists: {args.output}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Input error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
