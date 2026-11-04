# monkey development conventions

monkey is a Python command-line tool for evidence-traceable recovery into independent native project candidates. Source parsing, resource identity, recovery drafts and candidate generation belong here. GREA owns workflow orchestration; beaver owns development-project adoption and construction.

- Read `docs/PLAN.md` and the relevant public contract before making changes. Preserve current user authorization and repository ownership boundaries.
- Keep original inputs immutable. Private samples, candidates, account data, raw logs and internal coordination records stay under ignored local directories and must not enter Git or release artifacts.
- Preserve explicit source hashes, asset identities and generated-file ownership. Never silently overwrite human changes or fabricate missing resources, schema, server behavior or successful recovery.
- Native Unity output uses Bootstrap/Domain/Gameplay/Presentation/Services. Domain and Gameplay remain engine-independent. Runtime code must not interpret the source engine object graph.
- Numeric configuration remains UTF-8 JSON. Native object references may use native assets, but do not duplicate editable numeric truth.
- CLI/MCP contracts, versions, shared schemas and Editor ownership have one writer. Delegate only independent modules; do not recursively spawn agents or mutate another product's repository.
- Prefer bounded, relevant unit and integration checks. Generation, compilation, native import, runtime, visual comparison, publication and installation are separate evidence layers.
- Current published release is 0.7.0, but all new development is the single 0.8.0 line (user 2026-11-04); merge existing Cocos fixes and Unity recovery without iterating the 0.7 line. Preserve compatibility toolkit IDs, public contracts, old tags and fixed candidates. A release does not imply complete game recovery.
- Release only within current explicit user authorization. Stage exact reviewed paths, verify package contents, preserve licenses and private evidence, and use normal fast-forward-compatible remote updates.
- Global installations, other applications, credentials, game projects and shared services are outside ordinary repository maintenance. Coordinate an explicitly authorized native window before using shared Editor resources.

- Follow [VERSIONING.md](/Users/wangmeng/MyProjects/Manager/standards/VERSIONING.md). The current user override requires one active v0.8.0.devN head, with no continuing v0.7 heads; keep fixed candidate bytes and history immutable. Use only vX.Y.Z.devN development heads or actually released vX.Y.Z formal heads. Version policy grants no release/tag authority and requires no re-export or full regression.

- Current governance (2026-11-04): monkey is the internal recovery module of the GREA product. The GREA lead assigns ordinary tool work, decides bounded technical compatibility and coordinates fixed candidates, consumer adoption and unified external distribution. Keep this repository, source ownership, sessions, WIP and existing fixed inputs in place; do not independently publish monkey. The standalone repository is private; new GREA packages distribute module binaries under the later explicit human decision (Mac ARM64 first), superseding the same-day complete-module-source choice. Old published copies/licences are not revoked; do not claim binaries are unrecoverable. Existing concrete resource handoffs may finish with the lead informed.
