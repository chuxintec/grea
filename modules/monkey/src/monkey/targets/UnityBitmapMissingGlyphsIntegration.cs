using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using TMPro;

public static partial class MonkeyImporter
{
    [Serializable] public sealed class BitmapMissingGlyphContract
    {
        public string schema, status, policy, sourceCodeEvidence;
        public bool missingGlyphsAreVisibleTextRecovered;
        public BitmapMissingGlyphSpec[] components;
    }
    [Serializable] public sealed class BitmapMissingGlyphSpec
    {
        public string sourceComponentId, sourceNodeId, sourceText, sourceFontId, displayText, policy, sourceCodeEvidence;
        public int[] sourceGlyphUnicode, missingGlyphUnicode;
        public bool sourceEnabled, missingGlyphsAreVisibleTextRecovered;
    }

    public static void CreateBitmapMissingGlyphs(Plan plan, Dictionary<string,GameObject> nodes,
        Dictionary<string,TMP_FontAsset> fonts)
    {
        var contract=plan==null?null:plan.bitmapMissingGlyphs;
        if(contract==null||String.IsNullOrEmpty(contract.schema))return;
        ValidateBitmapMissingGlyphContract(contract);
        var components=(plan.components??Array.Empty<ComponentSpec>()).ToDictionary(x=>x.sourceId,StringComparer.Ordinal);
        foreach(var spec in (contract.components??Array.Empty<BitmapMissingGlyphSpec>()).OrderBy(x=>x.sourceComponentId,StringComparer.Ordinal))
        {
            if(!nodes.TryGetValue(spec.sourceNodeId,out var node)||node==null)continue;
            if(!components.TryGetValue(spec.sourceComponentId,out var source)||source.type!="cc.Label"||!source.bitmapLabel||
                source.node!=spec.sourceNodeId||source.font!=spec.sourceFontId||source.text!=spec.sourceText||source.enabled!=spec.sourceEnabled)
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_SOURCE_COMPONENT_DIFFERS: "+spec.sourceComponentId);
            if(fonts==null||!fonts.TryGetValue(spec.sourceFontId,out var font)||font==null)
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_NATIVE_FONT_MISSING: "+spec.sourceFontId);
            var label=node.GetComponent<TMP_Text>();
            if(label==null||label.text!=spec.sourceText||label.font!=font)
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_LABEL_TEXT_OR_FONT_DIFFERS: "+spec.sourceComponentId);
            VerifyBitmapMissingGlyphSourceCoverage(plan,spec);
            var existing=node.GetComponent<NativeBitmapMissingGlyphs>();
            if(existing!=null)throw new InvalidOperationException("BITMAP_MISSING_GLYPH_HELPER_ALREADY_PRESENT: "+spec.sourceComponentId);
            var helper=node.AddComponent<NativeBitmapMissingGlyphs>();
            helper.Target=label;helper.TargetFontAsset=font;
            helper.SourceComponentId=spec.sourceComponentId;helper.SourceNodeId=spec.sourceNodeId;
            helper.SourceFontId=spec.sourceFontId;helper.SourceText=spec.sourceText;helper.SourceEnabled=spec.sourceEnabled;
            helper.SourceGlyphUnicode=(int[])(spec.sourceGlyphUnicode??Array.Empty<int>()).Clone();
            helper.MissingGlyphUnicode=(int[])(spec.missingGlyphUnicode??Array.Empty<int>()).Clone();
            helper.Policy=spec.policy;helper.SourceCodeEvidence=spec.sourceCodeEvidence;
            if(!helper.InstallDerivedRenderer()||label.text!=spec.sourceText)
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_RENDERER_INSTALL_FAILED: "+spec.sourceComponentId);
            var display=helper.GetDisplayText();
            if(display!=spec.displayText)
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_DISPLAY_TEXT_DIFFERS: "+spec.sourceComponentId);
        }
    }

    public static NativeBitmapMissingGlyphs.Readback[] ReadBitmapMissingGlyphs(Plan plan,
        Dictionary<string,GameObject> persistentMap, Dictionary<string,GameObject> loadedMap,
        Dictionary<string,TMP_FontAsset> fonts)
    {
        var contract=plan==null?null:plan.bitmapMissingGlyphs;
        if(contract==null||String.IsNullOrEmpty(contract.schema))return Array.Empty<NativeBitmapMissingGlyphs.Readback>();
        ValidateBitmapMissingGlyphContract(contract);
        var results=new List<NativeBitmapMissingGlyphs.Readback>();
        foreach(var spec in (contract.components??Array.Empty<BitmapMissingGlyphSpec>()).OrderBy(x=>x.sourceComponentId,StringComparer.Ordinal))
        {
            if(persistentMap==null||!persistentMap.TryGetValue(spec.sourceNodeId,out var persistentNode)||persistentNode==null)continue;
            if(loadedMap==null||!loadedMap.TryGetValue(spec.sourceNodeId,out var loadedNode)||loadedNode==null)
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_LOADED_NODE_MISSING: "+spec.sourceNodeId);
            if(fonts==null||!fonts.TryGetValue(spec.sourceFontId,out var font)||font==null)
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_NATIVE_FONT_MISSING: "+spec.sourceFontId);
            VerifyBitmapMissingGlyphSourceCoverage(plan,spec);

            var savedLabel=persistentNode.GetComponent<TMP_Text>();
            var saved=persistentNode.GetComponent<NativeBitmapMissingGlyphs>();
            if(saved==null||!EditorUtility.IsPersistent(saved))
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_HELPER_NOT_PERSISTENT: "+spec.sourceComponentId);
            var ownerIdentity=BitmapMissingGlyphPersistentIdentity(persistentNode,"owner",spec.sourceComponentId);
            var helperIdentity=BitmapMissingGlyphPersistentIdentity(saved,"helper",spec.sourceComponentId);
            var savedTargetIdentity=BitmapMissingGlyphPersistentIdentity(saved.Target,"target",spec.sourceComponentId);
            var savedFontIdentity=BitmapMissingGlyphPersistentIdentity(saved.TargetFontAsset,"font",spec.sourceComponentId);
            if(savedLabel==null||saved.Target!=savedLabel||saved.TargetFontAsset!=font||savedLabel.font!=font||
                savedLabel.text!=spec.sourceText||saved.SourceComponentId!=spec.sourceComponentId||saved.SourceNodeId!=spec.sourceNodeId||
                saved.SourceFontId!=spec.sourceFontId||saved.SourceText!=spec.sourceText||saved.SourceEnabled!=spec.sourceEnabled||
                saved.Policy!=spec.policy||saved.SourceCodeEvidence!=spec.sourceCodeEvidence||
                !BitmapMissingGlyphSame(saved.SourceGlyphUnicode,spec.sourceGlyphUnicode)||
                !BitmapMissingGlyphSame(saved.MissingGlyphUnicode,spec.missingGlyphUnicode)||
                saved.Target.font!=saved.TargetFontAsset||savedTargetIdentity.guid!=ownerIdentity.guid||
                helperIdentity.guid!=ownerIdentity.guid||savedFontIdentity.guid!=AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(font)))
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_SAVED_TYPED_FIELDS_OR_REFERENCES_DIFFER: "+spec.sourceComponentId);

            var loadedLabel=loadedNode.GetComponent<TMP_Text>();
            var loaded=loadedNode.GetComponent<NativeBitmapMissingGlyphs>();
            if(loaded==null||loadedLabel==null||loaded.Target!=loadedLabel||loaded.TargetFontAsset!=font||
                loaded.SourceComponentId!=spec.sourceComponentId||loaded.SourceNodeId!=spec.sourceNodeId||
                loaded.SourceFontId!=spec.sourceFontId||loaded.SourceText!=spec.sourceText||loadedLabel.text!=spec.sourceText||
                loaded.SourceEnabled!=spec.sourceEnabled||loaded.SourceCodeEvidence!=spec.sourceCodeEvidence||
                loadedLabel.font!=font||!BitmapMissingGlyphSame(loaded.SourceGlyphUnicode,spec.sourceGlyphUnicode)||
                !BitmapMissingGlyphSame(loaded.MissingGlyphUnicode,spec.missingGlyphUnicode)||loaded.Policy!=spec.policy)
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_LOADED_CLONE_FIELDS_OR_REFERENCES_DIFFER: "+spec.sourceComponentId);
            if(!loaded.InstallDerivedRenderer()||loadedLabel.text!=spec.sourceText||loaded.GetDisplayText()!=spec.displayText)
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_LOADED_CLONE_RENDERER_DIFFERS: "+spec.sourceComponentId);

            var row=loaded.Read(loadedLabel,spec.sourceNodeId);
            row.sourceEnabled=spec.sourceEnabled;
            row.targetGuid=savedTargetIdentity.guid;row.targetLocalFileId=savedTargetIdentity.localId;
            row.targetFontGuid=savedFontIdentity.guid;row.targetFontLocalFileId=savedFontIdentity.localId;
            row.persistedTargetReferenceVerified=true;row.persistedFontReferenceVerified=true;
            if(row.targetReferenceVerified!=true||row.targetFontReferenceVerified!=true||row.rendererInstalled!=true||
                row.sourceComponentId!=spec.sourceComponentId||row.sourceNodeId!=spec.sourceNodeId||
                row.sourceEnabled!=spec.sourceEnabled||row.sourceFontId!=spec.sourceFontId||
                row.sourceText!=spec.sourceText||row.targetText!=spec.sourceText||row.displayText!=spec.displayText||
                row.policy!=spec.policy||row.sourceCodeEvidence!=spec.sourceCodeEvidence||
                !BitmapMissingGlyphSame(row.sourceGlyphUnicode,spec.sourceGlyphUnicode)||
                !BitmapMissingGlyphSame(row.missingGlyphUnicode,spec.missingGlyphUnicode)||row.missingGlyphsAreVisibleTextRecovered)
                throw new InvalidOperationException("BITMAP_MISSING_GLYPH_READBACK_DIFFERS: "+spec.sourceComponentId);
            results.Add(row);
        }
        return results.ToArray();
    }

    static void ValidateBitmapMissingGlyphContract(BitmapMissingGlyphContract contract)
    {
        if(contract.schema!="monkey-prefab-bitmap-missing-glyphs/1"||
            contract.policy!="cocos24-bitmap-missing-glyph-skip-v1"||
            contract.sourceCodeEvidence!="cocos2d/core/renderer/utils/label/bmfont.js:235"||
            contract.missingGlyphsAreVisibleTextRecovered||
            (contract.components??Array.Empty<BitmapMissingGlyphSpec>()).Any(x=>x==null||
                string.IsNullOrEmpty(x.sourceComponentId)||string.IsNullOrEmpty(x.sourceNodeId)||
                string.IsNullOrEmpty(x.sourceFontId)||x.sourceText==null||x.displayText==null||
                x.policy!=contract.policy||x.sourceCodeEvidence!=contract.sourceCodeEvidence||
                x.missingGlyphsAreVisibleTextRecovered||x.sourceGlyphUnicode==null||x.missingGlyphUnicode==null))
            throw new InvalidOperationException("BITMAP_MISSING_GLYPH_CONTRACT_INVALID");
    }

    static void VerifyBitmapMissingGlyphSourceCoverage(Plan plan,BitmapMissingGlyphSpec spec)
    {
        var font=(plan.bitmapFonts??Array.Empty<BitmapSpec>()).SingleOrDefault(x=>x.id==spec.sourceFontId);
        if(font==null||font.glyphs==null)throw new InvalidOperationException("BITMAP_MISSING_GLYPH_SOURCE_FONT_MISSING: "+spec.sourceFontId);
        var source=font.glyphs.Select(x=>checked((int)x.unicode)).Distinct().OrderBy(x=>x).ToArray();
        if(!BitmapMissingGlyphSame(source,spec.sourceGlyphUnicode))
            throw new InvalidOperationException("BITMAP_MISSING_GLYPH_SOURCE_GLYPH_SET_DIFFERS: "+spec.sourceFontId);
        var missing=new SortedSet<int>();var display=new System.Text.StringBuilder();
        for(var i=0;i<spec.sourceText.Length;i++)
        {
            var value=(int)spec.sourceText[i];
            if(value==13)continue;
            if(value==10||source.Contains(value))display.Append(spec.sourceText[i]);
            else missing.Add(value);
        }
        if(!BitmapMissingGlyphSame(missing.ToArray(),spec.missingGlyphUnicode)||display.ToString()!=spec.displayText)
            throw new InvalidOperationException("BITMAP_MISSING_GLYPH_SOURCE_FILTER_DIFFERS: "+spec.sourceComponentId);
    }

    static bool BitmapMissingGlyphSame(int[] a,int[] b)
    {
        return (a??Array.Empty<int>()).SequenceEqual(b??Array.Empty<int>());
    }

    static (string guid,long localId) BitmapMissingGlyphPersistentIdentity(UnityEngine.Object value,string role,string sourceId)
    {
        if(value==null||!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value,out string guid,out long localId)||
            string.IsNullOrEmpty(guid)||localId==0)
            throw new InvalidOperationException("BITMAP_MISSING_GLYPH_PERSISTENT_IDENTITY_MISSING: "+role+":"+sourceId);
        return (guid,localId);
    }
}
