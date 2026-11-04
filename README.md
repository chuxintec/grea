# beaver

Controlled native game-project tooling: inspect a target, prepare an immutable plan, apply bounded changes and retain readback/recovery evidence. GREA supplies workflows; monkey supplies recovery candidates; beaver operates on adopted or existing development projects.

## Install

Release version: **v0.6.0**. Verify the supplied SHA256SUMS, then install the downloaded wheel in an isolated environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install './beaver_game_tools-0.6.0-py3-none-any.whl[toolkit]'
.venv/bin/beaver version
.venv/bin/beaver capabilities
```

Python 3.10+ is required; the release validation report lists the interpreter actually tested. Native operations require an explicitly selected, already-installed Unity 6000.6.2f1 Editor and matching target dependencies. beaver does not install an engine. Optional `images` uses Pillow; optional `toolkit` uses Pillow and jsonschema. Go, protocol compilers, Docker, MySQL and Redis remain explicit external providers for the corresponding commands.

## Scope

- Incremental adoption, exact asset/assembly/SDK identity and guarded transaction recovery.
- Additive intake contracts 1–5, including explicitly declared engine objects and retained assemblies; unsupported methods/behaviors remain unknown.
- Native Prefab/UI, resource, JSON configuration, typed reference/wiring and C# maintenance operations.
- Explicit macOS build plans and native build/readback contracts with source/font restoration checks.
- Application instance identity, bounded QA collection and limited input. Virtual pointer is an explicitly selected backup; Computer Use remains the primary human-facing route.
- Optional inherited toolkit commands: `beaver tool <id> [args...]` retain their own output and exit-code contracts.

Normal operations return `beaver-result/1`: 0=ok, 1=partial, 2=failed, 3=blocked/not_run. Native writes bind the exact project, plan and implementation; later manual changes are protected. A failure after attempted execution must not be treated as zero writes or automatically replayed. Existing fixed17/fixed29/fixed31 installations, locks and transactions keep their original identities; a new version does not authorize replay or upgrade.

Read [release scope and support](docs/RELEASE-v0.6.0.md), [CLI contracts](docs/CLI-CONTRACT.md), [build policy](docs/BUILD-POLICY.md), [SDK migration](docs/SDK-MIGRATION.md), [QA binding](docs/QA-BINDING.md), [virtual pointer](docs/VIRTUAL-POINTER.md), and [provenance](docs/PROVENANCE.md).

MIT; required upstream notices are included. No game source, account, credential, private fixture or raw runtime evidence is distributed. The CLI has no native application bundle or application icon.
