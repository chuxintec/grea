// Finite pinned configuration adapter; not a source runtime or complete Kp recovery.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
#if UNITY_5_3_OR_NEWER
using UnityEngine;
#endif

namespace Game.Domain.Recovered {
public static class RecipeJsonConfiguration {
    const double MaxSafeInteger = 9007199254740991d;
    const int MaxJsonBytes = 4 * 1024 * 1024;
    const int MaxJsonDepth = 64;
    const int MaxRows = 10000;
    const int MaxEntriesPerMap = 10000;
    const int MaxTotalMapEntries = 200000;

#if UNITY_5_3_OR_NEWER
    public static OrderedMap<double, Recipe> Load(TextAsset asset) {
        if (asset == null) throw new ArgumentNullException(nameof(asset));
        return Load(asset.text);
    }
#endif

    public static OrderedMap<double, Recipe> Load(string json) {
        if (json == null) throw new ArgumentNullException(nameof(json));
        if (Encoding.UTF8.GetByteCount(json) > MaxJsonBytes)
            throw new InvalidDataException("Recipe JSON exceeds the declared 4 MiB limit.");
        var rows = new JsonReader(json).ReadTable();
        if (rows.Count == 0 || rows.Count > MaxRows)
            throw new InvalidDataException("Recipe JSON must contain 1..10000 rows.");

        var result = new OrderedMap<double, Recipe>();
        var rowIds = new HashSet<double>();
        foreach (var row in rows) {
            if (!rowIds.Add(row.Id))
                throw new InvalidDataException("Duplicate source row id: " + row.Id.ToString(CultureInfo.InvariantCulture));
            if (result.ContainsKey(row.Dish))
                throw new InvalidDataException("Duplicate dish id: " + row.Dish.ToString(CultureInfo.InvariantCulture));
            var ingredients = new OrderedMap<double, double>();
            foreach (var entry in OrderMapEntries(row.NeedElements)) {
                double ingredientId = ParseNumericKey(entry.Key, false);
                if (ingredients.ContainsKey(ingredientId))
                    throw new InvalidDataException("Ingredient keys collide after Number conversion: " + entry.Key);
                ingredients.Set(ingredientId, entry.Value);
            }
            result.Set(row.Dish, new Recipe { ingredients = ingredients });
        }
        ValidateAcyclic(result);
        return result;
    }

    static List<NumberEntry> OrderMapEntries(List<NumberEntry> entries) {
        var indexed = new List<NumberEntry>();
        var other = new List<NumberEntry>();
        foreach (var entry in entries) {
            uint index;
            if (TryArrayIndex(entry.Key, out index)) indexed.Add(entry);
            else other.Add(entry);
        }
        indexed.Sort((left, right) => ParseArrayIndex(left.Key).CompareTo(ParseArrayIndex(right.Key)));
        indexed.AddRange(other);
        return indexed;
    }

    static void ValidateAcyclic(OrderedMap<double, Recipe> recipes) {
        var dishes = new List<double>();
        var adjacency = new Dictionary<double, List<double>>();
        recipes.ForEach((recipe, dish) => {
            dishes.Add(dish);
            var edges = new List<double>();
            recipe.ingredients.ForEach((quantity, ingredient) => {
                if (recipes.ContainsKey(ingredient)) edges.Add(ingredient);
            });
            adjacency.Add(dish, edges);
        });
        var state = new Dictionary<double, int>();
        var active = new HashSet<double>();
        foreach (double start in dishes) {
            if (GetState(state, start) != 0) continue;
            var frames = new List<Frame> { new Frame(start, 0) };
            state[start] = 1;
            active.Add(start);
            while (frames.Count > 0) {
                int last = frames.Count - 1;
                Frame frame = frames[last];
                List<double> edges = adjacency[frame.Dish];
                if (frame.Next >= edges.Count) {
                    frames.RemoveAt(last);
                    active.Remove(frame.Dish);
                    state[frame.Dish] = 2;
                    continue;
                }
                double child = edges[frame.Next];
                frames[last] = new Frame(frame.Dish, frame.Next + 1);
                int childState = GetState(state, child);
                if (childState == 1 || active.Contains(child))
                    throw new InvalidDataException("Recipe cycle detected at dish " + child.ToString(CultureInfo.InvariantCulture));
                if (childState == 0) {
                    state[child] = 1;
                    active.Add(child);
                    frames.Add(new Frame(child, 0));
                }
            }
        }
    }

    static int GetState(Dictionary<double, int> states, double dish) {
        int state;
        return states.TryGetValue(dish, out state) ? state : 0;
    }

    static bool TryArrayIndex(string key, out uint index) {
        index = 0;
        if (String.IsNullOrEmpty(key) || (key.Length > 1 && key[0] == '0')) return false;
        for (int i = 0; i < key.Length; i++)
            if (key[i] < '0' || key[i] > '9') return false;
        if (!UInt32.TryParse(key, NumberStyles.None, CultureInfo.InvariantCulture, out index)) return false;
        return index <= 4294967294U;
    }

    static ulong ParseArrayIndex(string key) {
        return UInt64.Parse(key, NumberStyles.None, CultureInfo.InvariantCulture);
    }

    static double ParseNumericKey(string key, bool weightPrefix) {
        string token = weightPrefix ? key.Split('_')[0] : key;
        if (String.IsNullOrEmpty(token)) throw new InvalidDataException("Empty numeric map key.");
        for (int i = 0; i < token.Length; i++)
            if (token[i] < '0' || token[i] > '9')
                throw new InvalidDataException("Unsupported numeric map key: " + key);
        double value;
        if (!Double.TryParse(token, NumberStyles.None, CultureInfo.InvariantCulture, out value) ||
            !IsSafeInteger(value))
            throw new InvalidDataException("Unsafe numeric map key: " + key);
        return value;
    }

    static bool IsSafeInteger(double value) {
        return IsFinite(value) && Math.Truncate(value) == value && Math.Abs(value) <= MaxSafeInteger;
    }

    static bool IsFinite(double value) {
        return !Double.IsNaN(value) && !Double.IsInfinity(value);
    }

    sealed class Frame {
        public readonly double Dish;
        public readonly int Next;
        public Frame(double dish, int next) { Dish = dish; Next = next; }
    }

    sealed class NumberEntry {
        public readonly string Key;
        public readonly double Value;
        public NumberEntry(string key, double value) { Key = key; Value = value; }
    }

    sealed class Row {
        public string TableKey;
        public double Id;
        public double Dish;
        public List<NumberEntry> NeedElements;
    }

    sealed class JsonReader {
        readonly string text;
        int position;
        int depth;

        public JsonReader(string value) { text = value; }

        public List<Row> ReadTable() {
            var rows = new List<Row>();
            SkipWhitespace(); Expect('{'); SkipWhitespace();
            if (Take('}')) { EnsureEnd(); return rows; }
            var keys = new HashSet<string>(StringComparer.Ordinal);
            while (true) {
                string key = ReadString();
                if (!keys.Add(key)) throw Error("Duplicate table key: " + key);
                ParseNumericKey(key, false);
                SkipWhitespace(); Expect(':');
                rows.Add(ReadRow(key));
                SkipWhitespace();
                if (Take('}')) break;
                Expect(','); SkipWhitespace();
                if (rows.Count >= MaxRows) throw Error("Recipe row budget exceeded.");
            }
            EnsureEnd();
            return OrderRows(rows);
        }

        Row ReadRow(string tableKey) {
            Enter();
            var row = new Row { TableKey = tableKey };
            var seen = new HashSet<string>(StringComparer.Ordinal);
            bool hasId = false, hasNeed = false, hasWeights = false;
            bool hasCookware = false, hasDuration = false, hasCookType = false;
            SkipWhitespace(); Expect('{'); SkipWhitespace();
            if (Take('}')) { Leave(); throw Error("Empty configuration row."); }
            while (true) {
                string key = ReadString();
                if (!seen.Add(key)) throw Error("Duplicate row property: " + key);
                SkipWhitespace(); Expect(':'); SkipWhitespace();
                switch (key) {
                    case "id": row.Id = ReadSafeId(); hasId = true; break;
                    case "elementOrderId":
                        if (!IsSafeInteger(ReadNumber())) throw Error("elementOrderId must be a safe integer.");
                        hasCookware = true; break;
                    case "needElements": row.NeedElements = ReadNumberMap(); hasNeed = true; break;
                    case "elementIdWeight": row.Dish = ReadDishMap(); hasWeights = true; break;
                    case "duration": ReadNumber(); hasDuration = true; break;
                    case "cookType": ReadNumber(); hasCookType = true; break;
                    default: SkipValue(); break;
                }
                SkipWhitespace();
                if (Take('}')) break;
                Expect(','); SkipWhitespace();
            }
            Leave();
            if (!hasId || row.Id != ParseNumericKey(tableKey, false))
                throw Error("Row id must match its table key: " + tableKey);
            if (!hasCookware || !hasDuration || !hasCookType)
                throw Error("Required Kp source fields are missing in row " + tableKey);
            if (!hasNeed || row.NeedElements == null || row.NeedElements.Count == 0)
                throw Error("needElements must be a non-empty numeric object in row " + tableKey);
            if (!hasWeights || !IsSafeInteger(row.Dish))
                throw Error("elementIdWeight must provide a safe dish identifier in row " + tableKey);
            return row;
        }

        List<NumberEntry> ReadNumberMap() {
            CountMapEntry();
            var entries = new List<NumberEntry>();
            var keys = new HashSet<string>(StringComparer.Ordinal);
            SkipWhitespace(); Expect('{'); SkipWhitespace();
            if (Take('}')) return entries;
            while (true) {
                string key = ReadString();
                if (!keys.Add(key)) throw Error("Duplicate numeric map key: " + key);
                SkipWhitespace(); Expect(':'); SkipWhitespace();
                double value = ReadNumber();
                entries.Add(new NumberEntry(key, value));
                CountMapEntry();
                if (entries.Count > MaxEntriesPerMap) throw Error("Configuration map entry budget exceeded.");
                SkipWhitespace();
                if (Take('}')) break;
                Expect(','); SkipWhitespace();
            }
            return entries;
        }

        double ReadDishMap() {
            var entries = ReadNumberMap();
            if (entries.Count == 0) throw Error("elementIdWeight must not be empty.");
            entries = OrderMapEntries(entries);
            var dishIds = new HashSet<double>();
            double dish = 0;
            foreach (var entry in entries) {
                dish = ParseNumericKey(entry.Key, true);
                if (!dishIds.Add(dish)) throw Error("Duplicate dish prefix in elementIdWeight.");
            }
            return dish;
        }

        double ReadSafeId() {
            double value = ReadNumber();
            if (!IsSafeInteger(value)) throw Error("Identifiers must be safe integers.");
            return value;
        }

        double ReadNumber() {
            SkipWhitespace();
            int start = position;
            if (Take('-')) { }
            if (Take('0')) {
                if (position < text.Length && IsDigit(text[position])) throw Error("Leading zero in JSON number.");
            } else {
                if (position >= text.Length || text[position] < '1' || text[position] > '9') throw Error("Expected JSON number.");
                while (position < text.Length && IsDigit(text[position])) position++;
            }
            if (Take('.')) {
                int fractionStart = position;
                while (position < text.Length && IsDigit(text[position])) position++;
                if (position == fractionStart) throw Error("Invalid JSON fraction.");
            }
            if (Take('e') || Take('E')) {
                if (!Take('+')) Take('-');
                int exponentStart = position;
                while (position < text.Length && IsDigit(text[position])) position++;
                if (position == exponentStart) throw Error("Invalid JSON exponent.");
            }
            string token = text.Substring(start, position - start);
            double value;
            if (!Double.TryParse(token, NumberStyles.Float, CultureInfo.InvariantCulture, out value) ||
                !IsFinite(value) || Math.Abs(value) > MaxSafeInteger)
                throw Error("Unsupported, unsafe, or non-finite JSON number.");
            return value;
        }

        void SkipValue() {
            CountMapEntry();
            SkipWhitespace();
            if (position >= text.Length) throw Error("Unexpected end of JSON.");
            char current = text[position];
            if (current == '"') { ReadString(); return; }
            if (current == '{') { SkipObject(); return; }
            if (current == '[') { SkipArray(); return; }
            if (current == '-' || IsDigit(current)) { ReadNumber(); return; }
            if (TakeLiteral("true") || TakeLiteral("false") || TakeLiteral("null")) return;
            throw Error("Unsupported JSON value.");
        }

        void SkipObject() {
            Enter(); Expect('{'); SkipWhitespace();
            if (Take('}')) { Leave(); return; }
            var keys = new HashSet<string>(StringComparer.Ordinal);
            while (true) {
                string key = ReadString();
                if (!keys.Add(key)) throw Error("Duplicate property in skipped object: " + key);
                SkipWhitespace(); Expect(':'); SkipValue(); SkipWhitespace();
                if (Take('}')) break;
                Expect(','); SkipWhitespace();
            }
            Leave();
        }

        void SkipArray() {
            Enter(); Expect('['); SkipWhitespace();
            if (Take(']')) { Leave(); return; }
            while (true) {
                SkipValue(); SkipWhitespace();
                if (Take(']')) break;
                Expect(','); SkipWhitespace();
            }
            Leave();
        }

        void Enter() {
            depth++;
            if (depth > MaxJsonDepth) throw Error("JSON nesting depth limit exceeded.");
        }
        void CountMapEntry() {
            valueCount++;
            if (valueCount > MaxTotalMapEntries) throw Error("JSON value budget exceeded.");
        }
        void Leave() { depth--; }
        bool TakeLiteral(string literal) {
            if (position + literal.Length > text.Length ||
                String.CompareOrdinal(text, position, literal, 0, literal.Length) != 0) return false;
            position += literal.Length;
            return true;
        }
        string ReadString() {
            SkipWhitespace(); Expect('"');
            var builder = new StringBuilder();
            while (position < text.Length) {
                char c = text[position++];
                if (c == '"') return builder.ToString();
                if (c < 0x20) throw Error("Control character in JSON string.");
                if (c != '\\') { builder.Append(c); continue; }
                if (position >= text.Length) throw Error("Incomplete JSON escape.");
                char escape = text[position++];
                switch (escape) {
                    case '"': builder.Append('"'); break;
                    case '\\': builder.Append('\\'); break;
                    case '/': builder.Append('/'); break;
                    case 'b': builder.Append('\b'); break;
                    case 'f': builder.Append('\f'); break;
                    case 'n': builder.Append('\n'); break;
                    case 'r': builder.Append('\r'); break;
                    case 't': builder.Append('\t'); break;
                    case 'u':
                        if (position + 4 > text.Length) throw Error("Incomplete Unicode escape.");
                        int code;
                        if (!Int32.TryParse(text.Substring(position, 4), NumberStyles.HexNumber,
                                            CultureInfo.InvariantCulture, out code))
                            throw Error("Invalid Unicode escape.");
                        builder.Append((char)code); position += 4; break;
                    default: throw Error("Invalid JSON escape.");
                }
            }
            throw Error("Unterminated JSON string.");
        }
        void SkipWhitespace() {
            while (position < text.Length && (text[position] == ' ' || text[position] == '\t' ||
                   text[position] == '\r' || text[position] == '\n')) position++;
        }
        bool Take(char value) {
            if (position < text.Length && text[position] == value) { position++; return true; }
            return false;
        }
        void Expect(char value) {
            if (!Take(value)) throw Error("Expected '" + value + "'.");
        }
        void EnsureEnd() {
            SkipWhitespace();
            if (position != text.Length) throw Error("Trailing data after JSON value.");
        }
        InvalidDataException Error(string message) {
            return new InvalidDataException(message + " (offset " + position.ToString(CultureInfo.InvariantCulture) + ")");
        }
        static bool IsDigit(char value) { return value >= '0' && value <= '9'; }
        int valueCount;
        static List<Row> OrderRows(List<Row> rows) {
            var indexed = new List<Row>();
            var other = new List<Row>();
            foreach (var row in rows) {
                uint index;
                if (TryArrayIndex(row.TableKey, out index)) indexed.Add(row);
                else other.Add(row);
            }
            indexed.Sort((left, right) => ParseArrayIndex(left.TableKey).CompareTo(ParseArrayIndex(right.TableKey)));
            indexed.AddRange(other);
            return indexed;
        }
    }
}
}
