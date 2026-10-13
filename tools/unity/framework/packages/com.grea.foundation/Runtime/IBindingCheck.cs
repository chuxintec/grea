using System.Collections.Generic;

namespace Grea.Foundation.Runtime
{
    public interface IBindingCheck { IEnumerable<string> MissingBindings(); }
}
