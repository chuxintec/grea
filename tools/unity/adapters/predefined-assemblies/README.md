# Predefined assembly adapter 0.1.0

An opt-in bridge for existing Unity code compiled into Assembly-CSharp. Embed this package and com.grea.foundation 0.2.0 together. The facade is autoReferenced; core Contracts remains explicit. Projects with authored asmdefs should reference Grea.Foundation.Contracts directly instead.

LegacyLifetimeScope delegates to the existing scope implementation and exposes only BCL types. It adds no scheduler, scene object, update loop or persistence policy. The project adapter decides when a session ends, whether disable is pooling, and which resources it owns. Cancelling a generation must not wrap/reorder native coroutines. Hiding a pooled page must not discard its listeners unless its own contract requires rebinding.

This does not convert the caller to asmdefs or make its rules engine-independent. Scope ownership remains main-thread-only. Dispose invalidates/cancels before releasing in reverse order and preserves the core's aggregate cleanup errors. See the M5 report for two bounded legacy integration pilots; other Editors/platforms are unverified.
