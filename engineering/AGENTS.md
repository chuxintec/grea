# Engineering in monkey

This is the imported engineering module of monkey. New engineering changes and tests land in the monkey repository and run through `monkey develop`. Existing pinned beaver transactions keep their original runtime. Keep source recovery and development-project adoption as separately verified operations. The historical guidelines below still apply to implementation safety; standalone repository and release ownership is superseded.

GREA's internal development-engineering module: Python CLI and native Unity Editor companions. Source-package recovery belongs to upstream modules.

- Routine assignments, candidate/adoption reporting and cross-project coordination go through the GREA lead. Close existing direct technical handoffs at natural safe points; urgent safety/permission issues may go directly to the director.
- Keep the independent private repository, working directory and existing WIP in place. GREA owns unified external binary distribution for new module implementations; private source stays here. Explicitly classify helper/SDK/user-template/third-party resources and preserve MIT/upstream notices, historical releases and exact frozen identities. No independent module publication or automatic consumer upgrade.

- Branch heads use only `vX.Y.Z.devN` (development) or `vX.Y.Z` (released). Use full `refs/heads/` and `refs/tags/` in checks/pushes/deletions; published tags and fixed artifacts remain immutable. Current legacy/paused checkouts may be detached at their exact preserved commits; new product work uses its actual version worktree.

- Keep product code, tests and public documentation self-contained; use docs/PLAN.md as the single progress entry and docs/CLI-CONTRACT.md for public contracts.
- Default to inspect/plan. Native writes require an explicit target, immutable plan, implementation identity and content preconditions; preserve later manual edits.
- Edit Unity assets through native Editor APIs. Do not author serialized scenes or Prefabs by hand, unpack variants implicitly or guess subasset identifiers.
- Keep runtime numeric configuration in UTF-8 JSON; object references may remain native assets.
- Keep raw evidence, credentials, local environment data, original game files and generated candidates under ignored local directories. Publish only neutral examples and factual validation summaries.
- Preserve required copyright and third-party license notices. Toolkit subcommands retain their original output and exit-code contracts.
- Separate capability presence, provider readiness, native execution, runtime observations, physical input, visual parity and business acceptance.
- Run checks appropriate to the affected paths. Do not repeat unrelated engine or full-application suites for documentation changes.
- Project/service/player-data writes and installation operations require their own applicable authorization; a tool release does not grant them.
- Module contributors use disjoint files and do not start recursive agents; one owner controls shared interfaces, the Editor, desktop input and release state.
