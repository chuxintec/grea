using System;
using System.IO;
using Grea.Foundation.Contracts;
using ModernSample.Domain;
namespace ModernSample.Services
{
    public sealed class ProgressStore : IProgressStore
    {
        readonly ISaveStore store;
        public ProgressStore(ISaveStore store) { this.store=store; }
        public Progress Read()
        {
            var raw=store.Read();if(raw==null)return new Progress();
            if(!raw.StartsWith("modern:1|",StringComparison.Ordinal) || !int.TryParse(raw.Substring(9),out int actions))throw new InvalidDataException("Unknown save; preserved");
            return new Progress(actions);
        }
        public void Write(Progress value)=>store.Write("modern:1|"+value.Actions);
    }
}
