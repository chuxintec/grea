import glob
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "src/monkey/targets/UnityStaticSortVertexPrecision.cs"
UNITY_EDITOR = Path("/Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents")
UNITY_CSC = UNITY_EDITOR / "Resources/Scripting/DotNetSdk/sdk/8.0.318/Roslyn/bincore/csc.dll"
UNITY_ENGINE = UNITY_EDITOR / "Resources/Scripting/Managed/UnityEngine"
DOTNET = shutil.which("dotnet")


HARNESS = r"""
using System;
using UnityEngine;
using Monkey.StaticSortQueueProxy;

static class Check
{
    static Vector3 Apply(Matrix4x4 matrix, Vector3 point) => new Vector3(
        matrix.m00 * point.x + matrix.m01 * point.y + matrix.m02 * point.z + matrix.m03,
        matrix.m10 * point.x + matrix.m11 * point.y + matrix.m12 * point.z + matrix.m13,
        matrix.m20 * point.x + matrix.m21 * point.y + matrix.m22 * point.z + matrix.m23);

    static Vector3 OldFloatInverse(Matrix4x4 matrix, Vector3 world)
    {
        float determinant = matrix.m00 * matrix.m11 - matrix.m01 * matrix.m10;
        float x = world.x - matrix.m03;
        float y = world.y - matrix.m13;
        return new Vector3((matrix.m11 * x - matrix.m01 * y) / determinant,
            (-matrix.m10 * x + matrix.m00 * y) / determinant, 0f);
    }

    static int LargeCoordinatesImproveWithoutRelaxingGate()
    {
        var random = new System.Random(1);
        float angle = .000213f;
        float cosine = (float)Math.Cos(angle);
        float sine = (float)Math.Sin(angle);
        for (int exponent = 10; exponent <= 13; exponent++)
        {
            float translation = (float)Math.Pow(2, exponent);
            var source = Matrix4x4.identity;
            var target = Matrix4x4.identity;
            source.m00 = .15f; source.m11 = .15f;
            source.m03 = translation; source.m13 = -translation;
            target.m00 = .14999999f * cosine;
            target.m01 = -.14999999f * sine;
            target.m10 = .14999999f * sine;
            target.m11 = .14999999f * cosine;
            target.m03 = translation - .00048828125f;
            target.m13 = -translation + .00048828125f;

            for (int index = 0; index < 100000; index++)
            {
                var sourcePoint = new Vector3((float)(random.NextDouble() * 38000 - 19000),
                    (float)(random.NextDouble() * 45000 - 22500), 0f);
                var desired = Apply(source, sourcePoint);
                var initial = OldFloatInverse(target, desired);
                var oldError = (Apply(target, initial) - desired).magnitude;
                if (!(oldError > UnityStaticSortVertexPrecision.StrictWorldErrorLimit)) continue;

                var improved = UnityStaticSortVertexPrecision.ImproveInitialLocalPoint(
                    point => Apply(target, point), target, desired, initial, out var measured);
                if (measured < oldError && measured <= UnityStaticSortVertexPrecision.StrictWorldErrorLimit &&
                    Finite(improved) && Finite(measured)) return 0;
            }
        }
        return 2;
    }

    static int EqualMatrixDifferentTransformChainsAreMeasured()
    {
        var parent = Affine(789.5f, 1029.044f, 0f, .33f, 0f, 0f, .33f);
        var angle = .000213f;
        var child = Affine(0.00006103515625f, -0.000030517578125f, 0f,
            (float)Math.Cos(angle), -(float)Math.Sin(angle),
            (float)Math.Sin(angle), (float)Math.Cos(angle));
        var combined = parent * child;
        var random = new System.Random(97);
        for (var i = 0; i < 100000; i++)
        {
            var sourcePoint = new Vector3((float)(random.NextDouble() * 60000 - 30000),
                (float)(random.NextDouble() * 50000 - 25000), 0f);
            var desired = Apply(parent, Apply(child, sourcePoint));
            var initialError = (Apply(combined, sourcePoint) - desired).magnitude;
            if (!(initialError > UnityStaticSortVertexPrecision.StrictWorldErrorLimit)) continue;
            var improved = UnityStaticSortVertexPrecision.ImproveInitialLocalPoint(
                point => Apply(combined, point), combined, desired, sourcePoint, out var measured);
            if (measured < initialError && measured <= UnityStaticSortVertexPrecision.StrictWorldErrorLimit &&
                Finite(improved)) return 0;
        }
        return 13;
    }

    static int GoodInitialPointIsUnchanged()
    {
        var matrix = Matrix4x4.identity;
        matrix.m00 = .15f; matrix.m11 = .15f; matrix.m03 = 52f; matrix.m13 = -40f;
        var initial = new Vector3(19f, -20f, 0f);
        var desired = Apply(matrix, initial);
        var result = UnityStaticSortVertexPrecision.ImproveInitialLocalPoint(
            point => Apply(matrix, point), matrix, desired, initial, out var error);
        return result.Equals(initial) && error <= UnityStaticSortVertexPrecision.StrictWorldErrorLimit ? 0 : 3;
    }

    static int DegenerateUiPlaneCanBeSolved()
    {
        var matrix = Matrix4x4.identity;
        matrix.m00 = .25f; matrix.m11 = .5f; matrix.m22 = 0f;
        matrix.m03 = 31f; matrix.m13 = -17f; matrix.m23 = 4f;
        var exact = new Vector3(19000.125f, -22000.25f, 0f);
        var desired = Apply(matrix, exact);
        var initial = new Vector3(exact.x + 2f, exact.y - 3f, 0f);
        var improved = UnityStaticSortVertexPrecision.ImproveInitialLocalPoint(
            point => Apply(matrix, point), matrix, desired, initial, out var error);
        return error < .001f && Finite(improved) ? 0 : 4;
    }

    static int IllConditionedAndNonFiniteMatricesFailSafe()
    {
        var illConditioned = Matrix4x4.identity;
        illConditioned.m00 = 1e-14f;
        var initial = new Vector3(2f, 3f, 4f);
        var desired = new Vector3(10f, 3f, 4f);
        var result = UnityStaticSortVertexPrecision.ImproveInitialLocalPoint(
            point => Apply(illConditioned, point), illConditioned, desired, initial, out var ignoredError);
        if (!result.Equals(initial) || !Finite(result)) return 5;

        var invalid = Matrix4x4.identity;
        invalid.m00 = Single.NaN;
        result = UnityStaticSortVertexPrecision.ImproveInitialLocalPoint(
            point => point, invalid, new Vector3(10f, 20f, 30f), initial, out ignoredError);
        return result.Equals(initial) && Finite(result) ? 0 : 6;
    }

    static bool MatrixNear(Matrix4x4 left, Matrix4x4 right, float tolerance)
    {
        for (int row = 0; row < 4; row++)
        for (int column = 0; column < 4; column++)
            if (Math.Abs(left[row, column] - right[row, column]) > tolerance) return false;
        return true;
    }

    static Matrix4x4 Affine(float x, float y, float z, float m00, float m01,
        float m10, float m11, float m22 = 1f)
    {
        var result = Matrix4x4.identity;
        result.m00 = m00; result.m01 = m01; result.m03 = x;
        result.m10 = m10; result.m11 = m11; result.m13 = y;
        result.m22 = m22; result.m23 = z;
        return result;
    }

    static int RelativeMatrixWithIdentityTargetKeepsNestedLocalChain()
    {
        var sourceParent = Affine(0f, 387.5f, 0f, .7f, 0f, 0f, .7f);
        var sourceNode = Affine(3f, -5f, 0f, 1f, 0f, 0f, 1f);
        // The routine receives below-common-ancestor chains, so the shared
        // (large/scaled) ancestor must not contaminate the relative result.
        var sourceChain = sourceParent * sourceNode;
        if (!UnityStaticSortVertexPrecision.TryGetRelativeMatrixFromCommonAncestor(
            sourceChain, Matrix4x4.identity, out var local)) return 7;
        return local.Equals(sourceChain) ? 0 : 8;
    }

    static int RelativeMatrixUsesLocalTargetInverse()
    {
        float sourceAngle = .12f;
        var sourceChild = Affine(3f, -5f, 0f, 1.2f * (float)Math.Cos(sourceAngle),
            -.8f * (float)Math.Sin(sourceAngle), 1.2f * (float)Math.Sin(sourceAngle),
            .8f * (float)Math.Cos(sourceAngle));
        var sourceChain = Affine(0f, 387.5f, 0f, .7f, 0f, 0f, .7f) * sourceChild;
        float targetAngle = -.04f;
        var targetChain = Affine(23f, -11f, 0f, 1.1f * (float)Math.Cos(targetAngle),
            -.9f * (float)Math.Sin(targetAngle), 1.1f * (float)Math.Sin(targetAngle),
            .9f * (float)Math.Cos(targetAngle));
        if (!UnityStaticSortVertexPrecision.TryGetRelativeMatrixFromCommonAncestor(
            sourceChain, targetChain, out var local)) return 9;
        return MatrixNear(targetChain * local, sourceChain, .0001f) ? 0 : 10;
    }

    static int RelativeMatrixRejectsSingularAndNonFiniteTarget()
    {
        var sourceChain = Affine(1f, 2f, 3f, 1f, 0f, 0f, 1f);
        var singular = Affine(0f, 0f, 0f, 1f, 0f, 0f, 0f);
        if (UnityStaticSortVertexPrecision.TryGetRelativeMatrixFromCommonAncestor(
            sourceChain, singular, out _)) return 11;
        var nonFinite = Matrix4x4.identity;
        nonFinite.m12 = Single.NaN;
        return UnityStaticSortVertexPrecision.TryGetRelativeMatrixFromCommonAncestor(
            sourceChain, nonFinite, out _) ? 12 : 0;
    }

    static bool Finite(Vector3 value) => Finite(value.x) && Finite(value.y) && Finite(value.z);
    static bool Finite(float value) => !Single.IsNaN(value) && !Single.IsInfinity(value);

    static int Main()
    {
        var result = LargeCoordinatesImproveWithoutRelaxingGate();
        if (result != 0) return result;
        result = EqualMatrixDifferentTransformChainsAreMeasured();
        if (result != 0) return result;
        result = GoodInitialPointIsUnchanged();
        if (result != 0) return result;
        result = DegenerateUiPlaneCanBeSolved();
        if (result != 0) return result;
        result = IllConditionedAndNonFiniteMatricesFailSafe();
        if (result != 0) return result;
        result = RelativeMatrixWithIdentityTargetKeepsNestedLocalChain();
        if (result != 0) return result;
        result = RelativeMatrixUsesLocalTargetInverse();
        if (result != 0) return result;
        return RelativeMatrixRejectsSingularAndNonFiniteTarget();
    }
}
"""


@unittest.skipUnless(DOTNET and UNITY_CSC.is_file() and
                     (UNITY_ENGINE / "UnityEngine.CoreModule.dll").is_file(),
                     "Unity 6000.6.2f1 CoreModule and dotnet are required")
class UnityStaticSortVertexPrecisionTests(unittest.TestCase):
    def test_helper_against_unity_vector_and_matrix_types_without_editor(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            harness = work / "Check.cs"
            harness.write_text(HARNESS, encoding="utf-8")
            dotnet_version = Path(DOTNET).resolve().parents[1]
            reference_packs = sorted((dotnet_version / "libexec/packs/Microsoft.NETCore.App.Ref").glob("*/ref/net8.0"))
            ref_dir = reference_packs[-1] if reference_packs else None
            if ref_dir is None or not ref_dir.is_dir():
                self.skipTest(".NET 8 reference assemblies are unavailable")
            references = sorted(ref_dir.glob("*.dll"))
            references.append(UNITY_ENGINE / "UnityEngine.CoreModule.dll")
            assembly = work / "Check.dll"
            response = work / "compile.rsp"
            response.write_text("\n".join([
                "-nologo", "-target:exe", f'-out:"{assembly}"',
                *[f'-r:"{reference}"' for reference in references],
                f'"{HELPER}"', f'"{harness}"',
            ]) + "\n", encoding="utf-8")
            compiled = subprocess.run([DOTNET, str(UNITY_CSC), "@" + str(response)],
                                      capture_output=True, text=True, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)

            (work / "Check.runtimeconfig.json").write_text(
                '{"runtimeOptions":{"tfm":"net8.0","framework":{"name":"Microsoft.NETCore.App","version":"8.0.0"}}}',
                encoding="utf-8")
            # Matrix/Vector operations are managed and do not require an Editor.
            for module in UNITY_ENGINE.glob("UnityEngine.*Module.dll"):
                shutil.copy2(module, work / module.name)
            ran = subprocess.run([DOTNET, str(assembly)], cwd=work,
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_contract_keeps_strict_gate_and_actual_transform_measurement(self):
        source = HELPER.read_text(encoding="utf-8")
        self.assertIn("StrictWorldErrorLimit = 0.001f", source)
        self.assertIn("if (!(measuredWorldError > StrictWorldErrorLimit)) return bestLocal;", source)
        self.assertIn("target.TransformPoint", source)
        self.assertIn("TryGetRelativeMatrixFromCommonAncestor(Transform source", source)
        self.assertIn("MatrixExactlyIdentity(targetChain)", source)
        self.assertIn("Never replace the original with an equal or worse candidate", source)
        self.assertNotIn("SnapToPixel", source)


if __name__ == "__main__":
    unittest.main()
