# beaver development

Current approved local scope: structure audit and controlled migration plans, native build-resource filtering, persistent serialization readback and preview capture. Reuse the existing asset moves, import, transaction/recovery and debug/build components. No new remote release or global installation is part of this work.

Local candidate: `0.5.1.dev20261028+fix1`. Implemented all three command families and the consumer-requested bounded folder move extension using the existing Unity transaction. Type directories and independent structure-exception schema follow the current upstream contract; shader provenance consumes `monkey-shader-handoff/1` and remains distinct from native compilation.

Verified: 57 affected synthetic checks; two independent Unity 6000.6.2f1 projects; nested strings/null references, exact Sprite subresource IDs and saved-scene fields; 750×1334 and 320×480 preview captures; fully transparent negative frame; native build target/pipeline/scenes/Resources dependency collection; complete folder moves, independent reopen, new-path field readback and a reviewed reverse plan restoring original bytes/GUIDs/localIDs. Early provider/transport failures remain in private evidence and were corrected before delivery.

Current limitation: resource isolation is a precise plan only, with execution blocked until runtime-use proof and a safe native isolation transaction exist. It never deletes assets or substitutes shaders. Folder moves are bounded to 10,000 manifest entries/256 MiB and retain verified before-images; recovery uses inspection and a fresh reviewed reverse plan, not automatic overwrite. Dynamic consumer correctness, production-project adoption, physical input, visual parity and gameplay remain consumer-owned acceptance.

Delivered the fixed isolated candidate, CLI schemas and producer to the active consumer and upstream adapter maintainer. External acceptance remains pending actual project adoption and the final fix1 adapter gate. The preliminary candidate has a separately verified 39-check limited adapter result; it did not run an Editor or establish project adoption. A final installed-CLI regression identified legacy build-scene placement as an overbroad global blocker; fix1 retains that follow-up issue while allowing correctly guarded incremental migration declarations. No additional P1 scope is started.

## Released baseline: 0.5.0

The release combines the reusable execution toolkit with native UI inspection, guarded wiring, explicit UI field repairs and unified diagnostics. It retains the existing batch/production transaction and recovery contracts.

Completed: all effective product branches have been integrated; the existing toolkit source and tests are retained. UI field/type/resource identities, event wiring, native save/reload and runtime raycast observations have bounded private-fixture evidence. See [validation](VALIDATION-v0.5.json) and [usage](DEVELOPMENT-v0.5.md).

Release preparation: public documentation and examples use neutral project names and paths; private provenance originals and raw evidence remain local. Build wheel/sdist/checksums from the fixed committed source, then verify the public repository, tag, release state and downloaded hashes. Required copyright, compatibility API identifiers and public product/download references are retained.

Pending acceptance: naturally ready production-project adoption, physical input and visual parity. These do not become passed merely because a formal tool release exists. No new Go-service, Cocos, gameplay or production-data work is part of this release.
