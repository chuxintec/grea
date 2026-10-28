# beaver development

Current approved local scope: structure audit and controlled migration plans, native build-resource filtering, persistent serialization readback and preview capture. Reuse the existing asset moves, import, transaction/recovery and debug/build components. No new remote release or global installation is part of this work.

Local candidate: `0.5.1.dev20261028+fix3`. Implemented all three command families and the consumer-requested bounded folder move extension using the existing Unity transaction. Type directories and independent structure-exception schema follow the current upstream contract; shader provenance consumes `monkey-shader-handoff/1` and remains distinct from native compilation.

Verified: 68 affected synthetic checks; two independent Unity 6000.6.2f1 projects; nested strings/null references, exact Sprite subresource IDs and saved-scene fields; 750×1334 and 320×480 preview captures; fully transparent negative frame; native build target/pipeline/scenes/Resources dependency collection; complete folder moves, independent reopen, new-path field readback and a reviewed reverse plan restoring original bytes/GUIDs/localIDs. Early provider/transport failures remain in private evidence and were corrected before delivery.

Current limitation: resource isolation is a precise plan only, with execution blocked until runtime-use proof and a safe native isolation transaction exist. It never deletes assets or substitutes shaders. Folder moves are bounded to 10,000 manifest entries/256 MiB and retain verified before-images; recovery uses inspection and a fresh reviewed reverse plan, not automatic overwrite. Dynamic consumer correctness, production-project adoption, physical input, visual parity and gameplay remain consumer-owned acceptance.

Delivered the fixed isolated candidate, CLI schemas and producer to the active consumer and upstream adapter maintainer. Real project adoption of fix1 has verified four assets, 190 persistent objects and five fields with source guards intact; the older candidate scalar/profile/report issues remain recorded separately. The final fix3 consumer/adapter gate remains pending; fix3 addresses the real product-root profile, ArraySize scalar and large-report re-read issues. Upstream limited adapter results are separately verified for the initial candidate (39 checks), fix1 (10 incremental) and fix2 (5 incremental), without Editor or project-adoption claims. Final planning guards cover complete source/metadata input sets, generator paths in every root, JSON consumers and target/parent Unicode and case collisions. Unmigrated scenes remain follow-up issues while safe incremental declarations are possible; no declaration signs off project conformance. No additional P1 scope is started.

## Released baseline: 0.5.0

The release combines the reusable execution toolkit with native UI inspection, guarded wiring, explicit UI field repairs and unified diagnostics. It retains the existing batch/production transaction and recovery contracts.

Completed: all effective product branches have been integrated; the existing toolkit source and tests are retained. UI field/type/resource identities, event wiring, native save/reload and runtime raycast observations have bounded private-fixture evidence. See [validation](VALIDATION-v0.5.json) and [usage](DEVELOPMENT-v0.5.md).

Release preparation: public documentation and examples use neutral project names and paths; private provenance originals and raw evidence remain local. Build wheel/sdist/checksums from the fixed committed source, then verify the public repository, tag, release state and downloaded hashes. Required copyright, compatibility API identifiers and public product/download references are retained.

Pending acceptance: naturally ready production-project adoption, physical input and visual parity. These do not become passed merely because a formal tool release exists. No new Go-service, Cocos, gameplay or production-data work is part of this release.

Approved P0 continuation: the consumer needs old source-evidence assets and completed Editor writers retired from active Assets. A bounded native retirement/recovery operation is being added to the existing Unity transaction, with verified outside-Assets before-images, explicit protected roots and dynamic-key retirement declarations. The fixed fix3 core candidate solves profile/scalar/large-report issues; it does not claim retirement execution is already available.
