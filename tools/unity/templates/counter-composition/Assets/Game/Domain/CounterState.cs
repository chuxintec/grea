using System;

namespace Game.Domain
{
    public readonly struct CounterState
    {
        public int Value { get; }
        public CounterState(int value) { if (value < 0) throw new ArgumentOutOfRangeException(nameof(value)); Value = value; }
        public CounterState Next() => new CounterState(checked(Value + 1));
    }
}
