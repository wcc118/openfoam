"""Independent coordinate oracles and adversarial geometry checks."""

import csv
import json
import math
from pathlib import Path
import tempfile
import unittest
from scripts.generate_wing import build, generate, section_point, validate


class WingTests(unittest.TestCase):
    def test_pdas_normal_offset_coordinates(self):
        # PDAS sections45.html, second NACA 4412 table: normal-offset stations,
        # not its table interpolated at vertical x positions. Units: chord.
        expected = {
            0.1: (0.093054, 0.063810, 0.106946, -0.028810),
            0.4: (0.4, 0.098030, 0.4, -0.018030),
            0.8: (0.802323, 0.048350, 0.797677, -0.003906),
        }
        for station, row in expected.items():
            with self.subTest(station=station):
                for observed, reference in zip(section_point("4412", station), row):
                    self.assertAlmostEqual(observed, reference, delta=1e-6)

    def test_symmetric_section_and_finite_te(self):
        for x in (0, 0.01, 0.1, 0.3, 0.5, 0.8, 1):
            xu, zu, xl, zl = section_point("0012", x)
            self.assertEqual(xu, xl)
            self.assertEqual(zu, -zl)
        self.assertAlmostEqual(section_point("0012", 1)[1], 0.00126, places=14)
        # Analytic integral of standard 0012 thickness over unit chord.
        v, f, s, a = build("0012", span=1, chord=1, points=1025, sections=2)
        self.assertAlmostEqual(a, 0.08221, delta=2e-7)

    def test_default_topology_volume_and_references(self):
        for foil in ("4412", "0012"):
            v, f, s, a = build(foil)
            checks = validate(v, f, a * 1.2192)
            self.assertEqual(checks["vertex_count"], 514)
            self.assertEqual(len(v) - checks["edge_count"] + len(f), 2)
            self.assertAlmostEqual(max(p[1] for p in v) - min(p[1] for p in v), 1.2192)
            self.assertGreater(checks["min_triangle_area_m2"], 0)

    def test_scale_units(self):
        v, f, s, a = build()
        v2, f2, s2, a2 = build(span=2 * 1.2192, chord=3 * 0.1016)
        self.assertEqual(f, f2)
        r = validate(v, f, a * 1.2192)
        r2 = validate(v2, f2, a2 * 2 * 1.2192)
        self.assertAlmostEqual(a2 / a, 9)
        self.assertAlmostEqual(r2["volume_m3"] / r["volume_m3"], 18)

    def test_corrupt_surface_rejected(self):
        v, f, s, a = build(points=17, sections=3)
        for broken in (
            f[:-1],
            f + [f[0]],
            [(c, b, a) for a, b, c in f],
            [(f[0][0], f[0][0], f[0][2])] + f[1:],
            [(f[0][1], f[0][0], f[0][2])] + f[1:],
        ):
            with self.subTest(first=broken[0]):
                with self.assertRaises(ValueError):
                    validate(v, broken, a * 1.2192)
        with self.assertRaises(ValueError):
            validate(v + [(9, 9, 9)], f, a * 1.2192)
        with self.assertRaises(ValueError):
            validate([(math.nan, 0, 0)] + v[1:], f, a * 1.2192)
        with self.assertRaises(ValueError):
            validate(v, f, 2 * a * 1.2192)

    def test_section_simple_polygon(self):
        # A simple 2D polygon extruded linearly cannot cross itself in 3D.
        # Test nonadjacent edges, including the finite trailing-edge strip.
        def orient(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        for foil in ("4412", "0012"):
            v, _, _, _ = build(foil, sections=2)
            p = [(x, z) for x, y, z in v[:257]]
            for i, a in enumerate(p):
                b = p[(i + 1) % len(p)]
                for j in range(i + 2, len(p)):
                    if i == 0 and j == len(p) - 1:
                        continue
                    c, d = p[j], p[(j + 1) % len(p)]
                    self.assertFalse(
                        orient(a, b, c) * orient(a, b, d) < 0
                        and orient(c, d, a) * orient(c, d, b) < 0
                    )

    def test_invalid_inputs(self):
        for kwargs in (
            {"span": 0},
            {"chord": -1},
            {"span": math.nan},
            {"chord": math.inf},
            {"points": 8},
            {"points": 2000},
            {"sections": 1},
            {"sections": 300},
            {"points": 1025, "sections": 257},
            {"points": 12.5},
            {"airfoil": "2412"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    build(**kwargs)
        for x in (-0.1, 1.1, math.nan):
            with self.assertRaises(ValueError):
                section_point("4412", x)

    def test_exports_determinism_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / "a", Path(temp) / "b"
            ra = generate(a)
            rb = generate(b)
            self.assertEqual(ra["sha256"], rb["sha256"])
            self.assertEqual(ra["reference_area_m2"], 0.12387072)
            self.assertEqual(ra["moment_origin_m"], [0.0254, 0, 0])
            self.assertLess(ra["bounds_m"][0][0], 0)  # Do not clip normal offset.
            self.assertGreater(ra["bounds_m"][0][1], 0.1016)
            with (a / "section.csv").open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 129)
            self.assertGreater(float(rows[64]["upper_z_m"]), 0.005)
            self.assertEqual((a / "wing.stl").read_text().count("facet normal "), 1024)
            self.assertTrue(
                json.loads((a / "geometry.json").read_text())["checks"]["watertight"]
            )
            self.assertIn("<svg", (a / "preview.html").read_text())
            with self.assertRaises(FileExistsError):
                generate(a)
            empty = Path(temp) / "empty"
            empty.mkdir()
            with self.assertRaises(FileExistsError):
                generate(empty)


if __name__ == "__main__":
    unittest.main()
