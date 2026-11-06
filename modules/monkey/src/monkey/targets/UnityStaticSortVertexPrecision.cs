// Editor-only precision helper for static sort mesh snapshots.
// It keeps the existing Unity TransformPoint result as the authority and only
// searches for a better representable local vertex when the current result is
// outside the strict world-space tolerance.
using System;
using UnityEngine;

namespace Monkey.StaticSortQueueProxy
{
    internal static class UnityStaticSortVertexPrecision
    {
        internal const float StrictWorldErrorLimit = 0.001f;
        const double MinimumPivotRatio = 1e-12;
        const double MaximumPivotCondition = 1e10;
        const double MinimumPlaneDeterminantRatio = 1e-12;

        /// <summary>
        /// Express source's local transform in targetParent space using only
        /// the transform chains below their nearest shared ancestor. This
        /// avoids multiplying through a large Canvas/world basis and then
        /// inverting that rounded world matrix.
        /// </summary>
        internal static bool TryGetRelativeMatrixFromCommonAncestor(Transform source,
            Transform targetParent, out Matrix4x4 local)
        {
            local = Matrix4x4.identity;
            if (source == null || targetParent == null) return false;

            var sourceAncestors = new System.Collections.Generic.HashSet<Transform>();
            for (var node = source; node != null; node = node.parent) sourceAncestors.Add(node);
            Transform common = null;
            for (var node = targetParent; node != null; node = node.parent)
                if (sourceAncestors.Contains(node)) { common = node; break; }
            if (common == null) return false;

            if (!TryBuildLocalChain(source, common, out var sourceChain) ||
                !TryBuildLocalChain(targetParent, common, out var targetChain)) return false;
            return TryGetRelativeMatrixFromCommonAncestor(sourceChain, targetChain, out local);
        }

        // Matrix-level overload keeps the exact same calculation testable
        // against Unity's real Matrix4x4 implementation without creating
        // Editor-only Transform instances.
        internal static bool TryGetRelativeMatrixFromCommonAncestor(Matrix4x4 sourceChain,
            Matrix4x4 targetChain, out Matrix4x4 local)
        {
            local = Matrix4x4.identity;
            if (!Finite(sourceChain) || !Finite(targetChain)) return false;
            if (MatrixExactlyIdentity(targetChain))
            {
                local = sourceChain;
                return true;
            }

            if (!TryInvertMatrix(targetChain, out var inverse)) return false;
            var result = inverse * sourceChain;
            if (!Finite(result)) return false;
            local = result;
            return true;
        }

        static bool TryInvertMatrix(Matrix4x4 matrix, out Matrix4x4 inverse)
        {
            inverse = Matrix4x4.identity;
            var values = new double[4, 8];
            for (var row = 0; row < 4; row++)
            {
                for (var column = 0; column < 4; column++) values[row, column] = matrix[row, column];
                values[row, row + 4] = 1.0;
            }

            for (var column = 0; column < 4; column++)
            {
                var pivotRow = column;
                var pivotMagnitude = Math.Abs(values[column, column]);
                for (var row = column + 1; row < 4; row++)
                {
                    var candidate = Math.Abs(values[row, column]);
                    if (candidate > pivotMagnitude) { pivotMagnitude = candidate; pivotRow = row; }
                }
                if (!(pivotMagnitude > 0.0) || !Finite(pivotMagnitude)) return false;
                if (pivotRow != column)
                    for (var index = 0; index < 8; index++)
                    { var swap = values[column, index]; values[column, index] = values[pivotRow, index]; values[pivotRow, index] = swap; }
                var pivot = values[column, column];
                for (var index = 0; index < 8; index++) values[column, index] /= pivot;
                for (var row = 0; row < 4; row++)
                {
                    if (row == column) continue;
                    var factor = values[row, column];
                    for (var index = 0; index < 8; index++) values[row, index] -= factor * values[column, index];
                }
            }

            var candidateInverse = new Matrix4x4();
            for (var row = 0; row < 4; row++)
            for (var column = 0; column < 4; column++)
            {
                var value = values[row, column + 4];
                if (!Finite(value) || value > Single.MaxValue || value < -Single.MaxValue) return false;
                candidateInverse[row, column] = (float)value;
            }
            if (!Finite(candidateInverse)) return false;
            inverse = candidateInverse;
            return true;
        }

        static bool TryBuildLocalChain(Transform start, Transform stopExclusive, out Matrix4x4 chain)
        {
            chain = Matrix4x4.identity;
            if (start == null || stopExclusive == null) return false;
            for (var node = start; node != stopExclusive; node = node.parent)
            {
                if (node == null) { chain = Matrix4x4.identity; return false; }
                var local = Matrix4x4.TRS(node.localPosition, node.localRotation, node.localScale);
                if (!Finite(local)) { chain = Matrix4x4.identity; return false; }
                chain = local * chain;
                if (!Finite(chain)) { chain = Matrix4x4.identity; return false; }
            }
            return true;
        }

        static bool MatrixExactlyIdentity(Matrix4x4 matrix)
        {
            return matrix.m00 == 1f && matrix.m01 == 0f && matrix.m02 == 0f && matrix.m03 == 0f &&
                matrix.m10 == 0f && matrix.m11 == 1f && matrix.m12 == 0f && matrix.m13 == 0f &&
                matrix.m20 == 0f && matrix.m21 == 0f && matrix.m22 == 1f && matrix.m23 == 0f &&
                matrix.m30 == 0f && matrix.m31 == 0f && matrix.m32 == 0f && matrix.m33 == 1f;
        }

        /// <summary>
        /// Return the finite local point with the smallest measured Unity
        /// TransformPoint error. The initial point remains the fallback and is
        /// returned unchanged when it already satisfies the strict gate or no
        /// candidate improves it.
        /// </summary>
        internal static Vector3 ImproveInitialLocalPoint(Transform target, Vector3 desiredWorld,
            Vector3 initialLocal, out float measuredWorldError)
        {
            measuredWorldError = Single.PositiveInfinity;
            var bestLocal = initialLocal;
            if (target == null || !Finite(initialLocal) || !Finite(desiredWorld)) return bestLocal;

            return ImproveInitialLocalPoint(target.TransformPoint, target.localToWorldMatrix,
                desiredWorld, initialLocal, out measuredWorldError);
        }

        // Kept separately so the pure matrix/float path can be exercised with
        // Unity's real Vector3 and Matrix4x4 types without creating an Editor
        // Transform or opening a Unity project.
        internal static Vector3 ImproveInitialLocalPoint(Func<Vector3, Vector3> transformPoint,
            Matrix4x4 localToWorld, Vector3 desiredWorld, Vector3 initialLocal, out float measuredWorldError)
        {
            measuredWorldError = Single.PositiveInfinity;
            var bestLocal = initialLocal;
            if (transformPoint == null || !Finite(initialLocal) || !Finite(desiredWorld)) return bestLocal;

            if (!TryMeasure(transformPoint, desiredWorld, initialLocal, out measuredWorldError))
                measuredWorldError = Single.PositiveInfinity;
            if (!(measuredWorldError > StrictWorldErrorLimit)) return bestLocal;
            var initialError = measuredWorldError;
            var bestError = initialError;

            var matrix = localToWorld;
            if (!Finite(matrix)) return bestLocal;

            if (TrySolveAbsolute(matrix, desiredWorld, initialLocal, out var idealLocal))
                EvaluateNeighborhood(transformPoint, desiredWorld, idealLocal, ref bestLocal, ref bestError);

            // One residual correction compensates for the final float vertex
            // cast and Unity's actual TransformPoint arithmetic.
            if (TryMeasure(transformPoint, desiredWorld, bestLocal, out var currentError) &&
                currentError > StrictWorldErrorLimit)
            {
                var actualWorld = transformPoint(bestLocal);
                if (Finite(actualWorld))
                {
                    var residual = new Vector3(desiredWorld.x - actualWorld.x,
                        desiredWorld.y - actualWorld.y, desiredWorld.z - actualWorld.z);
                    if (Finite(residual) && TrySolveDelta(matrix, residual, out var delta))
                    {
                        var corrected = new Vector3((float)((double)bestLocal.x + delta.x),
                            (float)((double)bestLocal.y + delta.y), (float)((double)bestLocal.z + delta.z));
                        if (Finite(corrected))
                            EvaluateNeighborhood(transformPoint, desiredWorld, corrected, ref bestLocal, ref bestError);
                    }
                }
            }

            // Never replace the original with an equal or worse candidate.
            if (!(bestError < initialError))
                return initialLocal;
            measuredWorldError = bestError;
            return bestLocal;
        }

        static void EvaluateNeighborhood(Func<Vector3, Vector3> transformPoint, Vector3 desiredWorld, Vector3 center,
            ref Vector3 bestLocal, ref float bestError)
        {
            if (!Finite(center)) return;
            var xs = new[] { NextFloat(center.x, false), center.x, NextFloat(center.x, true) };
            var ys = new[] { NextFloat(center.y, false), center.y, NextFloat(center.y, true) };
            var zs = new[] { NextFloat(center.z, false), center.z, NextFloat(center.z, true) };
            for (var xi = 0; xi < xs.Length; xi++)
            for (var yi = 0; yi < ys.Length; yi++)
            for (var zi = 0; zi < zs.Length; zi++)
            {
                var candidate = new Vector3(xs[xi], ys[yi], zs[zi]);
                if (!Finite(candidate) || !TryMeasure(transformPoint, desiredWorld, candidate, out var error)) continue;
                if (error < bestError)
                {
                    bestError = error;
                    bestLocal = candidate;
                }
            }
        }

        static bool TryMeasure(Func<Vector3, Vector3> transformPoint, Vector3 desiredWorld,
            Vector3 local, out float error)
        {
            error = Single.PositiveInfinity;
            if (transformPoint == null || !Finite(desiredWorld) || !Finite(local)) return false;
            try
            {
                var actual = transformPoint(local);
                if (!Finite(actual)) return false;
                var delta = actual - desiredWorld;
                if (!Finite(delta)) return false;
                error = delta.magnitude;
                return Finite(error);
            }
            catch { return false; }
        }

        static bool TrySolveAbsolute(Matrix4x4 matrix, Vector3 desiredWorld, Vector3 fixedLocal,
            out Vector3 local)
        {
            local = fixedLocal;
            var a = new double[3, 3]
            {
                { matrix.m00, matrix.m01, matrix.m02 },
                { matrix.m10, matrix.m11, matrix.m12 },
                { matrix.m20, matrix.m21, matrix.m22 },
            };
            var b = new double[3]
            {
                (double)desiredWorld.x - matrix.m03,
                (double)desiredWorld.y - matrix.m13,
                (double)desiredWorld.z - matrix.m23,
            };
            if (TrySolve3(a, b, out var solved))
            {
                var candidate = new Vector3((float)solved[0], (float)solved[1], (float)solved[2]);
                if (!Finite(candidate)) return false;
                local = candidate;
                return true;
            }

            // A zero-depth UI Transform is singular in 3D but still has an
            // invertible XY plane. Preserve the existing local Z and solve
            // only the observable X/Y coordinates in double precision.
            var zColumn = new Vector3(matrix.m02, matrix.m12, matrix.m22);
            var xyScale = Math.Max(Math.Abs(matrix.m00) + Math.Abs(matrix.m01),
                Math.Max(Math.Abs(matrix.m10) + Math.Abs(matrix.m11), Math.Abs(matrix.m20) + Math.Abs(matrix.m21)));
            if (!(xyScale > 0.0) || !Finite(xyScale) || MagnitudeSquared(zColumn) > xyScale * xyScale * 1e-20) return false;
            var originZ = new Vector3(matrix.m02 * fixedLocal.z, matrix.m12 * fixedLocal.z, matrix.m22 * fixedLocal.z);
            var offset = new Vector3(matrix.m03 + originZ.x, matrix.m13 + originZ.y, matrix.m23 + originZ.z);
            var dx = (double)desiredWorld.x - offset.x;
            var dy = (double)desiredWorld.y - offset.y;
            var dz = (double)desiredWorld.z - offset.z;
            var xColumn = new Vector3(matrix.m00, matrix.m10, matrix.m20);
            var yColumn = new Vector3(matrix.m01, matrix.m11, matrix.m21);
            var xx = Dot(xColumn, xColumn);
            var xy = Dot(xColumn, yColumn);
            var yy = Dot(yColumn, yColumn);
            var determinant = xx * yy - xy * xy;
            var determinantScale = xx * yy;
            if (!Finite(xx) || !Finite(xy) || !Finite(yy) || !Finite(determinant) || !(determinantScale > 0.0) ||
                determinant <= determinantScale * MinimumPlaneDeterminantRatio) return false;
            var bx = xColumn.x * dx + xColumn.y * dy + xColumn.z * dz;
            var by = yColumn.x * dx + yColumn.y * dy + yColumn.z * dz;
            var solvedX = (bx * yy - by * xy) / determinant;
            var solvedY = (by * xx - bx * xy) / determinant;
            var planeCandidate = new Vector3((float)solvedX, (float)solvedY, fixedLocal.z);
            if (!Finite(planeCandidate)) return false;
            local = planeCandidate;
            return true;
        }

        static bool TrySolveDelta(Matrix4x4 matrix, Vector3 residual, out Vector3 delta)
        {
            delta = Vector3.zero;
            var a = new double[3, 3]
            {
                { matrix.m00, matrix.m01, matrix.m02 },
                { matrix.m10, matrix.m11, matrix.m12 },
                { matrix.m20, matrix.m21, matrix.m22 },
            };
            var b = new double[3] { residual.x, residual.y, residual.z };
            if (TrySolve3(a, b, out var solved))
            {
                delta = new Vector3((float)solved[0], (float)solved[1], (float)solved[2]);
                return Finite(delta);
            }

            var zColumn = new Vector3(matrix.m02, matrix.m12, matrix.m22);
            var xyScale = Math.Max(Math.Abs(matrix.m00) + Math.Abs(matrix.m01),
                Math.Max(Math.Abs(matrix.m10) + Math.Abs(matrix.m11), Math.Abs(matrix.m20) + Math.Abs(matrix.m21)));
            if (!(xyScale > 0.0) || !Finite(xyScale) || MagnitudeSquared(zColumn) > xyScale * xyScale * 1e-20) return false;
            var xColumn = new Vector3(matrix.m00, matrix.m10, matrix.m20);
            var yColumn = new Vector3(matrix.m01, matrix.m11, matrix.m21);
            var xx = Dot(xColumn, xColumn);
            var xy = Dot(xColumn, yColumn);
            var yy = Dot(yColumn, yColumn);
            var determinant = xx * yy - xy * xy;
            var determinantScale = xx * yy;
            if (!Finite(determinant) || !(determinantScale > 0.0) ||
                determinant <= determinantScale * MinimumPlaneDeterminantRatio) return false;
            var bx = Dot(xColumn, residual);
            var by = Dot(yColumn, residual);
            var solvedX = (bx * yy - by * xy) / determinant;
            var solvedY = (by * xx - bx * xy) / determinant;
            delta = new Vector3((float)solvedX, (float)solvedY, 0f);
            return Finite(delta);
        }

        static bool TrySolve3(double[,] coefficients, double[] right, out double[] solution)
        {
            solution = null;
            var values = new double[3, 4];
            var maxCoefficient = 0.0;
            for (var row = 0; row < 3; row++)
            {
                for (var column = 0; column < 3; column++)
                {
                    var value = coefficients[row, column];
                    if (!Finite(value)) return false;
                    values[row, column] = value;
                    maxCoefficient = Math.Max(maxCoefficient, Math.Abs(value));
                }
                if (!Finite(right[row])) return false;
                values[row, 3] = right[row];
            }
            if (!(maxCoefficient > 0.0) || !Finite(maxCoefficient)) return false;
            var minPivot = Double.PositiveInfinity;
            var maxPivot = 0.0;
            for (var column = 0; column < 3; column++)
            {
                var pivotRow = column;
                var pivotMagnitude = Math.Abs(values[column, column]);
                for (var row = column + 1; row < 3; row++)
                {
                    var candidate = Math.Abs(values[row, column]);
                    if (candidate > pivotMagnitude) { pivotMagnitude = candidate; pivotRow = row; }
                }
                if (!(pivotMagnitude > maxCoefficient * MinimumPivotRatio) || !Finite(pivotMagnitude)) return false;
                if (pivotRow != column)
                    for (var index = column; index < 4; index++)
                    { var swap = values[column, index]; values[column, index] = values[pivotRow, index]; values[pivotRow, index] = swap; }
                var pivot = values[column, column];
                var absolutePivot = Math.Abs(pivot);
                minPivot = Math.Min(minPivot, absolutePivot);
                maxPivot = Math.Max(maxPivot, absolutePivot);
                for (var index = column; index < 4; index++) values[column, index] /= pivot;
                for (var row = 0; row < 3; row++)
                {
                    if (row == column) continue;
                    var factor = values[row, column];
                    for (var index = column; index < 4; index++) values[row, index] -= factor * values[column, index];
                }
            }
            if (!(minPivot > 0.0) || maxPivot / minPivot > MaximumPivotCondition) return false;
            solution = new[] { values[0, 3], values[1, 3], values[2, 3] };
            return Finite(solution[0]) && Finite(solution[1]) && Finite(solution[2]);
        }

        static float NextFloat(float value, bool upward)
        {
            if (!Finite(value)) return value;
            if (value == 0f) return upward ? BitConverter.ToSingle(BitConverter.GetBytes(1), 0) :
                BitConverter.ToSingle(BitConverter.GetBytes(unchecked((int)0x80000001)), 0);
            var bits = BitConverter.ToInt32(BitConverter.GetBytes(value), 0);
            bits += ((value > 0f) == upward) ? 1 : -1;
            return BitConverter.ToSingle(BitConverter.GetBytes(bits), 0);
        }

        static double Dot(Vector3 left, Vector3 right)
        { return (double)left.x * right.x + (double)left.y * right.y + (double)left.z * right.z; }
        static double MagnitudeSquared(Vector3 value) { return Dot(value, value); }
        static bool Finite(Vector3 value) { return Finite(value.x) && Finite(value.y) && Finite(value.z); }
        static bool Finite(Matrix4x4 value)
        {
            return Finite(value.m00) && Finite(value.m01) && Finite(value.m02) && Finite(value.m03) &&
                Finite(value.m10) && Finite(value.m11) && Finite(value.m12) && Finite(value.m13) &&
                Finite(value.m20) && Finite(value.m21) && Finite(value.m22) && Finite(value.m23) &&
                Finite(value.m30) && Finite(value.m31) && Finite(value.m32) && Finite(value.m33);
        }
        static bool Finite(float value) { return !Single.IsNaN(value) && !Single.IsInfinity(value); }
        static bool Finite(double value) { return !Double.IsNaN(value) && !Double.IsInfinity(value); }
    }
}
