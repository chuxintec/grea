// Editor-only, hash-pinned upgrade of one existing static TMP fallback asset.
// This runner is installed only in a fresh native-font stage project.
using System;
using System.Collections.Generic;
using System.IO;
using System.Diagnostics;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using TMPro;
using UnityEditor;
using UnityEngine;

namespace Monkey.NativeEditor
{
    public static class UnityStaticFontCompletion
    {
        [Serializable]
        sealed class Request
        {
            public string schema, status, projectRoot, stageManifestPath, stageManifestSha256;
            public string sourceSelectionManifestSha256, completionReceiptSha256;
            public string completionEvidencePath, fontBindingPath, fontBindingSha256;
            public string generationReceiptPath, generationReceiptSha256;
            public string consumerResolutionPath, consumerResolutionSha256, corpusSha256;
            public string staticFontAssetId, staticFontAssetPath, staticFontAssetGuid, staticFontAssetSha256Before;
            public string staticFontMetaSha256, nativeReadbackPath;
            public int staticFontBaseGlyphCount, staticFontRequiredGlyphCount;
            public uint[] staticFontRequiredUnicode;
            public string[] staticFontAddedGlyphs, consumerTexts, forbiddenAssetPaths;
            public FontPin[] primaryFontAssets;
        }

        [Serializable]
        sealed class FontPin
        {
            public string assetId, assetPath, assetGuid, assetSha256, metaSha256;
        }

        [Serializable]
        sealed class StageManifest
        {
            public int schemaVersion;
            public string targetProfile, stageKind, sourceSelectionManifestSha256, completionReceiptSha256;
            public string fontBindingSha256, fontGenerationReceiptSha256, portableGenerationReceiptSha256;
            public StageStaticFont selectedStaticFont;
            public StageFile[] files;
        }

        [Serializable]
        sealed class StageStaticFont
        {
            public string assetId, assetPath, assetGuid, originalAssetSha256, originalMetaSha256;
        }

        [Serializable]
        sealed class StageFile
        {
            public string path, sha256, owner;
            public long bytes;
        }

        [Serializable]
        sealed class ConsumerResolution
        {
            public string schema, status, corpusSha256;
            public ConsumerRun[] labels;
        }

        [Serializable]
        sealed class ConsumerRun { public string text; }

        [Serializable]
        sealed class FileHashReadback
        {
            public string path, beforeSha256, afterSha256;
            public bool unchanged;
        }

        [Serializable]
        sealed class CorpusLookupReadback
        {
            public string textSha256;
            public uint[] requiredUnicode, missingUnicode;
            public string[] resolvedFontPaths;
        }

        [Serializable]
        sealed class NativeReadback
        {
            public string schema, status, stageManifestSha256, sourceSelectionManifestSha256, completionReceiptSha256;
            public string staticFontAssetId, staticFontAssetPath, staticFontAssetGuid;
            public string staticFontAssetSha256Before, staticFontAssetSha256After;
            public string fontGuidBefore, fontGuidAfter;
            public string atlasGuidBefore, atlasGuidAfter, materialGuidBefore, materialGuidAfter;
            public long fontLocalIdBefore, fontLocalIdAfter, atlasLocalIdBefore, atlasLocalIdAfter;
            public long materialLocalIdBefore, materialLocalIdAfter;
            public int atlasWidth, atlasHeight, glyphCountBefore, glyphCountAfter, characterCountBefore, characterCountAfter;
            public uint[] requiredUnicode, missingRequiredUnicode;
            public string[] addedGlyphs;
            public bool tryAddCharactersCalled, primaryAssetsUnchanged;
            public int consumerTextCount;
            public CorpusLookupReadback[] corpusLookups;
            public FileHashReadback[] primaryAssetHashes, unchangedFileHashes;
            public string error;
        }

        public static void Run()
        {
            Request request = null;
            string readbackPath = null;
            try
            {
                var args = Environment.GetCommandLineArgs();
                string requestPath = Argument(args, "-monkeyFontRequest");
                string expectedRequestSha = Argument(args, "-monkeyFontRequestSha256");
                if (string.IsNullOrEmpty(requestPath) || !IsSha256(expectedRequestSha))
                    throw new InvalidOperationException("NATIVE_FONT_REQUEST_ARGUMENTS_MISSING");
                requestPath = Path.GetFullPath(requestPath);
                request = ReadPinned<Request>(requestPath, expectedRequestSha, "NATIVE_FONT_REQUEST");
                string expectedRequestDirectory = Directory.GetParent(Path.GetFullPath(request.projectRoot)).FullName;
                if (!string.Equals(Path.GetDirectoryName(requestPath), expectedRequestDirectory, StringComparison.Ordinal))
                    throw new InvalidOperationException("NATIVE_FONT_REQUEST_MUST_BE_NEXT_TO_FRESH_PROJECT");
                readbackPath = SafeProjectPath(request.projectRoot, request.nativeReadbackPath);
                Execute(request);
            }
            catch (Exception exception)
            {
                if (request != null && !string.IsNullOrEmpty(readbackPath))
                {
                    try
                    {
                        WriteFailureReadback(request, readbackPath, exception);
                    }
                    catch (Exception writeException)
                    {
                        UnityEngine.Debug.LogError("NATIVE_FONT_FAILURE_READBACK_WRITE_FAILED: " + writeException.Message);
                    }
                }
                UnityEngine.Debug.LogException(exception);
                EditorApplication.Exit(1);
            }
        }

        static void Execute(Request request)
        {
            if (EditorApplication.isPlaying)
                throw new InvalidOperationException("NATIVE_FONT_STAGE_PLAY_MODE_FORBIDDEN");
            if (request.schema != "monkey-unity-static-font-completion-request/1" || request.status != "prepared")
                throw new InvalidOperationException("NATIVE_FONT_REQUEST_SCHEMA_INVALID");
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            if (!string.Equals(projectRoot, Path.GetFullPath(request.projectRoot), StringComparison.Ordinal))
                throw new InvalidOperationException("NATIVE_FONT_PROJECT_ROOT_MISMATCH");
            if (Application.platform != RuntimePlatform.OSXEditor)
                throw new InvalidOperationException("NATIVE_FONT_EDITOR_PLATFORM_UNSUPPORTED");
            if (request.primaryFontAssets == null || request.primaryFontAssets.Length == 0
                || request.staticFontRequiredUnicode == null || request.staticFontRequiredUnicode.Length == 0
                || request.consumerTexts == null || request.consumerTexts.Length == 0)
                throw new InvalidOperationException("NATIVE_FONT_REQUEST_SCOPE_INCOMPLETE");

            var manifest = ReadPinned<StageManifest>(SafeProjectPath(projectRoot, request.stageManifestPath),
                request.stageManifestSha256, "NATIVE_FONT_STAGE_MANIFEST");
            if (manifest.schemaVersion != 1 || manifest.stageKind != "native-static-font-corpus-completion"
                || manifest.sourceSelectionManifestSha256 != request.sourceSelectionManifestSha256
                || manifest.completionReceiptSha256 != request.completionReceiptSha256
                || manifest.fontBindingSha256 != request.fontBindingSha256
                || manifest.portableGenerationReceiptSha256 != request.generationReceiptSha256
                || manifest.selectedStaticFont == null
                || manifest.selectedStaticFont.assetId != request.staticFontAssetId
                || manifest.selectedStaticFont.assetPath != request.staticFontAssetPath
                || manifest.selectedStaticFont.assetGuid != request.staticFontAssetGuid
                || manifest.selectedStaticFont.originalAssetSha256 != request.staticFontAssetSha256Before
                || manifest.selectedStaticFont.originalMetaSha256 != request.staticFontMetaSha256)
                throw new InvalidOperationException("NATIVE_FONT_STAGE_MANIFEST_IDENTITY_MISMATCH");
            VerifyManifestFiles(projectRoot, manifest, request.staticFontAssetPath, request.staticFontAssetSha256Before);
            foreach (var forbidden in request.forbiddenAssetPaths ?? Array.Empty<string>())
                if (File.Exists(SafeProjectPath(projectRoot, forbidden)))
                    throw new InvalidOperationException("NATIVE_FONT_FORBIDDEN_GAME_FONT_COPIED: " + forbidden);

            string bindingPath = SafeProjectPath(projectRoot, request.fontBindingPath);
            var binding = ReadPinned<UnitySystemFonts.BindingSet>(bindingPath, request.fontBindingSha256, "NATIVE_FONT_BINDING");
            if (binding.schema != "monkey-unity-system-fonts/1" || binding.status != "prepared"
                || binding.systemFonts == null || binding.systemFonts.fonts == null
                || binding.labelBindings == null)
                throw new InvalidOperationException("NATIVE_FONT_BINDING_INVALID");
            if (binding.systemFonts.targetOS != "macOS"
                || ReadMacOSVersion("-productVersion") != binding.systemFonts.targetOSVersion
                || (!string.IsNullOrEmpty(binding.systemFonts.targetOSBuild)
                    && ReadMacOSVersion("-buildVersion") != binding.systemFonts.targetOSBuild))
                throw new InvalidOperationException("NATIVE_FONT_CORETEXT_TARGET_BUILD_MISMATCH");
            string plannedReadback = SafeProjectPath(projectRoot, request.nativeReadbackPath);
            if (File.Exists(plannedReadback))
                throw new InvalidOperationException("NATIVE_FONT_READBACK_ALREADY_EXISTS");
            var staticSpecRows = binding.systemFonts.fonts.Where(font => font != null
                && font.assetId == request.staticFontAssetId).ToArray();
            if (staticSpecRows.Length != 1 || staticSpecRows[0].populationMode != "StaticSDFRequired"
                || staticSpecRows[0].assetPath != request.staticFontAssetPath
                || staticSpecRows[0].requiredUnicode == null
                || !staticSpecRows[0].requiredUnicode.OrderBy(value => value).SequenceEqual(
                    request.staticFontRequiredUnicode.OrderBy(value => value)))
                throw new InvalidOperationException("NATIVE_FONT_STATIC_BINDING_MISMATCH");
            var staticSpec = staticSpecRows[0];

            string resolutionPath = SafeProjectPath(projectRoot, request.consumerResolutionPath);
            var resolution = ReadPinned<ConsumerResolution>(resolutionPath, request.consumerResolutionSha256,
                "NATIVE_FONT_CONSUMER_RESOLUTION");
            if (resolution.schema != "monkey-consumer-text-coretext-resolution/1"
                || resolution.status != "resolved" || resolution.corpusSha256 != request.corpusSha256
                || resolution.labels == null || !resolution.labels.Select(row => row.text)
                    .SequenceEqual(request.consumerTexts, StringComparer.Ordinal))
                throw new InvalidOperationException("NATIVE_FONT_CONSUMER_CORPUS_MISMATCH");

            string staticPath = SafeProjectPath(projectRoot, request.staticFontAssetPath);
            string staticMetaPath = staticPath + ".meta";
            if (FileHash(staticMetaPath) != request.staticFontMetaSha256
                || AssetDatabase.AssetPathToGUID(request.staticFontAssetPath) != request.staticFontAssetGuid)
                throw new InvalidOperationException("NATIVE_FONT_STATIC_ASSET_GUID_MISMATCH");
            var font = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(request.staticFontAssetPath);
            if (font == null || font.atlasPopulationMode != AtlasPopulationMode.Static
                || font.sourceFontFile != null || font.atlasTextures == null || font.atlasTextures.Length != 1
                || font.material == null || font.atlasTextures[0] == null)
                throw new InvalidOperationException("NATIVE_FONT_STATIC_TARGET_INVALID");
            var originalAtlas = font.atlasTextures[0];
            var originalMaterial = font.material;
            var beforeIdentity = CaptureAssetIdentity(font, originalAtlas, originalMaterial);
            if (beforeIdentity.fontGuid != request.staticFontAssetGuid
                || beforeIdentity.fontFileSha256 != request.staticFontAssetSha256Before
                || font.characterTable.Count != request.staticFontBaseGlyphCount
                || font.glyphTable.Count != request.staticFontBaseGlyphCount)
                throw new InvalidOperationException("NATIVE_FONT_BASE_ASSET_READBACK_MISMATCH");

            var primaryBefore = ValidatePrimaryPins(projectRoot, binding, request.primaryFontAssets, font);
            if (string.IsNullOrEmpty(request.generationReceiptPath)
                || !IsSha256(request.generationReceiptSha256))
                throw new InvalidOperationException("NATIVE_FONT_GENERATION_RECEIPT_PIN_MISSING");
            string generationReceiptPath = SafeProjectPath(projectRoot, request.generationReceiptPath);

            var upgrade = UnitySystemFonts.UpgradeStaticSdfAsset(binding, request.staticFontAssetId,
                generationReceiptPath, request.generationReceiptSha256, font);
            if (upgrade == null || upgrade.status != "updated_pending_save_reopen"
                || upgrade.tryAddCharactersCalled
                || upgrade.atlasWidth != originalAtlas.width || upgrade.atlasHeight != originalAtlas.height
                || upgrade.glyphCount != request.staticFontRequiredGlyphCount
                || upgrade.characterCount != request.staticFontRequiredGlyphCount
                || !upgrade.requiredUnicode.OrderBy(value => value).SequenceEqual(
                    request.staticFontRequiredUnicode.OrderBy(value => value)))
                throw new InvalidOperationException("NATIVE_FONT_UPGRADE_BRIDGE_READBACK_MISMATCH");

            foreach (var code in request.staticFontRequiredUnicode)
                if (!font.HasCharacter((int)code))
                    throw new InvalidOperationException("NATIVE_FONT_SAVED_LOOKUP_MISSING: U+" + code.ToString("X4"));

            EditorUtility.SetDirty(font);
            AssetDatabase.SaveAssets();
            string editedFontSha = FileHash(staticPath);
            AssetDatabase.ImportAsset(request.staticFontAssetPath, ImportAssetOptions.ForceUpdate);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            // Reload the bound chain together. A loaded primary can otherwise
            // retain fallback-character caches pointing at the unloaded asset.
            foreach (var pin in request.primaryFontAssets)
            {
                var primary = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(pin.assetPath);
                if (primary != null) Resources.UnloadAsset(primary);
            }
            Resources.UnloadAsset(font);
            AssetDatabase.ImportAsset(request.staticFontAssetPath, ImportAssetOptions.ForceUpdate);
            var reopened = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(request.staticFontAssetPath);
            if (reopened == null || reopened.atlasTextures == null || reopened.atlasTextures.Length != 1
                || reopened.material == null)
                throw new InvalidOperationException("NATIVE_FONT_SAVE_REOPEN_FAILED");
            var reopenedAtlas = reopened.atlasTextures[0];
            var reopenedMaterial = reopened.material;
            var afterIdentity = CaptureAssetIdentity(reopened, reopenedAtlas, reopenedMaterial);
            if (!SamePersistentIds(beforeIdentity, afterIdentity)
                || afterIdentity.fontFileSha256 != editedFontSha
                || reopened.atlasPopulationMode != AtlasPopulationMode.Static
                || reopened.sourceFontFile != null || reopenedAtlas.width != upgrade.atlasWidth
                || reopenedAtlas.height != upgrade.atlasHeight
                || reopened.glyphTable.Count != request.staticFontRequiredGlyphCount
                || reopened.characterTable.Count != request.staticFontRequiredGlyphCount)
                throw new InvalidOperationException("NATIVE_FONT_SAVE_REOPEN_IDENTITY_MISMATCH");
            var missingRequired = request.staticFontRequiredUnicode.Where(code => !reopened.HasCharacter((int)code)).ToArray();
            if (missingRequired.Length > 0)
                throw new InvalidOperationException("NATIVE_FONT_REOPEN_LOOKUP_MISSING: " + string.Join(",", missingRequired.Select(code => "U+" + code.ToString("X4"))));

            var corpusReadbacks = ValidateCorpusLookups(binding, request.primaryFontAssets,
                request.staticFontAssetId, request.staticFontAssetPath, request.consumerTexts);
            var primaryAfter = ValidatePrimaryPins(projectRoot, binding, request.primaryFontAssets, reopened);
            if (!primaryBefore.Select(row => row.afterSha256).SequenceEqual(primaryAfter.Select(row => row.afterSha256), StringComparer.Ordinal)
                || primaryAfter.Any(row => !row.unchanged))
                throw new InvalidOperationException("NATIVE_FONT_PRIMARY_DYNAMIC_ASSET_CHANGED");
            var unchangedFiles = VerifyPostEditFiles(projectRoot, manifest, request.staticFontAssetPath,
                editedFontSha, request.primaryFontAssets);

            var readback = new NativeReadback {
                schema = "monkey-unity-static-font-completion-readback/1", status = "pass",
                stageManifestSha256 = request.stageManifestSha256,
                sourceSelectionManifestSha256 = request.sourceSelectionManifestSha256,
                completionReceiptSha256 = request.completionReceiptSha256,
                staticFontAssetId = request.staticFontAssetId, staticFontAssetPath = request.staticFontAssetPath,
                staticFontAssetGuid = request.staticFontAssetGuid,
                staticFontAssetSha256Before = request.staticFontAssetSha256Before,
                staticFontAssetSha256After = editedFontSha,
                fontGuidBefore = beforeIdentity.fontGuid, fontGuidAfter = afterIdentity.fontGuid,
                atlasGuidBefore = beforeIdentity.atlasGuid, atlasGuidAfter = afterIdentity.atlasGuid,
                materialGuidBefore = beforeIdentity.materialGuid, materialGuidAfter = afterIdentity.materialGuid,
                fontLocalIdBefore = beforeIdentity.fontLocalId, fontLocalIdAfter = afterIdentity.fontLocalId,
                atlasLocalIdBefore = beforeIdentity.atlasLocalId, atlasLocalIdAfter = afterIdentity.atlasLocalId,
                materialLocalIdBefore = beforeIdentity.materialLocalId, materialLocalIdAfter = afterIdentity.materialLocalId,
                atlasWidth = reopenedAtlas.width, atlasHeight = reopenedAtlas.height,
                glyphCountBefore = request.staticFontBaseGlyphCount,
                glyphCountAfter = reopened.glyphTable.Count, characterCountBefore = request.staticFontBaseGlyphCount,
                characterCountAfter = reopened.characterTable.Count,
                requiredUnicode = request.staticFontRequiredUnicode,
                missingRequiredUnicode = Array.Empty<uint>(), addedGlyphs = request.staticFontAddedGlyphs,
                tryAddCharactersCalled = upgrade.tryAddCharactersCalled,
                primaryAssetsUnchanged = true, consumerTextCount = corpusReadbacks.Length,
                corpusLookups = corpusReadbacks, primaryAssetHashes = primaryAfter,
                unchangedFileHashes = unchangedFiles,
            };
            string readbackPath = SafeProjectPath(projectRoot, request.nativeReadbackPath);
            if (File.Exists(readbackPath))
                throw new InvalidOperationException("NATIVE_FONT_READBACK_ALREADY_EXISTS");
            Directory.CreateDirectory(Path.GetDirectoryName(readbackPath));
            File.WriteAllText(readbackPath, JsonUtility.ToJson(readback, true), new UTF8Encoding(false));
        }

        sealed class PersistentAssetIdentity
        {
            public string fontGuid, atlasGuid, materialGuid, fontFileSha256;
            public long fontLocalId, atlasLocalId, materialLocalId;
        }

        static PersistentAssetIdentity CaptureAssetIdentity(TMP_FontAsset font, Texture2D atlas, Material material)
        {
            if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(font, out var fontGuid, out long fontLocalId)
                || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(atlas, out var atlasGuid, out long atlasLocalId)
                || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material, out var materialGuid, out long materialLocalId))
                throw new InvalidOperationException("NATIVE_FONT_SUBASSET_IDENTITY_UNAVAILABLE");
            string path = AssetDatabase.GetAssetPath(font);
            return new PersistentAssetIdentity {
                fontGuid = fontGuid.ToLowerInvariant(), fontLocalId = fontLocalId,
                atlasGuid = atlasGuid.ToLowerInvariant(), atlasLocalId = atlasLocalId,
                materialGuid = materialGuid.ToLowerInvariant(), materialLocalId = materialLocalId,
                fontFileSha256 = FileHash(path),
            };
        }

        static bool SamePersistentIds(PersistentAssetIdentity before, PersistentAssetIdentity after)
        {
            return before.fontGuid == after.fontGuid && before.fontLocalId == after.fontLocalId
                && before.atlasGuid == after.atlasGuid && before.atlasLocalId == after.atlasLocalId
                && before.materialGuid == after.materialGuid && before.materialLocalId == after.materialLocalId;
        }

        static FileHashReadback[] ValidatePrimaryPins(string projectRoot, UnitySystemFonts.BindingSet binding, FontPin[] pins,
            TMP_FontAsset expectedStaticFallback)
        {
            var result = new List<FileHashReadback>();
            foreach (var pin in pins)
            {
                var specs = binding.systemFonts.fonts.Where(font => font != null && font.assetId == pin.assetId).ToArray();
                if (specs.Length != 1 || specs[0].populationMode != "DynamicOS" || specs[0].assetPath != pin.assetPath)
                    throw new InvalidOperationException("NATIVE_FONT_PRIMARY_BINDING_MISMATCH: " + pin.assetId);
                var fallbackSpec = binding.systemFonts.fonts.SingleOrDefault(row => row != null
                    && row.populationMode == "StaticSDFRequired"
                    && string.Equals(row.assetPath, AssetDatabase.GetAssetPath(expectedStaticFallback), StringComparison.Ordinal));
                if (fallbackSpec == null || !(specs[0].fallbackAssetIds ?? Array.Empty<string>()).Contains(fallbackSpec.assetId))
                    throw new InvalidOperationException("NATIVE_FONT_PRIMARY_FALLBACK_BINDING_MISMATCH: " + pin.assetId);
                string path = SafeProjectPath(projectRoot, pin.assetPath);
                string meta = path + ".meta";
                string before = FileHash(path);
                if (before != pin.assetSha256 || FileHash(meta) != pin.metaSha256
                    || AssetDatabase.AssetPathToGUID(pin.assetPath) != pin.assetGuid)
                    throw new InvalidOperationException("NATIVE_FONT_PRIMARY_HASH_OR_GUID_MISMATCH: " + pin.assetId);
                var primary = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(pin.assetPath);
                if (primary == null || primary.atlasPopulationMode != AtlasPopulationMode.DynamicOS)
                    throw new InvalidOperationException("NATIVE_FONT_PRIMARY_DYNAMIC_ASSET_MISSING: " + pin.assetId);
                if (primary.fallbackFontAssetTable == null || !primary.fallbackFontAssetTable.Contains(expectedStaticFallback))
                    throw new InvalidOperationException("NATIVE_FONT_PRIMARY_FALLBACK_ASSET_MISSING: " + pin.assetId);
                result.Add(new FileHashReadback { path = pin.assetPath, beforeSha256 = before,
                    afterSha256 = FileHash(path), unchanged = before == FileHash(path) });
            }
            return result.ToArray();
        }

        static CorpusLookupReadback[] ValidateCorpusLookups(UnitySystemFonts.BindingSet binding, FontPin[] pins,
            string staticFontAssetId, string staticFontAssetPath, string[] texts)
        {
            var primaryAssets = pins.Select(pin => AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(pin.assetPath)).ToArray();
            var fontSpecs = binding.systemFonts.fonts.ToDictionary(row => row.assetId, StringComparer.Ordinal);
            var rows = new List<CorpusLookupReadback>();
            for (int primaryIndex = 0; primaryIndex < pins.Length; primaryIndex++)
            {
                var pin = pins[primaryIndex];
                var primary = primaryAssets[primaryIndex];
                var primarySpec = fontSpecs[pin.assetId];
                var fallbackIds = primarySpec.fallbackAssetIds ?? Array.Empty<string>();
                if (!fallbackIds.Contains(staticFontAssetId)
                    || fontSpecs[staticFontAssetId].assetPath != staticFontAssetPath)
                    throw new InvalidOperationException("NATIVE_FONT_CORPUS_PRIMARY_FALLBACK_SPEC_MISMATCH: " + pin.assetId);
                var allowedPaths = new HashSet<string>(StringComparer.Ordinal) { pin.assetPath };
                foreach (var fallbackId in fallbackIds)
                {
                    if (!fontSpecs.TryGetValue(fallbackId, out var fallbackSpec))
                        throw new InvalidOperationException("NATIVE_FONT_CORPUS_FALLBACK_SPEC_MISSING: " + fallbackId);
                    allowedPaths.Add(fallbackSpec.assetPath);
                }
                foreach (string text in texts)
                {
                    var required = text.Distinct().Select(character => (uint)character).OrderBy(value => value).ToArray();
                    var missing = new List<uint>();
                    var usedPaths = new HashSet<string>(StringComparer.Ordinal);
                    foreach (uint code in required)
                    {
                        bool alternative;
                        var character = TMP_FontAssetUtilities.GetCharacterFromFontAsset(code, primary, true,
                            FontStyles.Normal, FontWeight.Regular, out alternative);
                        var assigned = character == null ? null : character.textAsset as TMP_FontAsset;
                        if (assigned == null) missing.Add(code);
                        else
                        {
                            string assignedPath = AssetDatabase.GetAssetPath(assigned);
                            if (!allowedPaths.Contains(assignedPath))
                                throw new InvalidOperationException("NATIVE_FONT_CORPUS_LOOKUP_ESCAPED_BOUND_CHAIN: " + assignedPath);
                            usedPaths.Add(assignedPath);
                        }
                    }
                    if (missing.Count > 0)
                        throw new InvalidOperationException("NATIVE_FONT_CORPUS_LOOKUP_MISSING: "
                            + string.Join(",", missing.Select(value => "U+" + value.ToString("X4"))));
                    rows.Add(new CorpusLookupReadback {
                        textSha256 = Sha256(Encoding.UTF8.GetBytes(text)), requiredUnicode = required,
                        missingUnicode = Array.Empty<uint>(), resolvedFontPaths = usedPaths.OrderBy(path => path, StringComparer.Ordinal).ToArray(),
                    });
                }
            }
            return rows.ToArray();
        }

        static FileHashReadback[] VerifyPostEditFiles(string projectRoot, StageManifest manifest, string fontPath,
            string editedFontSha, FontPin[] primaryPins)
        {
            var primaryPaths = new HashSet<string>(primaryPins.Select(row => row.assetPath), StringComparer.Ordinal);
            var rows = new List<FileHashReadback>();
            foreach (var pin in manifest.files ?? Array.Empty<StageFile>())
            {
                if (pin.path == fontPath) continue;
                string path = SafeProjectPath(projectRoot, pin.path);
                string actual = FileHash(path);
                if (actual != pin.sha256)
                    throw new InvalidOperationException("NATIVE_FONT_UNEXPECTED_PROJECT_FILE_CHANGE: " + pin.path);
                if (primaryPaths.Contains(pin.path) && actual != pin.sha256)
                    throw new InvalidOperationException("NATIVE_FONT_PRIMARY_DYNAMIC_ASSET_CHANGED: " + pin.path);
                rows.Add(new FileHashReadback { path = pin.path, beforeSha256 = pin.sha256,
                    afterSha256 = actual, unchanged = true });
            }
            string actualFontHash = FileHash(SafeProjectPath(projectRoot, fontPath));
            if (actualFontHash != editedFontSha)
                throw new InvalidOperationException("NATIVE_FONT_FINAL_ASSET_HASH_DRIFTED");
            return rows.ToArray();
        }

        static void VerifyManifestFiles(string projectRoot, StageManifest manifest, string staticFontPath, string expectedStaticSha)
        {
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var row in manifest.files ?? Array.Empty<StageFile>())
            {
                if (row == null || string.IsNullOrEmpty(row.path) || !IsSha256(row.sha256) || !seen.Add(row.path))
                    throw new InvalidOperationException("NATIVE_FONT_STAGE_FILE_INVENTORY_INVALID");
                string path = SafeProjectPath(projectRoot, row.path);
                if (!File.Exists(path)) throw new InvalidOperationException("NATIVE_FONT_STAGE_FILE_MISSING: " + row.path);
                if (row.path == staticFontPath && FileHash(path) != expectedStaticSha)
                    throw new InvalidOperationException("NATIVE_FONT_STATIC_FILE_BASE_HASH_MISMATCH");
                if (row.path != staticFontPath && FileHash(path) != row.sha256)
                    throw new InvalidOperationException("NATIVE_FONT_STAGE_FILE_HASH_MISMATCH: " + row.path);
            }
        }

        static T ReadPinned<T>(string path, string expectedSha, string code) where T : class
        {
            if (!IsSha256(expectedSha) || !File.Exists(path) || FileHash(path) != expectedSha)
                throw new InvalidOperationException(code + "_HASH_MISMATCH");
            var value = JsonUtility.FromJson<T>(File.ReadAllText(path, Encoding.UTF8));
            if (value == null) throw new InvalidOperationException(code + "_INVALID_JSON");
            return value;
        }

        static string SafeProjectPath(string projectRoot, string relative)
        {
            if (string.IsNullOrEmpty(relative) || Path.IsPathRooted(relative) || relative.IndexOf('\\') >= 0
                || relative.Split('/').Any(part => part == ".." || part == "." || part.Length == 0))
                throw new InvalidOperationException("NATIVE_FONT_UNSAFE_PROJECT_PATH: " + relative);
            string root = Path.GetFullPath(projectRoot).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string candidate = Path.GetFullPath(Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar)));
            if (!candidate.StartsWith(root, StringComparison.Ordinal))
                throw new InvalidOperationException("NATIVE_FONT_PROJECT_PATH_ESCAPES_ROOT: " + relative);
            var cursor = root;
            foreach (var part in relative.Split('/'))
            {
                cursor = Path.Combine(cursor, part);
                if ((File.Exists(cursor) || Directory.Exists(cursor))
                    && (File.GetAttributes(cursor) & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidOperationException("NATIVE_FONT_REPARSE_PATH_FORBIDDEN: " + relative);
            }
            return candidate;
        }

        static string Argument(string[] args, string key)
        {
            for (int i = 0; i + 1 < args.Length; i++) if (args[i] == key) return args[i + 1];
            return null;
        }

        static string FileHash(string path)
        {
            using (var sha = SHA256.Create()) return string.Concat(sha.ComputeHash(File.ReadAllBytes(path)).Select(value => value.ToString("x2")));
        }

        static string ReadMacOSVersion(string argument)
        {
            var process = new Process {
                StartInfo = new ProcessStartInfo("/usr/bin/sw_vers", argument) {
                    UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true,
                    CreateNoWindow = true,
                }
            };
            process.Start();
            string output = process.StandardOutput.ReadToEnd().Trim();
            process.WaitForExit();
            if (process.ExitCode != 0 || string.IsNullOrEmpty(output))
                throw new InvalidOperationException("NATIVE_FONT_MACOS_VERSION_QUERY_FAILED");
            return output;
        }

        static string Sha256(byte[] bytes)
        {
            using (var sha = SHA256.Create()) return string.Concat(sha.ComputeHash(bytes).Select(value => value.ToString("x2")));
        }

        static bool IsSha256(string value)
        {
            return value != null && value.Length == 64 && value.All(character =>
                character >= '0' && character <= '9' || character >= 'a' && character <= 'f');
        }

        static void WriteFailureReadback(Request request, string path, Exception exception)
        {
            if (File.Exists(path)) return;
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var failure = new NativeReadback {
                schema = "monkey-unity-static-font-completion-readback/1", status = "failed",
                stageManifestSha256 = request.stageManifestSha256,
                sourceSelectionManifestSha256 = request.sourceSelectionManifestSha256,
                completionReceiptSha256 = request.completionReceiptSha256,
                staticFontAssetId = request.staticFontAssetId, staticFontAssetPath = request.staticFontAssetPath,
                staticFontAssetGuid = request.staticFontAssetGuid,
                staticFontAssetSha256Before = request.staticFontAssetSha256Before,
                error = exception.ToString(), tryAddCharactersCalled = false,
            };
            File.WriteAllText(path, JsonUtility.ToJson(failure, true), new UTF8Encoding(false));
        }
    }
}
