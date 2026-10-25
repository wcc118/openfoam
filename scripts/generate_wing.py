"""Generate a demonstration rectangular NACA wing, in SI coordinates.

Audited/adapted NACA equations: wcc118/aero panel_solver/geometry.py at
79c1236252fe12e0518384a33cd45c181e2df740; correct its missing normal x offsets.
Thickness convention and independent tables: https://www.pdas.com/sections45.html
and https://www.pdas.com/naca456thick4.html. The 5*t polynomial is HALF thickness.
No sibling source imports. Surface topology and checks implemented here.
"""

import math
from collections import defaultdict


def section_point(airfoil, x):
    if airfoil not in ("0012", "4412") or not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError("unsupported airfoil or station")
    m, p, t = int(airfoil[0]) / 100, int(airfoil[1]) / 10, int(airfoil[2:]) / 100
    yc = slope = 0.0
    if m:
        if x < p:
            yc = m / p**2 * (2 * p * x - x * x)
            slope = 2 * m / p**2 * (p - x)
        else:
            yc = m / (1 - p) ** 2 * (1 - 2 * p + 2 * p * x - x * x)
            slope = 2 * m / (1 - p) ** 2 * (p - x)
    theta = math.atan(slope)
    yt = (
        5
        * t
        * (
            0.2969 * math.sqrt(x)
            - 0.126 * x
            - 0.3516 * x * x
            + 0.2843 * x**3
            - 0.1015 * x**4
        )
    )
    return (
        x - yt * math.sin(theta),
        yc + yt * math.cos(theta),
        x + yt * math.sin(theta),
        yc - yt * math.cos(theta),
    )


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def normal(v, face):
    a, b, c = (v[i] for i in face)
    return cross(tuple(y - x for x, y in zip(a, b)), tuple(y - x for x, y in zip(a, c)))


def build(airfoil="4412", span=1.2192, chord=0.1016, points=129, sections=2):
    if not all(math.isfinite(v) and 1e-5 <= v <= 1e4 for v in (span, chord)):
        raise ValueError("span and chord must be finite and in [1e-5,1e4] m")
    if (
        airfoil not in ("0012", "4412")
        or type(points) is not int
        or type(sections) is not int
        or not 9 <= points <= 1025
        or not 2 <= sections <= 257
        or points * sections > 100000
    ):
        raise ValueError("invalid airfoil or bounded resolution")
    s = [
        tuple(
            c * chord
            for c in section_point(
                airfoil, (1 - math.cos(math.pi * i / (points - 1))) / 2
            )
        )
        for i in range(points)
    ]
    # Counterclockwise in x,z: LE -> lower TE -> upper TE -> upper LE.
    polygon = [(q[2], q[3]) for q in s] + [(q[0], q[1]) for q in reversed(s[1:])]
    n = len(polygon)
    vertices = [
        (x, -span / 2 + span * j / (sections - 1), z)
        for j in range(sections)
        for x, z in polygon
    ]
    faces = []
    for j in range(sections - 1):
        for i in range(n):
            a = j * n + i
            b = j * n + (i + 1) % n
            c = (j + 1) * n + (i + 1) % n
            d = (j + 1) * n + i
            faces.extend(((a, d, b), (b, d, c)))
    # Tips: strips between matching normal-offset stations, sharing the LE.
    for j in (0, sections - 1):
        offset = j * n
        lower = lambda i: offset + i
        upper = lambda i: offset + (n - i if i else 0)
        tris = [(lower(0), lower(1), upper(1))]
        for i in range(1, points - 1):
            tris.extend(
                (
                    (lower(i), lower(i + 1), upper(i)),
                    (lower(i + 1), upper(i + 1), upper(i)),
                )
            )
        # CCW x,z is -y, the lower-span cap's outward normal.
        faces.extend(tris if j == 0 else [(a, c, b) for a, b, c in tris])
    area = (
        math.fsum(
            polygon[i][0] * polygon[(i + 1) % n][1]
            - polygon[(i + 1) % n][0] * polygon[i][1]
            for i in range(n)
        )
        / 2
    )
    return vertices, faces, s, area


def validate(vertices, faces, expected_volume):
    if not all(math.isfinite(q) for v in vertices for q in v):
        raise ValueError("nonfinite vertices")
    edge = defaultdict(list)
    adjacency = [set() for _ in vertices]
    volumes = []
    areas = []
    for a, b, c in faces:
        if len({a, b, c}) != 3 or min(a, b, c) < 0 or max(a, b, c) >= len(vertices):
            raise ValueError("invalid face indices")
        area = (
            math.sqrt(dot(normal(vertices, (a, b, c)), normal(vertices, (a, b, c)))) / 2
        )
        if not math.isfinite(area) or area <= 0:
            raise ValueError("degenerate triangle")
        areas.append(area)
        volumes.append(dot(vertices[a], cross(vertices[b], vertices[c])) / 6)
        for u, v in ((a, b), (b, c), (c, a)):
            edge[tuple(sorted((u, v)))].append(1 if u < v else -1)
            adjacency[u].add(v)
            adjacency[v].add(u)
    if any(len(v) != 2 or sum(v) != 0 for v in edge.values()):
        raise ValueError("surface not closed and consistently oriented")
    seen = {0}
    stack = [0]
    while stack:
        for j in adjacency[stack.pop()] - seen:
            seen.add(j)
            stack.append(j)
    if len(seen) != len(vertices):
        raise ValueError("disconnected vertices")
    volume = math.fsum(volumes)
    if (
        not math.isfinite(volume)
        or volume <= 0
        or not math.isclose(volume, expected_volume, rel_tol=1e-10, abs_tol=0)
    ):
        raise ValueError("volume mismatch or inward orientation")
    return dict(
        watertight=True,
        oriented=True,
        connected=True,
        vertex_count=len(vertices),
        triangle_count=len(faces),
        edge_count=len(edge),
        min_triangle_area_m2=min(areas),
        volume_m3=volume,
        expected_volume_m3=expected_volume,
    )


def preview(vertices, sections, points, chord, span, airfoil):
    """Self-contained SVG views, all with equal physical axis scales."""
    import html

    n = 2 * points - 1
    lines = []
    for j in (0, sections // 2, sections - 1):
        lines.append([vertices[j * n + i] for i in range(n)] + [vertices[j * n]])
    for i in (0, points - 1, points):
        lines.append([vertices[j * n + i] for j in range(sections)])

    def svg(paths, project):
        projected = [[project(v) for v in path] for path in paths]
        xs = [x for path in projected for x, y in path]
        ys = [y for path in projected for x, y in path]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        width = max(xmax - xmin, 1e-12)
        height = max(ymax - ymin, width * 0.15)
        pad = max(width, height) * 0.07
        shapes = "".join(
            '<polyline points="'
            + " ".join(f"{x:.9g},{-y:.9g}" for x, y in path)
            + '"/>'
            for path in projected
        )
        return f'<svg viewBox="{xmin - pad} {-ymax - pad} {width + 2 * pad} {height + 2 * pad}" role="img"><g fill="none" stroke="#38bdf8" stroke-width="{max(width, height) * 0.002}">{shapes}</g></svg>'

    iso = lambda v: (v[1] + 0.6 * v[0], v[2] + 0.28 * v[1] - 0.4 * v[0])
    section = svg([lines[0]], lambda v: (v[0], v[2]))
    plan = svg(lines, lambda v: (v[1], -v[0]))
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Wing geometry preview</title>
<style>body{{background:#101827;color:#e2e8f0;font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 24px}}svg{{width:100%;max-height:360px;background:#172338;border-radius:12px}}h1{{font-size:28px}}p{{line-height:1.6}}a{{color:#7dd3fc}}</style>
<h1>NACA {html.escape(airfoil)} · provisional wing</h1><p>Full span {span:g} m · nominal chord {chord:g} m · reference area {span * chord:.8g} m².<br>Rectangular, unswept, untwisted. Finite trailing edge and closed tips. Demonstration geometry, not an approved aircraft design.</p>
<h2>Oblique outline</h2>{svg(lines, iso)}<h2>Airfoil section · equal x/z scale</h2>{section}<h2>Planform · equal x/y scale</h2>{plan}
<p>Axes: x downstream, y along span, z upward. Moment origin: midspan quarter chord. This is a surface preview; it contains no flow or flutter results.</p><p><a href="wing.stl">STL surface</a> · <a href="geometry.json">Geometry checks and provenance</a> · <a href="section.csv">Section coordinates</a></p></html>"""


def generate(output, airfoil="4412", span=1.2192, chord=0.1016, points=129, sections=2):
    import csv
    from datetime import datetime, timezone
    import hashlib
    import json
    import subprocess
    from pathlib import Path

    vertices, faces, section, area = build(airfoil, span, chord, points, sections)
    checks = validate(vertices, faces, area * span)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    with (output / "wing.stl").open("w") as f:
        f.write("solid wing\n")
        for face in faces:
            norm = normal(vertices, face)
            length = math.sqrt(dot(norm, norm))
            f.write(
                "facet normal "
                + " ".join(f"{q / length:.17g}" for q in norm)
                + "\n outer loop\n"
            )
            for i in face:
                f.write("  vertex " + " ".join(f"{q:.17g}" for q in vertices[i]) + "\n")
            f.write(" endloop\nendfacet\n")
        f.write("endsolid wing\n")
    with (output / "section.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["mean_x_over_c", "upper_x_m", "upper_z_m", "lower_x_m", "lower_z_m"]
        )
        for i, row in enumerate(section):
            writer.writerow([(1 - math.cos(math.pi * i / (points - 1))) / 2, *row])
    (output / "preview.html").write_text(
        preview(vertices, sections, points, chord, span, airfoil)
    )
    root = Path(__file__).resolve().parent.parent
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True
    )
    report = dict(
        schema_version=1,
        created_utc=datetime.now(timezone.utc).isoformat(),
        demonstration_only=True,
        airfoil=airfoil,
        span_m=span,
        chord_m=chord,
        reference_area_m2=span * chord,
        moment_origin_m=[0.25 * chord, 0, 0],
        points=points,
        span_sections=sections,
        axes={"x": "downstream", "y": "span", "z": "up"},
        trailing_edge="finite: coefficient -0.1015",
        cross_section_area_m2=area,
        bounds_m=[
            [min(v[i] for v in vertices), max(v[i] for v in vertices)] for i in range(3)
        ],
        checks=checks,
        source={
            "revision": revision.stdout.strip() if revision.returncode == 0 else None,
            "dirty": bool(dirty.stdout) if dirty.returncode == 0 else None,
            "generator_sha256": sha(Path(__file__)),
            "adapted_from": "wcc118/aero panel_solver/geometry.py@79c1236252fe12e0518384a33cd45c181e2df740",
            "correction": "normal-offset x coordinates; half-thickness polynomial used without further halving",
            "reference": "https://www.pdas.com/sections45.html",
        },
        sha256={p.name: sha(p) for p in sorted(output.iterdir())},
    )
    (output / "geometry.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    return report


def main():
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--airfoil", choices=["4412", "0012"], default="4412")
    p.add_argument("--span-m", type=float, default=1.2192)
    p.add_argument("--chord-m", type=float, default=0.1016)
    p.add_argument("--points", type=int, default=129)
    p.add_argument("--span-sections", type=int, default=2)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    try:
        report = generate(
            args.output,
            args.airfoil,
            args.span_m,
            args.chord_m,
            args.points,
            args.span_sections,
        )
    except (ValueError, OSError) as exc:
        p.exit(1, f"Geometry generation failed: {exc}\n")
    print(
        f"Generated {report['checks']['triangle_count']} checked triangles in {args.output}"
    )


if __name__ == "__main__":
    main()
