using System;
using System.Globalization;
using System.IO;
using Game.Domain;
using Game.Gameplay;
using Grea.Foundation.Contracts;

namespace Game.Services
{
    public sealed class CounterPersistence : ICounterPersistence
    {
        readonly ISaveStore store;
        public CounterPersistence(ISaveStore store) { this.store = store ?? throw new ArgumentNullException(nameof(store)); }
        public CounterState Load()
        {
            string dto = store.Read();
            if (dto == null) return new CounterState(0);
            if (!dto.StartsWith("counter:1:", StringComparison.Ordinal) ||
                !int.TryParse(dto.Substring(10), NumberStyles.None, CultureInfo.InvariantCulture, out int value))
                throw new InvalidDataException("Unknown counter DTO; no automatic migration");
            return new CounterState(value);
        }
        public void Save(CounterState value) => store.Write("counter:1:" + value.Value.ToString(CultureInfo.InvariantCulture));
    }
}
