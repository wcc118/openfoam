"""Read a LIMITED mesh-evidence gate, not CFD/yPlus/physical qualification.

Supported input: legacy VTK 2.0 ASCII POLYDATA with POINTS, POLYGONS,
CELL_DATA FIELD nSurfaceLayers and optional top-level TimeValue metadata.
Arrays are whitespace-delimited; line wrapping has no semantic meaning.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

MAX_BYTES = 64 * 1024 * 1024
MAX_COUNT = 1_000_000


class Tokens:
    def __init__(self, text):
        self.items = text.split()
        self.index = 0

    def take(self):
        if self.index >= len(self.items):
            raise ValueError("Truncated VTK data")
        token = self.items[self.index]
        self.index += 1
        return token

    def expect(self, expected):
        if self.take() != expected:
            raise ValueError(f"Expected {expected}")

    def integer(self, low=0, high=MAX_COUNT):
        value = int(self.take())
        if not low <= value <= high:
            raise ValueError("Integer/count outside supported bounds")
        return value

    def number(self):
        value = float(self.take())
        if not math.isfinite(value):
            raise ValueError("Nonfinite VTK value")
        return value

    def numeric_type(self):
        if self.take() not in ("float", "double"):
            raise ValueError("Unsupported VTK numeric type")


def polygon_area_3d(points, polygon):
    if len(polygon) < 3 or len(set(polygon)) != len(polygon):
        raise ValueError("Degenerate polygon indices")
    if any(type(i) is not int or not 0 <= i < len(points) for i in polygon):
        raise ValueError("Invalid polygon index")
    # Translation reduces cancellation for small faces far from the origin.
    origin = points[polygon[0]]
    vectors = [tuple(x - y for x, y in zip(points[i], origin)) for i in polygon]
    cross_sum = [
        math.fsum(
            v[j] * w[k] - v[k] * w[j]
            for v, w in zip(vectors, vectors[1:] + vectors[:1])
        )
        for j, k in ((1, 2), (2, 0), (0, 1))
    ]
    area = math.hypot(*cross_sum) / 2
    if not math.isfinite(area) or area <= 0:
        raise ValueError("Nonfinite or zero-area polygon")
    return area


def parse_vtk_polydata(
    data, max_size=MAX_BYTES, max_points=MAX_COUNT, max_polygons=MAX_COUNT
):
    if len(data) > max_size:
        raise ValueError("VTK exceeds byte limit")
    lines = data.decode("ascii").splitlines()
    if (
        len(lines) < 4
        or lines[0].strip() != "# vtk DataFile Version 2.0"
        or lines[2].strip() != "ASCII"
        or lines[3].strip() != "DATASET POLYDATA"
    ):
        raise ValueError("Only legacy VTK 2.0 ASCII POLYDATA is supported")
    tokens = Tokens("\n".join(lines[4:]))
    if tokens.items and tokens.items[0] == "FIELD":
        for word in ("FIELD", "FieldData", "1", "TimeValue", "1", "1"):
            tokens.expect(word)
        tokens.numeric_type()
        tokens.number()
    tokens.expect("POINTS")
    count = tokens.integer(1, max_points)
    tokens.numeric_type()
    points = [tuple(tokens.number() for _ in range(3)) for _ in range(count)]
    tokens.expect("POLYGONS")
    count = tokens.integer(1, max_polygons)
    declared = tokens.integer(count * 4, 8 * MAX_COUNT)
    polygons = []
    consumed = 0
    for _ in range(count):
        size = tokens.integer(3, min(len(points), 1024))
        consumed += size + 1
        polygon = tuple(tokens.integer(0, len(points) - 1) for _ in range(size))
        polygon_area_3d(points, polygon)  # Reject, never skip, bad facets.
        polygons.append(polygon)
    if consumed != declared:
        raise ValueError("POLYGONS count mismatch")
    tokens.expect("CELL_DATA")
    if tokens.integer(1, max_polygons) != count:
        raise ValueError("CELL_DATA count mismatch")
    for word in ("FIELD", "FieldData", "1", "nSurfaceLayers", "1"):
        tokens.expect(word)
    if tokens.integer(1, max_polygons) != count:
        raise ValueError("Layer tuple count mismatch")
    tokens.numeric_type()
    layers = []
    for _ in range(count):
        v = tokens.number()
        if v < 0 or not v.is_integer():
            raise ValueError("Layers must be nonnegative integers")
        layers.append(int(v))
    if tokens.index != len(tokens.items):
        raise ValueError("Unexpected trailing VTK data")
    return dict(points=points, polygons=polygons, nSurfaceLayers=tuple(layers))


def validate_parameters(requested_layers, min_coverage):
    if type(requested_layers) is not int or not 1 <= requested_layers <= 1000:
        raise ValueError("Requested layers must be integer in [1,1000]")
    if not math.isfinite(min_coverage) or not 0 <= min_coverage <= 1:
        raise ValueError("Minimum coverage must be finite in [0,1]")


def compute_metrics(points, polygons, n_surface_layers, requested_layers, min_coverage):
    validate_parameters(requested_layers, min_coverage)
    if (
        not points
        or not polygons
        or n_surface_layers is None
        or len(n_surface_layers) != len(polygons)
    ):
        raise ValueError("Missing/inconsistent surface or layer data")
    if any(len(p) != 3 or not all(math.isfinite(x) for x in p) for p in points):
        raise ValueError("Invalid point")
    if any(
        type(v) is not int or not 0 <= v <= requested_layers for v in n_surface_layers
    ):
        raise ValueError("Layer value outside [0,requested_layers]")
    areas = [polygon_area_3d(points, p) for p in polygons]
    total = math.fsum(areas)
    covered = math.fsum(a for a, l in zip(areas, n_surface_layers) if l > 0)
    full = math.fsum(
        a for a, l in zip(areas, n_surface_layers) if l == requested_layers
    )
    weighted = math.fsum(a * l for a, l in zip(areas, n_surface_layers))
    if not all(math.isfinite(v) for v in (total, covered, full, weighted)):
        raise ValueError("Nonfinite aggregate area/weight")
    count = sum(v > 0 for v in n_surface_layers)
    return dict(
        total_faces=len(polygons),
        total_area=total,
        faces_with_layers=count,
        area_with_layers=covered,
        face_coverage=count / len(polygons),
        area_coverage=covered / total,
        weighted_layer_count=weighted / total,
        min_layer=min(n_surface_layers),
        max_layer=max(n_surface_layers),
        full_area=full,
        full_area_coverage=full / total,
        requested_layers=requested_layers,
        min_coverage=min_coverage,
    )


def parse_checkmesh_log(text):
    failures = re.findall(r"^\s*Failed\s+(\d+)\s+mesh\s+checks?\.", text, re.M)
    if failures:
        return dict(
            mesh_ok=False, failed_checks=max(map(int, failures)), raw_status="failed"
        )
    if "FOAM FATAL" in text:
        return dict(mesh_ok=False, failed_checks=None, raw_status="fatal")
    # Require completion marker after the verdict, not an unfinished/log snippet.
    if re.search(r"^\s*Mesh OK\.\s*$[\s\S]*?^\s*End\s*$", text, re.M):
        return dict(mesh_ok=True, failed_checks=0, raw_status="ok")
    return dict(mesh_ok=None, failed_checks=None, raw_status="unknown")


def read_bounded(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Input exceeds 64 MiB limit")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wall-surface", required=True)
    parser.add_argument("--mesh-log", required=True)
    parser.add_argument("--requested-layers", type=int, default=18)
    parser.add_argument("--minimum-coverage", type=float, default=0.9)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if Path(args.output).exists():
            raise FileExistsError(args.output)
        validate_parameters(args.requested_layers, args.minimum_coverage)
        surface = read_bounded(args.wall_surface)
        log = read_bounded(args.mesh_log)
        report = dict(
            schema_version=1,
            evidence_scope="Limited mesh log/layer gate; not yPlus, flow or physical qualification",
            input={
                "wall_surface": str(Path(args.wall_surface).resolve()),
                "wall_surface_hash": hashlib.sha256(surface).hexdigest(),
                "mesh_log": str(Path(args.mesh_log).resolve()),
                "mesh_log_hash": hashlib.sha256(log).hexdigest(),
            },
            parameters={
                "requested_layers": args.requested_layers,
                "minimum_coverage": args.minimum_coverage,
            },
        )
        try:
            mesh = parse_vtk_polydata(surface)
            metrics = compute_metrics(
                mesh["points"],
                mesh["polygons"],
                mesh["nSurfaceLayers"],
                args.requested_layers,
                args.minimum_coverage,
            )
            mesh_result = parse_checkmesh_log(log.decode("utf-8"))
            covered = metrics["area_coverage"] >= args.minimum_coverage
            passed = covered and mesh_result["mesh_ok"] is True
            report.update(
                metrics=metrics,
                mesh_check={"result": mesh_result},
                coverage={
                    "gate_passed": covered,
                    "actual_coverage": metrics["area_coverage"],
                },
                overall={
                    "status": "pass" if passed else "gate_failure",
                    "gate_passed": passed,
                },
            )
            code = 0 if passed else 1
        except (ValueError, OverflowError) as exc:
            report.update(
                error=str(exc), overall={"status": "input_error", "gate_passed": False}
            )
            code = 2
        with Path(args.output).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except (OSError, ValueError) as exc:
        print(f"Input/output error: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)


if __name__ == "__main__":
    main()
