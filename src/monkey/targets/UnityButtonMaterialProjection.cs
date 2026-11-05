// Optional Editor-only adapter installed in an explicitly prepared retry copy.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

public static partial class MonkeyImporter
{
    [Serializable] sealed class ButtonProjectionRow
    {
        public string buttonId, buttonNativeId, nodeId, spriteId, spriteNativeId;
        public string materialId, frameId, texturePath, textureGuid;
        public bool enabled;
    }
    [Serializable] sealed class ButtonProjection
    {
        public string schema, importPlanSha256, sourceManifestSha256;
        public MonkeyUnityMaterialBindings.Spec material;
        public ButtonProjectionRow[] rows;
    }
    static Dictionary<string, ButtonProjectionRow> projectedButtons;
    static string projectedMaterialPath;

    const string ProjectionPin = "__MONKEY_PROJECTION_SHA256__";

    static partial void StampButtonMaterialProjection(Readback readback)
    {
        if (projectedButtons != null) readback.buttonMaterialProjectionSha256 = ProjectionPin;
    }

    static partial void ApplyButtonMaterialProjection(Plan plan)
    {
        const string path = "Analysis/Mappings/button-material-projection.json";
        if (Hash(path) != ProjectionPin)
            throw new InvalidOperationException("BUTTON_MATERIAL_PROJECTION_PIN");
        var projection = JsonUtility.FromJson<ButtonProjection>(File.ReadAllText(path));
        if (projection == null || projection.schema != "monkey-button-material-projection/1" ||
            projection.importPlanSha256 != Hash(Paths.plan) || projection.sourceManifestSha256 != plan.sourceManifestSha256 ||
            projection.rows == null || projection.rows.Length == 0 || projection.material == null ||
            (plan.materialBinding != null && !String.IsNullOrEmpty(plan.materialBinding.profile)))
            throw new InvalidOperationException("BUTTON_MATERIAL_PROJECTION_INPUT");

        var components = plan.components.ToDictionary(c => c.sourceId);
        var textures = plan.textures.ToDictionary(t => t.id);
        var rows = projection.rows.ToDictionary(r => r.buttonId);
        var spriteIds = new HashSet<string>(rows.Values.Select(r => r.spriteId));
        var bindings = projection.material.spriteBindings;
        if (bindings == null || spriteIds.Count != bindings.Length || !spriteIds.SetEquals(bindings.Select(b => b.sourceId)))
            throw new InvalidOperationException("BUTTON_MATERIAL_PROJECTION_BINDINGS");
        foreach (var r in rows.Values)
        {
            var b = components[r.buttonId];
            var s = components[r.spriteId];
            if (b.type != "cc.Button" || !b.convertible || b.transition != 1 || b.staticButtonBinding == null ||
                !b.staticButtonBinding.renderReady || (String.IsNullOrEmpty(b.target) ? b.node : b.target) != r.nodeId || b.nativeId != r.buttonNativeId ||
                s.type != "cc.Sprite" || s.convertible || s.node != r.nodeId || s.nativeId != r.spriteNativeId ||
                s.materials == null || s.materials.Length != 1 || s.materials[0] != r.materialId || s.spriteFrame != r.frameId ||
                s.mode != 2 || s.trim || s.untrimmedGeometryPolicy != "identity-full-frame-zero-offset" || s.enabled != r.enabled ||
                textures[r.frameId+"@original"].path != r.texturePath || AssetDatabase.AssetPathToGUID(r.texturePath) != r.textureGuid)
                throw new InvalidOperationException("BUTTON_MATERIAL_PROJECTION_RELATION: "+r.buttonId);
        }
        foreach (var id in spriteIds) components[id].convertible = true;
        plan.materialBinding = projection.material;
        projectedMaterialPath = projection.material.materialPath;
        projectedButtons = rows;
    }

    static partial void CheckProjectedButton(ComponentSpec spec, Button button, GameObject target)
    {
        if (projectedButtons == null || !projectedButtons.TryGetValue(spec.sourceId, out var row)) return;
        var image = target == null ? null : target.GetComponent<Image>();
        if (button == null || image == null || target.GetComponents<Graphic>().Length != 1 ||
            button.targetGraphic != image || image.sprite == null || image.type != Image.Type.Tiled ||
            image.enabled != row.enabled || AssetDatabase.LoadAssetAtPath<Sprite>(row.texturePath) != image.sprite ||
            image.material == null || AssetDatabase.GetAssetPath(image.material) != projectedMaterialPath)
            throw new InvalidOperationException("BUTTON_MATERIAL_TARGET_IDENTITY_MISMATCH: "+spec.sourceId);
    }
}
