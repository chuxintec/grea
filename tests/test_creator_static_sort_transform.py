import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def identity():
    return [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]


def multiply(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def inverse(m):
    rows = [m[r][:] + identity()[r] for r in range(4)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda row: abs(rows[row][col]))
        if abs(rows[pivot][col]) < 1e-12:
            raise ValueError("singular")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        factor = rows[col][col]
        rows[col] = [v / factor for v in rows[col]]
        for row in range(4):
            if row == col:
                continue
            factor = rows[row][col]
            rows[row] = [a - factor * b for a, b in zip(rows[row], rows[col])]
    return [row[4:] for row in rows]


def determinant3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def compose(position, angles, scale):
    x, y, z = [v / 2 for v in angles]
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    # Rz * Ry * Rx, followed by scale on the matrix columns (Creator SRT).
    rotation = [
        [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
        [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
        [-sy, cy * sx, cy * cx],
    ]
    result = identity()
    for row in range(3):
        for col in range(3):
            result[row][col] = rotation[row][col] * scale[col]
    for row, value in enumerate(position):
        result[row][3] = value
    return result


def creator_srt_reconstruct(matrix):
    # Mirrors Creator 3.8 Mat4.toSRT's column lengths and determinant reflection
    # handling. Quaternion conversion preserves this proper rotation matrix.
    scales = [math.sqrt(sum(matrix[row][col] ** 2 for row in range(3))) for col in range(3)]
    rotation = [[matrix[row][col] / scales[col] for col in range(3)] for row in range(3)]
    if determinant3(rotation) < 0:
        scales[0] *= -1
        for row in range(3):
            rotation[row][0] *= -1
    result = identity()
    for row in range(3):
        for col in range(3):
            result[row][col] = rotation[row][col] * scales[col]
        result[row][3] = matrix[row][3]
    return result


def creator_srt_reconstruct_zero_scales(matrix, authored_zero_axes=None):
    columns = [[matrix[row][col] for row in range(3)] for col in range(3)]
    lengths = [math.sqrt(sum(value * value for value in column)) for column in columns]
    zero = [length == 0 or bool(authored_zero_axes and authored_zero_axes[index]) for index, length in enumerate(lengths)]
    tolerance = max([1.0] + lengths) * 1e-8
    if authored_zero_axes and any(authored_zero_axes[i] and lengths[i] > tolerance for i in range(3)):
        raise ValueError("authored zero axis mismatch")
    if not any(zero):
        return creator_srt_reconstruct(matrix)
    basis = [None if zero[index] else [value / lengths[index] for value in columns[index]] for index in range(3)]

    def dot(a, b):
        return sum(a[i] * b[i] for i in range(3))

    def cross(a, b):
        return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]

    def normalize(value):
        length = math.sqrt(dot(value, value))
        if not length:
            raise ValueError("degenerate synthetic basis")
        return [channel / length for channel in value]

    known = [index for index, axis in enumerate(basis) if axis is not None]
    for left in range(len(known)):
        for right in range(left + 1, len(known)):
            if abs(dot(basis[known[left]], basis[known[right]])) > 1e-7:
                raise ValueError("zero-scale shear")
    if len(known) == 2:
        if zero[0]: basis[0] = normalize(cross(basis[1], basis[2]))
        elif zero[1]: basis[1] = normalize(cross(basis[2], basis[0]))
        else: basis[2] = normalize(cross(basis[0], basis[1]))
    elif len(known) == 1:
        axis = known[0]
        current = basis[axis]
        reference = [0, 0, 1] if abs(current[2]) < 0.9 else [0, 1, 0]
        if axis == 0:
            basis[1] = normalize(cross(reference, current)); basis[2] = normalize(cross(current, basis[1]))
        elif axis == 1:
            basis[2] = normalize(cross(current, reference)); basis[0] = normalize(cross(basis[1], basis[2]))
        else:
            basis[0] = normalize(cross(reference, current)); basis[1] = normalize(cross(current, basis[0]))
    else:
        basis = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    temporary = [row[:] for row in matrix]
    for col in range(3):
        if zero[col]:
            for row in range(3): temporary[row][col] = basis[col][row]
    result = creator_srt_reconstruct(temporary)
    for col in range(3):
        if zero[col]:
            for row in range(3): result[row][col] = 0
    return result


def collapsed_parent_local(parent, source):
    det = parent[0][0] * parent[1][1] - parent[0][1] * parent[1][0]
    inverse2d = [[parent[1][1] / det, -parent[0][1] / det],
                 [-parent[1][0] / det, parent[0][0] / det]]
    local = identity()
    for col in (0, 1):
        x, y = source[0][col], source[1][col]
        local[0][col] = inverse2d[0][0] * x + inverse2d[0][1] * y
        local[1][col] = inverse2d[1][0] * x + inverse2d[1][1] * y
    dx, dy = source[0][3] - parent[0][3], source[1][3] - parent[1][3]
    local[0][3] = inverse2d[0][0] * dx + inverse2d[0][1] * dy
    local[1][3] = inverse2d[1][0] * dx + inverse2d[1][1] * dy
    # Source and parent are coplanar with collapsed Z; any local Z basis works.
    local[2][2] = 1
    return local


def assert_matrix_equal(test, actual, expected, epsilon=1e-6):
    for row in range(4):
        for col in range(4):
            test.assertAlmostEqual(actual[row][col], expected[row][col], delta=epsilon)


class CreatorStaticSortTransformTests(unittest.TestCase):
    def test_proxy_local_is_inverse_parent_times_source_world_for_reflections_and_nonuniform_rotation(self):
        cases = [
            ("negative-z", (14, -9, 2), (0.4, -0.7, 1.2), (1, 1, -1)),
            ("negative-x", (-3, 5, 11), (-0.5, 0.8, 0.3), (-1, 2, 0.75)),
            ("nonuniform-rotated", (6, 2, -4), (0.2, 1.1, -0.6), (0.5, 2.5, 1.25)),
        ]
        parent = compose((20, -12, 7), (0.35, -0.8, 0.55), (1.5, 0.75, 2.0))
        for name, position, angles, scale in cases:
            with self.subTest(name=name):
                local_source = compose(position, angles, scale)
                source_world = multiply(parent, local_source)
                proxy_local = multiply(inverse(parent), source_world)
                assert_matrix_equal(self, creator_srt_reconstruct(proxy_local), local_source)
                assert_matrix_equal(self, multiply(parent, creator_srt_reconstruct(proxy_local)), source_world)

    def test_zero_scale_axes_and_collapsed_2d_parent_preserve_world_matrix(self):
        rotated_parent = compose((8, -4, 2), (0, 0, 0.35), (1.5, 0.7, 1.0))
        zero_z_source = compose((12, 3, 0), (0, 0, -0.8), (1.2, 0.6, 0.0))
        source_world = multiply(rotated_parent, zero_z_source)
        local = multiply(inverse(rotated_parent), source_world)
        recovered_zero_z = creator_srt_reconstruct_zero_scales(local, [False, False, True])
        assert_matrix_equal(self, recovered_zero_z, zero_z_source)
        assert_matrix_equal(self, multiply(rotated_parent, recovered_zero_z), source_world)

        zero_scale_cases = [
            compose((4, -8, 1), (0.3, -0.5, 0.9), (0.0, 1.5, 0.75)),
            compose((-6, 3, 2), (-0.4, 0.7, -0.2), (1.25, 0.0, -0.5)),
            compose((2, 5, -7), (0.8, 0.2, 1.1), (0.0, 0.0, 1.0)),
            compose((9, -1, 0), (0.1, -0.3, 0.65), (0.0, 0.0, 0.0)),
        ]
        for source in zero_scale_cases:
            local = multiply(inverse(rotated_parent), multiply(rotated_parent, source))
            authored_zero_axes = [all(source[row][col] == 0 for row in range(3)) for col in range(3)]
            recovered = creator_srt_reconstruct_zero_scales(local, authored_zero_axes)
            assert_matrix_equal(self, recovered, source)
            assert_matrix_equal(self, multiply(rotated_parent, recovered), multiply(rotated_parent, source))

        collapsed_parent = compose((20, -12, 0), (0, 0, 0.6), (1.5, 0.75, 0.0))
        child = compose((13, 24, 0), (0, 0, -0.4), (1.0, 1.0, 1.0))
        collapsed_world = multiply(collapsed_parent, child)
        recovered = collapsed_parent_local(collapsed_parent, collapsed_world)
        assert_matrix_equal(self, multiply(collapsed_parent, recovered), collapsed_world)
        self.assertAlmostEqual(collapsed_world[0][3], recovered[0][3] * collapsed_parent[0][0] +
                               recovered[1][3] * collapsed_parent[0][1] + collapsed_parent[0][3], delta=1e-6)

    def test_production_copy_uses_real_world_matrices_and_fails_on_unrepresentable_results(self):
        source = (ROOT / "src/monkey/targets/CreatorStaticSortQueueProxy.ts").read_text()
        self.assertIn("new Mat4(source.worldMatrix)", source)
        self.assertIn("new Mat4(parent.worldMatrix)", source)
        self.assertIn("Mat4.invert(new Mat4(), parentWorld)", source)
        self.assertIn("Mat4.multiply(new Mat4(), parentInverse, sourceWorld)", source)
        self.assertIn("planarLocalForCollapsedParent(parentWorld, sourceWorld, source.name)", source)
        self.assertIn("withSyntheticZeroScaleBasis(localMatrix, source.name, authoredWorldZeroAxes)", source)
        self.assertIn("const zeroAxes = lengths.map((length, index) => length === 0 || authoredWorldZeroAxes?.[index] === true)", source)
        self.assertIn("CREATOR_PROXY_ZERO_SCALE_AXIS_MATRIX_MISMATCH", source)
        self.assertIn("target.setScale(decomposition.zeroAxes[0] ? 0", source)
        self.assertIn("target.matrix = decomposition.matrix", source)
        self.assertIn("matricesMatch(source, target)", source)
        self.assertIn("CREATOR_PROXY_WORLD_MATRIX_NOT_EXACT", source)

    def test_opacity_readback_uses_serialized_local_products_not_batcher_cache(self):
        source = (ROOT / "src/monkey/targets/CreatorStaticSortQueueProxy.ts").read_text()
        self.assertIn("Math.abs(sourceAuthoredOpacityWithinRoot - proxyAuthoredOpacityWithinProxy) <= 1 / 255 + 1e-6", source)
        self.assertIn("const proxyOpacity = new Map<Node, number>([[proxyRoot, 1]])", source)
        self.assertIn("setOpacityProjection(sourceNode, proxyNode, rendererParentOpacity, sourceRoot, proxyRoot)", source)
        self.assertIn("sourceAuthoredOpacityWithinRoot", source)
        self.assertIn("proxyAuthoredOpacityWithinProxy", source)
        self.assertIn("authoredOpacityWithin(source, sourceRoot)", source)
        self.assertIn("opacityPathReadback(source.node", source)
        self.assertIn("sourceOpacityPath, proxyOpacityPath", source)
        props = Path("/Applications/Cocos/Creator/3.8.8/CocosCreator.app/Contents/Resources/resources/3d/engine/cocos/scene-graph/node-ui-properties.ts").read_text()
        batcher = Path("/Applications/Cocos/Creator/3.8.8/CocosCreator.app/Contents/Resources/resources/3d/engine/cocos/2d/renderer/batcher-2d.ts").read_text()
        self.assertIn("private _opacity = 1", props)
        self.assertIn("this._opacity = v", props)
        self.assertIn("uiProps.setOpacity(opacity)", batcher)

    def test_root_layout_fixture_excludes_structural_proxy_without_ui_transform(self):
        source = (ROOT / "src/monkey/targets/CreatorStaticSortQueueProxy.ts").read_text()
        layout = Path("/Applications/Cocos/Creator/3.8.8/CocosCreator.app/Contents/Resources/resources/3d/engine/cocos/ui/layout.ts").read_text()
        self.assertIn("copyWorldNode(sourceRoot, proxyRoot, sourceRoot, sourceRoot.layer, false)", source)
        self.assertIn("!proxyRoot.getComponent(UITransform)", source)
        self.assertIn("const uiTrans = child._getUITransformComp()", layout)
        self.assertIn("if (child.activeInHierarchy && uiTrans)", layout)

        # Neutral authored Layout fixture: adding the generated active root does
        # not change the eligible source-child sequence or any source position.
        original = [("authored-a", True, (13, 24)), ("authored-b", True, (-5, 9))]
        generated = ("sort-proxy", True, None)
        eligible_before = [row for row in original if row[1] and row[2] is not None]
        eligible_after = [row for row in original + [generated] if row[1] and row[2] is not None]
        self.assertEqual(eligible_after, eligible_before)


if __name__ == "__main__":
    unittest.main()
