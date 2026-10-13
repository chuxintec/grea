# AssemblySanitizer

Normalizes AssetRipper/IL2CPP dummy assemblies for offline Unity recovery. It removes generated editor-scan types, clears executable entry-point metadata, and replaces unavailable P/Invoke bodies with explicit `NotSupportedException` stubs. It does not reconstruct original game logic.

Dry-run is the default:

```sh
assembly-sanitizer Assets/Plugins Evidence/DllBackup \
  --unity-editor /Applications/Unity/Hub/Editor/6000.5.10f1/Unity.app
```

Add `--apply` only after reviewing candidates. Apply mode creates first-copy backups before rewriting DLLs. Always retain source hashes and run Unity compilation and Play Mode validation afterward.
