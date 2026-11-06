using System;
using System.Collections.Generic;

namespace {{NAMESPACE}}
{
    public static class PureSequence
    {
        public static double RequireFinite(double value, string location)
        {
            if (double.IsNaN(value) || double.IsInfinity(value))
                throw new InvalidOperationException("Non-finite Number at " + location + ".");
            return value;
        }

        public static List<T> Filter<T>(IReadOnlyList<T> items, Func<T, bool> predicate)
        {
            if (items == null) throw new ArgumentNullException(nameof(items));
            if (predicate == null) throw new ArgumentNullException(nameof(predicate));
            var result = new List<T>();
            for (var i = 0; i < items.Count; i++)
                if (predicate(items[i])) result.Add(items[i]);
            return result;
        }

        public static List<T> StableSort<T>(IReadOnlyList<T> items, Func<T, T, double> compare)
        {
            if (items == null) throw new ArgumentNullException(nameof(items));
            if (compare == null) throw new ArgumentNullException(nameof(compare));
            var result = new List<T>(items.Count);
            for (var i = 0; i < items.Count; i++) result.Add(items[i]);
            for (var i = 1; i < result.Count; i++)
            {
                var value = result[i];
                var cursor = i - 1;
                while (cursor >= 0)
                {
                    var order = RequireFinite(compare(result[cursor], value), "sort comparator");
                    if (order <= 0) break;
                    result[cursor + 1] = result[cursor];
                    cursor--;
                }
                result[cursor + 1] = value;
            }
            return result;
        }
    }
}
