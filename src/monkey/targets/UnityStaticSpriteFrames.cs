// Scene-local projection for validated source SpriteFrames. Resource loading
// and source behavior execution remain with the caller and are never inferred.
using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public static class UnityStaticSpriteFrames
{
    [Serializable]
    public sealed class ProjectionPlan
    {
        public string schema, recipeId, sourcePrefabId, sourceManifestSha256, sourcePlanSha256;
        public Entry[] entries;
    }

    [Serializable]
    public sealed class Entry
    {
        public string projectionId, parentSourceId;
        public string[] expectedParentChildSourceIds;
        public Root root;
        public SpriteChild spriteChild;
        public bool targetResourceBound;
    }

    [Serializable]
    public sealed class Root
    {
        public string name;
        public float[] size, localPosition, localScale;
        public int[] color;
        public bool active;
        public int? zIndex;
    }

    [Serializable]
    public sealed class SpriteChild
    {
        public string name, spriteFrameSourceId;
        public string logicalPath, sizeMode;
        public float[] sourceRect, originalSize, localPosition, anchor;
        public int[] color;
        public bool enabled;
    }

    [Serializable]
    public sealed class Result
    {
        public string projectionId, parentSourceId, spriteFrameSourceId;
        public float[] size;
        public bool verified, sourceBehaviorsExecuted;
    }

    public static Result[] Apply(ProjectionPlan plan,
        IDictionary<string, GameObject> sourceNodes, Func<string, Sprite> resolveSprite)
    {
        ValidatePlan(plan);
        if (sourceNodes == null || resolveSprite == null) throw new ArgumentNullException();
        var results = new List<Result>();
        foreach (var entry in plan.entries)
        {
            if (!entry.targetResourceBound)
                throw new InvalidOperationException("STATIC_SPRITE_TARGET_RESOURCE_UNBOUND: " + entry.spriteChild.spriteFrameSourceId);
            if (!sourceNodes.TryGetValue(entry.parentSourceId, out var parentObject) || parentObject == null)
                throw new InvalidOperationException("STATIC_SPRITE_PARENT_MISSING: " + entry.parentSourceId);
            var parent = parentObject.transform;
            var scene = parent.gameObject.scene;
            if (!scene.IsValid() || !scene.isLoaded)
                throw new InvalidOperationException("STATIC_SPRITE_REQUIRES_SCENE_CLONE: " + entry.parentSourceId);
            if (parent.childCount != entry.expectedParentChildSourceIds.Length)
                throw new InvalidOperationException("STATIC_SPRITE_PARENT_CHILDREN_MISMATCH: " + entry.parentSourceId);
            EnsureBehaviorsDisabled(parent);

            var name = "__monkey_static_sprite__" + entry.projectionId;
            Transform generated = null;
            for (var i = 0; i < parent.childCount; i++)
                if (parent.GetChild(i).name == name) { generated = parent.GetChild(i); break; }

            var sprite = resolveSprite(entry.spriteChild.spriteFrameSourceId);
            if (sprite == null)
                throw new InvalidOperationException("STATIC_SPRITE_TARGET_ASSET_MISSING: " + entry.spriteChild.spriteFrameSourceId);
            if (Mathf.Abs(sprite.rect.width - entry.spriteChild.originalSize[0]) > 0.01f ||
                Mathf.Abs(sprite.rect.height - entry.spriteChild.originalSize[1]) > 0.01f)
                throw new InvalidOperationException("STATIC_SPRITE_TARGET_GEOMETRY_MISMATCH: " + entry.spriteChild.spriteFrameSourceId);

            if (generated == null)
            {
                var rootObject = new GameObject(name, typeof(RectTransform));rootObject.layer=parent.gameObject.layer;
                generated = rootObject.transform;
                generated.SetParent(parent, false);
                var rootRect = (RectTransform)generated;
                rootRect.anchorMin = rootRect.anchorMax = ((RectTransform)parent).pivot;
                rootRect.pivot = new Vector2(0.5f, 0.5f);
                rootRect.sizeDelta = new Vector2(entry.root.size[0], entry.root.size[1]);
                rootRect.anchoredPosition3D = Vec3(entry.root.localPosition);
                rootRect.localScale = Vec3(entry.root.localScale);
                generated.gameObject.SetActive(entry.root.active);

                var childObject = new GameObject(entry.spriteChild.name, typeof(RectTransform), typeof(CanvasRenderer), typeof(Image));childObject.layer=parent.gameObject.layer;
                var childTransform = childObject.transform;
                childTransform.SetParent(generated, false);
                var childRect = (RectTransform)childTransform;
                childRect.anchorMin = childRect.anchorMax = Vec2(entry.spriteChild.anchor);
                childRect.pivot = Vec2(entry.spriteChild.anchor);
                childRect.sizeDelta = new Vector2(entry.spriteChild.originalSize[0], entry.spriteChild.originalSize[1]);
                childRect.anchoredPosition3D = Vec3(entry.spriteChild.localPosition);
                var image = childObject.GetComponent<Image>();
                image.sprite = sprite;
                image.type = Image.Type.Simple;
                image.preserveAspect = false;
                image.raycastTarget = false;
                image.color = Color32(entry.spriteChild.color);
                image.enabled = entry.spriteChild.enabled;
            }
            else if (generated.childCount != 1 || generated.GetChild(0).name != entry.spriteChild.name)
                throw new InvalidOperationException("STATIC_SPRITE_REENTRY_SHAPE_MISMATCH: " + entry.projectionId);

            var readImage = generated.GetChild(0).GetComponent<Image>();
            if (readImage == null || readImage.sprite != sprite || readImage.enabled != entry.spriteChild.enabled ||
                readImage.type != Image.Type.Simple)
                throw new InvalidOperationException("STATIC_SPRITE_READBACK_MISMATCH: " + entry.projectionId);
            results.Add(new Result { projectionId = entry.projectionId, parentSourceId = entry.parentSourceId,
                spriteFrameSourceId = entry.spriteChild.spriteFrameSourceId,
                size = new[] { readImage.sprite.rect.width, readImage.sprite.rect.height },
                verified = true, sourceBehaviorsExecuted = false });
        }
        return results.ToArray();
    }

    public static Result[] Read(ProjectionPlan plan, IDictionary<string, GameObject> sourceNodes,
        Func<string, Sprite> resolveSprite)
    {
        ValidatePlan(plan);
        if (sourceNodes == null || resolveSprite == null) throw new ArgumentNullException();
        var results = new List<Result>();
        foreach (var entry in plan.entries)
        {
            if (!sourceNodes.TryGetValue(entry.parentSourceId, out var parentObject) || parentObject == null)
                throw new InvalidOperationException("STATIC_SPRITE_PARENT_MISSING: " + entry.parentSourceId);
            var name = "__monkey_static_sprite__" + entry.projectionId;
            var generated = parentObject.transform.Find(name);
            var expected = resolveSprite(entry.spriteChild.spriteFrameSourceId);
            var image = generated != null && generated.childCount == 1 ? generated.GetChild(0).GetComponent<Image>() : null;
            var verified = expected != null && image != null && GeometryMatches(parentObject,generated,image,entry) && image.sprite == expected && image.enabled == entry.spriteChild.enabled &&
                Mathf.Abs(image.sprite.rect.width - entry.spriteChild.originalSize[0]) <= 0.01f &&
                Mathf.Abs(image.sprite.rect.height - entry.spriteChild.originalSize[1]) <= 0.01f;
            results.Add(new Result { projectionId = entry.projectionId, parentSourceId = entry.parentSourceId,
                spriteFrameSourceId = entry.spriteChild.spriteFrameSourceId,
                size = verified ? new[] { image.sprite.rect.width, image.sprite.rect.height } : Array.Empty<float>(),
                verified = verified, sourceBehaviorsExecuted = false });
        }
        return results.ToArray();
    }

    private static bool GeometryMatches(GameObject parent,Transform root,Image image,Entry entry) {
        var rr=root as RectTransform;var cr=image.transform as RectTransform;
        return rr!=null&&cr!=null&&parent.transform.childCount==entry.expectedParentChildSourceIds.Length+1&&root.GetSiblingIndex()==0&&
            root.parent==parent.transform&&root.gameObject.layer==parent.layer&&image.gameObject.layer==parent.layer&&
            root.gameObject.activeSelf==entry.root.active&&image.gameObject.name==entry.spriteChild.name&&
            (rr.rect.size-Vec2(entry.root.size)).sqrMagnitude<=1e-8f&&(root.localPosition-Vec3(entry.root.localPosition)).sqrMagnitude<=1e-8f&&
            (root.localScale-Vec3(entry.root.localScale)).sqrMagnitude<=1e-8f&&
            (cr.rect.size-Vec2(entry.spriteChild.originalSize)).sqrMagnitude<=1e-8f&&(cr.pivot-Vec2(entry.spriteChild.anchor)).sqrMagnitude<=1e-8f&&
            (cr.localPosition-Vec3(entry.spriteChild.localPosition)).sqrMagnitude<=1e-8f&&image.color==Color32(entry.spriteChild.color);
    }

    private static void ValidatePlan(ProjectionPlan plan)
    {
        if (plan == null || plan.schema != "monkey-prefab-static-sprite-projection-plan/1" ||
            plan.entries == null || plan.entries.Length == 0)
            throw new InvalidOperationException("STATIC_SPRITE_PLAN_INVALID");
        foreach (var entry in plan.entries)
            if (entry == null || string.IsNullOrEmpty(entry.projectionId) || string.IsNullOrEmpty(entry.parentSourceId) ||
                entry.root == null || entry.root.size == null || entry.root.size.Length != 2 ||
                entry.root.localPosition == null || entry.root.localPosition.Length != 3 ||
                entry.root.localScale == null || entry.root.localScale.Length != 3 ||
                entry.spriteChild == null || entry.spriteChild.sizeMode != "TRIMMED" ||
                entry.spriteChild.originalSize == null || entry.spriteChild.originalSize.Length != 2 ||
                entry.spriteChild.localPosition == null || entry.spriteChild.localPosition.Length != 3 ||
                entry.spriteChild.anchor == null || entry.spriteChild.anchor.Length != 2 ||
                entry.expectedParentChildSourceIds == null)
                throw new InvalidOperationException("STATIC_SPRITE_ENTRY_INVALID");
    }

    private static void EnsureBehaviorsDisabled(Transform parent)
    {
        foreach (var behaviour in parent.GetComponentsInChildren<MonoBehaviour>(true))
            if (behaviour != null && behaviour.enabled)
                throw new InvalidOperationException("STATIC_SPRITE_ENABLED_USER_BEHAVIOR: " + behaviour.GetType().FullName);
    }

    private static Vector3 Vec3(float[] v) => new Vector3(v[0], v[1], v[2]);
    private static Vector2 Vec2(float[] v) => new Vector2(v[0], v[1]);
    private static Color Color32(int[] v) => new Color32((byte)v[0], (byte)v[1], (byte)v[2], (byte)v[3]);
}
