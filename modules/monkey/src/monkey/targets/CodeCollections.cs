// Typed data helpers for the declared recovery call domain; no source VM.
using System;
using System.Collections.Generic;

namespace __NAMESPACE__ {
public struct Optional<T> {
    readonly bool defined;
    readonly T value;
    public Optional(T item) { defined = true; value = item; }
    public bool HasValue => defined;
    // Values in a declared Map exclude JS null. Missing means undefined.
    public bool IsNotNull => true;
    public T RequireValue() {
        if (!defined) throw new InvalidOperationException("Missing source map value");
        return value;
    }
}

public sealed class OrderedMap<K,V> {
    readonly List<K> keys = new List<K>();
    readonly List<V> values = new List<V>();
    int Find(K key) {
        for (int i = 0; i < keys.Count; i++)
            if (EqualityComparer<K>.Default.Equals(keys[i], key)) return i;
        return -1;
    }
    public Optional<V> Get(K key) {
        int at = Find(key);
        return at < 0 ? default(Optional<V>) : new Optional<V>(values[at]);
    }
    public bool ContainsKey(K key) => Find(key) >= 0;
    public OrderedMap<K,V> Set(K key, V value) {
        int at = Find(key);
        if (at < 0) { keys.Add(key); values.Add(value); }
        else values[at] = value;
        return this;
    }
    public void ForEach(Action<V,K> action) {
        // JS Map iteration visits appended entries and observes updated values.
        // Delete/reinsert and mutation during source recursion are not admitted.
        for (int i = 0; i < keys.Count; i++) action(values[i], keys[i]);
    }
}

public sealed class OrderedSet<T> {
    readonly List<T> values = new List<T>();
    public OrderedSet<T> Add(T item) {
        if (!values.Contains(item)) values.Add(item);
        return this;
    }
    public List<T> ToList() => new List<T>(values);
}

public static class SequenceOrder {
    public static int Append<T>(List<T> items, T item) { items.Add(item); return items.Count; }
    // Source comparators must be pure. Stable insertion order avoids relying on
    // Dictionary/HashSet iteration or the unstable List<T>.Sort implementation.
    public static List<T> StableSort<T>(List<T> items, Func<T,T,double> compare) {
        for (int i = 1; i < items.Count; i++) {
            T item = items[i]; int at = i;
            while (at > 0 && compare(items[at-1], item) > 0) {
                items[at] = items[at-1]; at--;
            }
            items[at] = item;
        }
        return items;
    }
}

public static class NumberMath {
    public static double NumberOrNaN(Optional<double> value) => value.HasValue ? value.RequireValue() : double.NaN;
    public static bool Truth(double value) => value != 0 && !double.IsNaN(value);
    public static double Max(double left, double right) {
        if (double.IsNaN(left) || double.IsNaN(right)) return double.NaN;
        if (left == 0 && right == 0)
            return BitConverter.DoubleToInt64Bits(left) >= 0 || BitConverter.DoubleToInt64Bits(right) >= 0 ? 0d : -0d;
        return left > right ? left : right;
    }
    public static double Min(double left, double right) {
        if (double.IsNaN(left) || double.IsNaN(right)) return double.NaN;
        if (left == 0 && right == 0)
            return BitConverter.DoubleToInt64Bits(left) < 0 || BitConverter.DoubleToInt64Bits(right) < 0 ? -0d : 0d;
        return left < right ? left : right;
    }
}
}
