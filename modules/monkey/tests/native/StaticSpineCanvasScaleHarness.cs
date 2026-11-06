using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Monkey.StaticSortQueueProxy;
using Monkey.Targets.Spine;

internal static class StaticSpineCanvasScaleHarness
{
    private static readonly JsonSerializerOptions JsonOptions = new JsonSerializerOptions { IncludeFields = true };

    private static object DeserializeWithFields(string json, Type type)
    {
        return JsonSerializer.Deserialize(json, type, JsonOptions);
    }

    private static object Field(object value, string name) => value == null ? null :
        value.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(value);

    private static void Require(bool value, string message)
    {
        if (!value) throw new InvalidOperationException(message);
    }

    private static UnitySpineNativeFactory.DataAssetSpec Read(string importJson, string renderingJson, string sourceComponentId,
        float canvasPpu, string projectRoot) =>
        UnityStaticSortQueueProxy.ReadCocosStaticSpineSpecForValidation(importJson, renderingJson,
            sourceComponentId, canvasPpu, projectRoot, DeserializeWithFields);

    private static void ExpectReject(string name, Action action, string expectedToken = null)
    {
        try
        {
            action();
        }
        catch (Exception error)
        {
            if (expectedToken != null && !error.ToString().Contains(expectedToken, StringComparison.Ordinal))
                throw new InvalidOperationException(name + " rejected for an unexpected reason: " + error, error);
            return;
        }
        throw new InvalidOperationException(name + " unexpectedly passed");
    }

    private static JsonObject ParseRendering(string renderingJson) =>
        JsonNode.Parse(renderingJson).AsObject();

    private static string Reembed(string importJson, JsonObject rendering)
    {
        var plan = JsonNode.Parse(importJson).AsObject();
        var serialized = rendering.ToJsonString(new JsonSerializerOptions { WriteIndented = false });
        plan["staticSpineRenderingJson"] = serialized;
        return plan.ToJsonString(new JsonSerializerOptions { WriteIndented = false });
    }

    private static (string importJson, string renderingJson) Mutate(
        string importJson, string renderingJson, Action<JsonObject> mutation)
    {
        var rendering = ParseRendering(renderingJson);
        mutation(rendering);
        var newRendering = rendering.ToJsonString(new JsonSerializerOptions { WriteIndented = false });
        return (Reembed(importJson, rendering), newRendering);
    }

    private static string ReembedContinuation(string importJson, JsonObject continuation)
    {
        var plan = JsonNode.Parse(importJson).AsObject();
        plan["staticSpineContinuationJson"] = continuation.ToJsonString(new JsonSerializerOptions { WriteIndented = false });
        return plan.ToJsonString(new JsonSerializerOptions { WriteIndented = false });
    }

    private static JsonArray Components(JsonObject rendering) => rendering["components"].AsArray();

    private static JsonObject Component(JsonObject rendering, int index = 0) => Components(rendering)[index].AsObject();

    private static JsonObject DataFor(JsonObject rendering, string sourceDataAssetId)
    {
        return rendering["dataAssets"].AsArray().Select(node => node.AsObject())
            .Single(row => (string)row["sourceDataAssetId"] == sourceDataAssetId);
    }

    private static string FirstComponentId(string renderingJson) =>
        (string)Component(ParseRendering(renderingJson))["sourceComponentId"];

    private static void CheckPersistedScale(string projectRoot, string assetPath, float expected)
    {
        var fullPath = Path.Combine(projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar));
        Require(File.Exists(fullPath), "persisted SkeletonData asset is absent: " + assetPath);
        var text = File.ReadAllText(fullPath);
        var match = Regex.Match(text, @"(?m)^\s*scale:\s*(?<value>[-+0-9.eE]+)\s*$");
        Require(match.Success, "persisted SkeletonData YAML has no scale value: " + assetPath);
        var actual = float.Parse(match.Groups["value"].Value, CultureInfo.InvariantCulture);
        Require(Math.Abs(actual - expected) <= 0.000001f,
            "persisted SkeletonData scale differs: path=" + assetPath + " expected=" + expected + " actual=" + actual);
    }

    private static void VerifyEverySourceComponent(string importJson, string renderingJson, string projectRoot)
    {
        using var planDoc = JsonDocument.Parse(importJson);
        using var renderDoc = JsonDocument.Parse(renderingJson);
        var plan = planDoc.RootElement;
        var render = renderDoc.RootElement;
        Require(Math.Abs(plan.GetProperty("pixelsPerUnit").GetSingle() - 100f) <= 0.000001f,
            "native-13 plan PixelsPerUnit differs from the fixture's verified Canvas PPU input");
        Require(plan.GetProperty("staticSpineRenderingJson").GetString() == renderingJson,
            "import-plan embedded Cocos render fragment differs from the candidate file bytes");
        var components = render.GetProperty("components").EnumerateArray().ToArray();
        var dataAssets = render.GetProperty("dataAssets").EnumerateArray().ToArray();
        Require(components.Length == 75, "expected all 75 source Spine component rows");
        Require(dataAssets.Length == 18, "expected all 18 source Spine data assets");
        Require(dataAssets.All(row => row.GetProperty("eligible").GetBoolean()),
            "native-13 frozen fixture contains an ineligible data asset");

        var sourceIds = new HashSet<string>(StringComparer.Ordinal);
        var sourceDataIds = new HashSet<string>(StringComparer.Ordinal);
        var assetPaths = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var component in components)
        {
            var sourceId = component.GetProperty("sourceComponentId").GetString();
            var dataId = component.GetProperty("sourceDataAssetId").GetString();
            Require(!String.IsNullOrWhiteSpace(sourceId) && sourceIds.Add(sourceId),
                "source component ID is blank or duplicated");
            Require(!String.IsNullOrWhiteSpace(dataId), "eligible source component has no data asset ID: " + sourceId);
            Require(component.GetProperty("eligible").GetBoolean(), "source component is not eligible: " + sourceId);
            var factory = DataFor(JsonNode.Parse(renderingJson).AsObject(), dataId)["factorySpec"].AsObject();
            // The plan deliberately omits scale so the verified Canvas context is
            // the only source of the native value.
            Require(!factory.ContainsKey("scale") || factory["scale"] == null || (float)factory["scale"] == 0f,
                "frozen Cocos factory spec already contains a nonzero stored scale: " + dataId);

            UnitySpineNativeFactory.DataAssetSpec spec;
            try { spec = Read(importJson, renderingJson, sourceId, 100f, projectRoot); }
            catch (Exception error)
            { throw new InvalidOperationException("production sort-spec join failed for component " + sourceId, error); }
            Require(spec.sourceAssetId == dataId, "component/data source join differs: " + sourceId);
            Require(Math.Abs(spec.sourceDefaultScale - 1f) <= 0.000001f,
                "source default scale differs from pinned Cocos profile: " + dataId);
            Require(Math.Abs(spec.targetUnitsPerSourcePixel - 1f) <= 0.000001f,
                "target units per source pixel differs from frozen mapping: " + dataId);
            var expected = spec.sourceDefaultScale * spec.targetUnitsPerSourcePixel / 100f;
            Require(Math.Abs(spec.scale - expected) <= 0.000001f && Math.Abs(spec.scale - 0.01f) <= 0.000001f,
                "resolved DataAssetSpec scale is not sourceDefaultScale*targetUnitsPerSourcePixel/canvasPpu: " + dataId);
            sourceDataIds.Add(dataId);
            assetPaths[dataId] = spec.skeletonDataAssetPath;
        }
        Require(sourceDataIds.Count == 18, "75 components do not map to exactly 18 source data assets");
        foreach (var assetPath in assetPaths.Values.Distinct(StringComparer.Ordinal))
            CheckPersistedScale(projectRoot, assetPath, 0.01f);
        VerifyRawSerializedSpecRejectsMissingCanvasScale(renderingJson);
        Console.WriteLine("native-13: components=75 dataAssets=18 uniqueDataAssets=" + sourceDataIds.Count +
            " canvasPpu=100 resolvedScale=0.01 persistedScale=0.01");
    }

    private static void VerifyRawSerializedSpecRejectsMissingCanvasScale(string renderingJson)
    {
        var rendering = ParseRendering(renderingJson);
        var firstData = rendering["dataAssets"].AsArray()[0].AsObject();
        var specType = typeof(UnitySpineNativeFactory).GetNestedType("DataAssetSpec",
            BindingFlags.Public | BindingFlags.NonPublic);
        Require(specType != null, "production DataAssetSpec type is not available");
        var rawSpec = JsonSerializer.Deserialize(firstData["factorySpec"].ToJsonString(), specType, JsonOptions);
        Require(rawSpec != null && (float)Field(rawSpec, "scale") == 0f,
            "frozen factorySpec did not deserialize an omitted scale as zero");
        var validate = typeof(UnitySpineNativeFactory).GetMethod("ValidateSpec",
            BindingFlags.Static | BindingFlags.NonPublic);
        Require(validate != null, "production Factory.ValidateSpec method was not found");
        ExpectReject("raw factory spec without canvas scale", () => validate.Invoke(null, new[] { rawSpec }),
            "SPINE_NATIVE_DATA_ASSET_SPEC_INVALID:scale:expected=finite-positive;actual=0");
        Console.WriteLine("raw frozen factory spec with omitted scale rejected before Canvas resolution");
    }

    private static void VerifyRefusals(string importJson, string renderingJson, string projectRoot)
    {
        var componentId = FirstComponentId(renderingJson);
        ExpectReject("zero canvas PPU", () => Read(importJson, renderingJson, componentId, 0f, projectRoot),
            "canvasReferencePixelsPerUnit");
        ExpectReject("negative canvas PPU", () => Read(importJson, renderingJson, componentId, -100f, projectRoot),
            "canvasReferencePixelsPerUnit");
        ExpectReject("NaN canvas PPU", () => Read(importJson, renderingJson, componentId, Single.NaN, projectRoot),
            "canvasReferencePixelsPerUnit");
        ExpectReject("infinite canvas PPU", () => Read(importJson, renderingJson, componentId, Single.PositiveInfinity, projectRoot),
            "canvasReferencePixelsPerUnit");
        ExpectReject("missing component ID", () => Read(importJson, renderingJson, "missing:component", 100f, projectRoot),
            "COCOS_STATIC_SPEC_COMPONENT_MISSING_OR_AMBIGUOUS");
        ExpectReject("embedded fragment mismatch", () => Read(importJson, renderingJson + " ", componentId, 100f, projectRoot),
            "COCOS_STATIC_SPEC_IMPORT_RENDERING_MISMATCH");
        ExpectReject("missing payload root", () => Read(importJson, renderingJson, componentId, 100f,
            projectRoot + ".missing"));

        var changedScale = Mutate(importJson, renderingJson, render =>
            Component(render)["sourceDataAssetId"] = "spineAsset:missing");
        ExpectReject("component/data mapping mismatch", () => Read(changedScale.importJson,
            changedScale.renderingJson, componentId, 100f, projectRoot));

        var duplicate = Mutate(importJson, renderingJson, render =>
            Components(render).Add(Component(render).DeepClone()));
        ExpectReject("duplicate component source ID", () => Read(duplicate.importJson,
            duplicate.renderingJson, componentId, 100f, projectRoot),
            "COCOS_STATIC_SPEC_COMPONENT_MISSING_OR_AMBIGUOUS");

        var ineligible = Mutate(importJson, renderingJson, render => Component(render)["eligible"] = false);
        ExpectReject("ineligible source component", () => Read(ineligible.importJson,
            ineligible.renderingJson, componentId, 100f, projectRoot),
            "COCOS_STATIC_SPEC_COMPONENT_MISSING_OR_AMBIGUOUS");

        var pathEscape = Mutate(importJson, renderingJson, render =>
            DataFor(render, (string)Component(render)["sourceDataAssetId"])["factorySpec"]["skeletonTextAssetPath"] = "Assets/../outside.bytes");
        ExpectReject("skeleton path traversal", () => Read(pathEscape.importJson,
            pathEscape.renderingJson, componentId, 100f, projectRoot), "COCOS_STATIC_SPEC_UNSAFE_SOURCE_PATH");

        var badSkeletonHash = Mutate(importJson, renderingJson, render =>
            DataFor(render, (string)Component(render)["sourceDataAssetId"])["factorySpec"]["skeletonSha256"] = new string('0', 64));
        ExpectReject("skeleton payload SHA mismatch", () => Read(badSkeletonHash.importJson,
            badSkeletonHash.renderingJson, componentId, 100f, projectRoot));

        var badPage = Mutate(importJson, renderingJson, render =>
            DataFor(render, (string)Component(render)["sourceDataAssetId"])["factorySpec"]["pages"][0]["sourceAtlasPage"] = "wrong-page.png");
        ExpectReject("source/native page identity mismatch", () => Read(badPage.importJson,
            badPage.renderingJson, componentId, 100f, projectRoot), "cocos-static-spine-source-page-identity-differs-from-factory-profile");

        var explicitScale = Mutate(importJson, renderingJson, render =>
            DataFor(render, (string)Component(render)["sourceDataAssetId"])["factorySpec"]["scale"] = 0.5f);
        ExpectReject("conflicting explicit scale", () => Read(explicitScale.importJson,
            explicitScale.renderingJson, componentId, 100f, projectRoot),
            "SPINE_STATIC_SPEC_FIELD_INVALID:scale");

        var zeroSourceScale = Mutate(importJson, renderingJson, render =>
            DataFor(render, (string)Component(render)["sourceDataAssetId"])["factorySpec"]["sourceDefaultScale"] = 0f);
        ExpectReject("invalid source default scale", () => Read(zeroSourceScale.importJson,
            zeroSourceScale.renderingJson, componentId, 100f, projectRoot),
            "SPINE_STATIC_SPEC_FIELD_INVALID:sourceDefaultScale");

        var zeroTargetUnits = Mutate(importJson, renderingJson, render =>
            DataFor(render, (string)Component(render)["sourceDataAssetId"])["factorySpec"]["targetUnitsPerSourcePixel"] = 0f);
        ExpectReject("invalid target unit mapping", () => Read(zeroTargetUnits.importJson,
            zeroTargetUnits.renderingJson, componentId, 100f, projectRoot),
            "SPINE_STATIC_SPEC_FIELD_INVALID:targetUnitsPerSourcePixel");

        var defaults = ParseRendering(renderingJson)["sourceComponentDefaults"].AsObject();
        var omittedPmaId = defaults["componentSourceIds"].AsArray()[0].GetValue<string>();
        var missingDefault = Mutate(importJson, renderingJson, render =>
            render["sourceComponentDefaults"]["componentSourceIds"].AsArray().RemoveAt(0));
        ExpectReject("omitted PMA without component-scoped default proof", () => Read(missingDefault.importJson,
            missingDefault.renderingJson, omittedPmaId, 100f, projectRoot),
            "cocos-static-spine-source-pma-unknown-without-exact-version-default-proof");

        var planWithPmaConflict = JsonNode.Parse(importJson).AsObject();
        var continuation = JsonNode.Parse((string)planWithPmaConflict["staticSpineContinuationJson"]).AsObject();
        // The first component's asset need not be PMA-defaulted; select an exact
        // source ID from the pinned omission scope and its data reference instead.
        var omittedComponent = Components(ParseRendering(renderingJson)).Select(node => node.AsObject())
            .Single(row => (string)row["sourceComponentId"] == omittedPmaId);
        var omittedDataId = (string)omittedComponent["sourceDataAssetId"];
        var continuationData = continuation["dataAssets"].AsArray().Select(node => node.AsObject())
            .Single(row => (string)row["sourceDataAssetId"] == omittedDataId);
        continuationData["sourcePma"]["knownValues"] = new JsonArray(JsonValue.Create(false));
        planWithPmaConflict["staticSpineContinuationJson"] = continuation.ToJsonString(new JsonSerializerOptions { WriteIndented = false });
        var conflictPlan = planWithPmaConflict.ToJsonString(new JsonSerializerOptions { WriteIndented = false });
        ExpectReject("conflicting serialized PMA evidence", () => Read(conflictPlan,
            renderingJson, omittedPmaId, 100f, projectRoot),
            "cocos-static-spine-source-pma-unknown-without-exact-version-default-proof");
        Console.WriteLine("refusals: invalid PPU, mappings, eligibility, paths, payloads, pages, source scale and explicit scale rejected");
    }

    public static int Main(string[] args)
    {
        try
        {
            if (args.Length != 2) throw new ArgumentException("expected <import-plan.json> <UnityProject-root>");
            var importJson = File.ReadAllText(args[0]);
            using var plan = JsonDocument.Parse(importJson);
            var renderingJson = plan.RootElement.GetProperty("staticSpineRenderingJson").GetString();
            Require(!String.IsNullOrWhiteSpace(renderingJson), "import plan has no frozen static Spine rendering fragment");
            VerifyEverySourceComponent(importJson, renderingJson, args[1]);
            VerifyRefusals(importJson, renderingJson, args[1]);
            Console.WriteLine("offline production boundary validated; Unity AssetDatabase GUID persistence remains Editor-only");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }
}
