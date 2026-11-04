# monkey development conventions

monkey is a Python command-line tool for evidence-traceable recovery into independent native project candidates. Source parsing, resource identity, recovery drafts and candidate generation belong here. GREA owns workflow orchestration; beaver owns development-project adoption and construction.

- Read `docs/PLAN.md` and the relevant public contract before making changes. Preserve current user authorization and repository ownership boundaries.
- Keep original inputs immutable. Private samples, candidates, account data, raw logs and internal coordination records stay under ignored local directories and must not enter Git or release artifacts.
- Preserve explicit source hashes, asset identities and generated-file ownership. Never silently overwrite human changes or fabricate missing resources, schema, server behavior or successful recovery.
- Native Unity output uses Bootstrap/Domain/Gameplay/Presentation/Services. Domain and Gameplay remain engine-independent. Runtime code must not interpret the source engine object graph.
- Numeric configuration remains UTF-8 JSON. Native object references may use native assets, but do not duplicate editable numeric truth.
- CLI/MCP contracts, versions, shared schemas and Editor ownership have one writer. Delegate only independent modules; do not recursively spawn agents or mutate another product's repository.
- Prefer bounded, relevant unit and integration checks. Generation, compilation, native import, runtime, visual comparison, publication and installation are separate evidence layers.
- Stable release target is 0.7.0; independent 0.8 development candidates remain separate. Preserve the compatibility toolkit IDs and public provider contracts. A formal release does not imply all source versions or complete game behavior are restored.
- Release only within current explicit user authorization. Stage exact reviewed paths, verify package contents, preserve licenses and private evidence, and use normal fast-forward-compatible remote updates.
- Global installations, other applications, credentials, game projects and shared services are outside ordinary repository maintenance. Coordinate an explicitly authorized native window before using shared Editor resources.

- Use three-component numeric release versions and .devN for development candidates; preserve immutable published/fixed candidate identities.
