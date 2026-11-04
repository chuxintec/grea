"""Synthetic source-oracle vectors for the pinned Creator 2.4.15 algorithms.

The numeric expectations below were executed from the pinned engine methods in
the private bounded Node harness. Keep this public test synthetic: it contains
no engine source, private paths, or game samples.
"""

import unittest

from monkey.prefab_static_layout_completion import (
    simulate_layout,
    simulate_widget_alignment,
)


def assert_vector(test, actual, expected, places=8):
    test.assertEqual(len(actual), len(expected))
    for got, want in zip(actual, expected):
        if isinstance(want, list):
            assert_vector(test, got, want, places)
        else:
            test.assertAlmostEqual(got, want, places=places)


class StaticLayoutSourceOracleTests(unittest.TestCase):
    def test_horizontal_fractional_padding_spacing_and_negative_scale(self):
        # Source starts at leftBoundary + paddingLeft - spacingX, then adds
        # anchor*extent + spacingX for each active child.
        result = simulate_layout(
            {"layoutType": 1, "resize": 0, "padding": [11.5, 4, 19.25, 6],
             "spacingXY": [6.75, 3], "affectedByScale": True},
            [180, 70], [0.25, 0.5],
            [
                {"position": [0, 0], "size": [13.5, 8], "scale": [-1.5, 1], "anchor": [0.25, 0.5]},
                {"position": [0, 0], "size": [20.25, 9], "scale": [0.5, 1], "anchor": [0.75, 0.5]},
            ],
        )
        assert_vector(self, result["children"][0]["position"], [-28.4375, 0])
        assert_vector(self, result["children"][1]["position"], [1.09375, 0])

    def test_vertical_top_to_bottom_uses_top_padding(self):
        # The module's padding vector is [left, bottom, right, top], so the
        # source's paddingTop is the final value (13.25). Its initial spacing
        # subtraction cancels against the first child increment.
        result = simulate_layout(
            {"layoutType": 2, "resize": 0, "padding": [3, 8.5, 5, 13.25],
             "spacingXY": [2, 4.75], "verticalDirection": 1, "affectedByScale": True},
            [80, 150], [0.5, 0.25],
            [
                {"position": [0, 0], "size": [8, 14.5], "scale": [1, -1.25], "anchor": [0.5, 0.25]},
                {"position": [0, 0], "size": [9, 20.25], "scale": [1, 0.5], "anchor": [0.5, 0.75]},
            ],
        )
        assert_vector(self, result["children"][0]["position"], [0, 85.65625])
        assert_vector(self, result["children"][1]["position"], [0, 73.84375])

    def test_resize_modes_and_rtl_match_source_vectors(self):
        cases = [
            ({"layoutType": 1, "resize": 1, "padding": [5, 3, 9, 4], "spacingXY": [7, 2],
              "affectedByScale": True}, [100, 50], [0.5, 0.5],
             [(10, 5, 1, 1, 0), (20, 6, -1, 1, 0.5)], [51, 50], [-20.5, 6.5]),
            ({"layoutType": 1, "resize": 2, "padding": [10, 3, 20, 4], "spacingXY": [7, 2],
              "affectedByScale": True}, [100, 50], [0.5, 0.5],
             [(10, 5, 1, 1, 0), (20, 6, -2, 1, 0.5)], [100, 50], [-40, 14.25]),
            ({"layoutType": 1, "resize": 0, "padding": [9, 3, 17, 4], "spacingXY": [5.5, 2],
              "horizontalDirection": 1, "affectedByScale": True}, [120, 40], [0.2, 0.5],
             [(8, 5, 1.5, 1, 0.25), (14, 6, -0.5, 1, 0.75)], [120, 40], [70, 59.75]),
        ]
        for slot, owner_size, owner_anchor, raw_children, expected_owner, expected_x in cases:
            children = [
                {"position": [0, 0], "size": [w, h], "scale": [sx, sy], "anchor": [ax, 0.5]}
                for w, h, sx, sy, ax in raw_children
            ]
            with self.subTest(slot=slot):
                result = simulate_layout(slot, owner_size, owner_anchor, children)
                assert_vector(self, result["ownerSize"], expected_owner)
                assert_vector(self, [row["position"][0] for row in result["children"]], expected_x)

    def test_two_ordered_layouts_resize_nested_children(self):
        # First component resizes its sole nested Layout node to 160. The next
        # component then divides 160 - 10 - 10 - 5 across two children.
        outer = simulate_layout(
            {"layoutType": 1, "resize": 2, "padding": [5, 0, 15, 0], "spacingXY": [10, 0]},
            [180, 50], [0, 0],
            [{"position": [0, 0], "size": [80, 40], "scale": [1, 1], "anchor": [0, 0]}],
        )
        self.assertEqual(outer["children"][0]["size"], [160, 40])
        inner = simulate_layout(
            {"layoutType": 1, "resize": 2, "padding": [10, 0, 10, 0], "spacingXY": [5, 0]},
            outer["children"][0]["size"], [0, 0],
            [
                {"position": [0, 0], "size": [20, 8], "scale": [1, 1], "anchor": [0, 0]},
                {"position": [0, 0], "size": [30, 9], "scale": [1, 1], "anchor": [0.5, 0]},
            ],
        )
        assert_vector(self, [row["size"] for row in inner["children"]], [[67.5, 8], [67.5, 9]])
        assert_vector(self, [row["position"] for row in inner["children"]], [[10, 0], [116.25, 0]])


class StaticWidgetSourceOracleTests(unittest.TestCase):
    @staticmethod
    def _widget(flags=45, margins=(12, 7, 20, 9)):
        return {"alignFlags": flags, "margins": list(margins), "absolute": [True] * 4,
                "center": [0, 0], "centerAbsolute": [True, True]}

    def test_stretch_edges_use_independent_low_and_high_margins(self):
        # The source computes low = base + lowMargin and high = base + length
        # - highMargin. It does not derive high from low.
        result = simulate_widget_alignment(
            self._widget(),
            {"size": [40, 30], "position": [3, -2], "scale": [-2, 1.5], "anchor": [0.2, 0.7]},
            {"size": [200, 120], "anchor": [0.25, 0.5]},
        )
        assert_vector(self, result["size"], [84, 69.33333333333333])
        assert_vector(self, result["position"], [96.4, 19.8])

    def test_explicit_target_uses_xy_chain_even_when_z_scale_is_zero(self):
        # The source inverts x/y through each ancestor independently; a zero
        # z scale has no bearing on the 2D alignment calculation.
        result = simulate_widget_alignment(
            self._widget(),
            {"size": [40, 30], "position": [3, -2], "scale": [-2, -1.5], "anchor": [0.2, 0.7]},
            {"size": [200, 120], "anchor": [0.25, 0.6], "explicit": True},
            [
                {"position": [10, -4, 0], "scale": [2, 3, 0]},
                {"position": [5, 2, 0], "scale": [0.5, 2, 0]},
            ],
        )
        assert_vector(self, result["size"], [84, 11.555555555555555])
        assert_vector(self, result["position"], [76.4, -5.966666666666666])

    def test_one_sided_alignment_and_negative_ancestor_scales(self):
        result = simulate_widget_alignment(
            self._widget(flags=33, margins=(6, 4, 13, 8)),  # right + top
            {"size": [18, 16], "position": [3, -2], "scale": [1.25, -0.5], "anchor": [0.8, 0.2]},
            {"size": [90, 70], "anchor": [0.7, 0.3], "explicit": True},
            [
                {"position": [3, 7, 0], "scale": [-2, 0.75, 0]},
                {"position": [-5, 2, 0], "scale": [1.5, -1.25, 0]},
            ],
        )
        assert_vector(self, result["size"], [18, 16])
        assert_vector(self, result["position"], [-4.833333333333335, -36.266666666666666])


if __name__ == "__main__":
    unittest.main()
