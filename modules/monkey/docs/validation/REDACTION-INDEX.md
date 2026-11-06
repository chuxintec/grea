# Historical validation redaction index

The validation records in this folder are historical summaries or preserved structured records derived from private source work. Renamed records remain historical evidence; they are not synthetic fixtures and were not rerun for this release. Detailed source identities and private candidate logs were removed from the publishable tree.

The original source documents and refs are retained in a private local release archive outside the release tree. Their relative recovery mapping is recorded only in the private release receipt; this index intentionally exposes no local path, backup name, or sensitive filename.

The following neutral records retain only their historical topic and status:

- `source-intake-summary.json`, `source-unavailable-summary.json`: source intake and availability records.
- `native-mounted-capture.json`, `native-resource-summary.json`: native resource inspection records.
- `2026-10-24-resources-summary.md`, `2026-10-24-graphs-summary.md`: resource and graph inspection records.
- `2026-10-23-full-source-audit-summary.md`, `2026-10-25-reexport-summary.md`: source audit and re-export records.
- `2026-10-25-release-summary.md`: historical release evidence summary.

JSON object/array nesting, list lengths, value types, and field counts were preserved; one identity-bearing source label was replaced with neutral wording. Compatibility identifiers required by the CLI and profile loader remain in technical examples as machine contracts, without identifying game names in surrounding prose. Public product and engine names, required license notices, public GitHub links, and fixed upstream hashes for public dependencies are retained.
