import copy
import json
import math
import unittest
from pathlib import Path

from src.monkey.prefab_static_sort_readback import _check_block_input_events, _check_source_mask_identities, _check_text_sources, _empty_renderer_matches, verify, verify_creator


def slot_enumeration(source_id, rows):
    return {"sourceComponentId": source_id, "sourceTextSha256": "a" * 64,
            "slotCount": len(rows), "verified": True, "evidenceSha256": "b" * 64, "rows": rows}


def slot_row(slot, disposition):
    placeholder = disposition == "empty-placeholder"
    return {"slot": slot, "characterReferences": 0 if placeholder else 1,
            "visibleCharacterReferences": 0 if placeholder else 1,
            "textInfoMaterialMissing": False,
            "textInfoVertexCount": 0 if placeholder else 4,
            "textInfoTriangleIndexCount": 0 if placeholder else 6,
            "textInfoNondegenerateTriangleCount": 0 if placeholder else 2,
            "canvasVertexCount": 0 if placeholder else 4,
            "canvasTriangleIndexCount": 0 if placeholder else 6,
            "canvasNondegenerateTriangleCount": 0 if placeholder else 2,
            "disposition": disposition, "sourceAssetKind": "font", "sourceAssetGuid": "b" * 32,
            "sourceAssetLocalFileId": 11, "atlasGuid": "e" * 32, "atlasLocalFileId": 15,
            "textInfoMaterialFingerprint": "5" * 64,
            "sourceGraphicMaterialFingerprint": "4" * 64,
            "characterEvidenceSha256": "6" * 64,
            "characterAssetEvidenceSha256": "7" * 64,
            "sourceMeshSha256": None if placeholder else "1" * 64,
            "evidenceSha256": f"{slot + 1:064x}"}


CREATOR_MASK_CHECKS = (
    "maskPresent", "expectedSourceMaskPresent", "sourceAndProxyMaskRefs", "markerSourceComponentId",
    "markerMaskType", "maskType", "enabled", "inverted", "alphaThreshold", "backingType", "spriteFrame",
    "sourceAndNativeSpriteFields", "identityPresent", "identityDisabled", "identitySourceId", "identityNativeId",
    "identitySourceMaskType", "identityInverted", "identityAlphaThreshold", "identityFieldsJson",
    "identitySpriteFrameUuid", "identityNativeMaskReference", "identitySpriteFrameReference",
    "transform", "worldMatrix", "uiContentSize",
    "uiAnchor", "opacity", "layer",
)


def creator_mask_row(source_id, native_id, node, mask_type=0, enabled=True, inverted=False, threshold=0.1):
    return {"sourceId": source_id, "sourceNode": node, "sourceMaskType": mask_type,
            "nativeMaskType": mask_type, "inverted": inverted, "enabled": enabled,
            "alphaThreshold": threshold, "spriteFrameUuid": None,
            "transformVerified": True, "opacityVerified": True, "verified": True,
            "checks": {key: True for key in CREATOR_MASK_CHECKS},
            "sourceMaskEnabled": enabled, "sourceMaskInverted": inverted, "sourceAlphaThreshold": threshold,
            "expectedMaskEnabled": enabled, "expectedMaskType": mask_type,
            "expectedInverted": inverted, "expectedAlphaThreshold": threshold, "expectedSpriteFrameUuid": None,
            "sourceSpriteType": None, "sourceSpriteEnabled": None, "sourceSpriteFrameUuid": None,
            "nativeSpriteType": None, "nativeSpriteEnabled": None, "nativeSpriteFrameExpectedUuid": None,
            "sourceSpriteFingerprint": None, "nativeSpriteFingerprint": None,
            "identitySourceId": source_id, "identityNativeId": native_id, "identityNativeMaskRefMatches": True,
            "sourceLocalTransform": [0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
            "nativeLocalTransform": [0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
            "sourceWorldMatrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            "nativeWorldMatrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            "sourceSizeAnchor": [100, 50, 0.5, 0.5], "nativeSizeAnchor": [100, 50, 0.5, 0.5],
            "sourceOpacityFactor": 1, "nativeOpacityFactor": 1, "sourceLayer": 0, "nativeLayer": 0}


def initialized_slot_enumeration(saved):
    current = copy.deepcopy(saved)
    current["evidenceSha256"] = "c" * 64
    for row in current["rows"]:
        row["textInfoMaterialMissing"] = True
        row["textInfoMaterialFingerprint"] = "8" * 64
        row["characterEvidenceSha256"] = "9" * 64
        row["evidenceSha256"] = "a" * 64
    return current


def fixture():
    queue = {
        "rootScope": "root", "sourcePrefabId": "prefab-a", "prefabPath": "Assets/Game/Prefabs/A.prefab",
        "renderers": [{"node": "icon", "sourceComponentId": "sprite-a", "sourceQueueIndex": 0}],
        "drawEvents": [{"kind": "renderer", "node": "icon", "sourceComponentId": "sprite-a"}],
        "sourceChildOrder": [{"node": "root", "children": ["icon"]}],
        "sourceNodeActive": [{"node": "root", "active": True}, {"node": "icon", "active": True}],
        "sourceBlockInputEvents": [],
        "masks": [], "sourceFields": [{"sourceId": "sort-a", "nativeId": "sort-native-a", "node": "icon",
                                          "sortOrder": 7, "enabled": True}],
        "sourceSortRoots": [{"sourceId": "scope-a", "nativeId": "scope-native-a", "node": "icon", "enabled": False}],
    }
    plan = {"staticSortQueue": [queue], "sourcePrefabs": [{"sourceId": "prefab-a", "path": queue["prefabPath"]}],
            "components": [], "staticMasks": {"masks": []}}
    graphic = {
        "sourceComponentId": "sprite-a", "sourceNode": "icon", "sourceQueueIndex": 0,
        "staticSnapshotVerified": True, "verified": True, "sourceGraphicEnabled": True, "vertexCount": 4,
        "meshAssetGuid": "a" * 32, "sourceMeshSha256": "1" * 64, "proxyMeshSha256": "2" * 64,
        "capturedSourceMeshSha256": "1" * 64, "meshContentSha256": "2" * 64,
        "sourceRendererAlpha": 0.8, "proxyRendererAlpha": 0.8,
        "sourceInheritedAlpha": 0.5, "proxyInheritedAlpha": 0.5,
        "sourceEffectiveAlpha": 0.4, "proxyEffectiveAlpha": 0.4, "opacityVerified": True,
        "renderedMeshSha256": None, "sourceCulled": True, "proxyVisible": False,
        "runtimeMeshVerified": False, "transformedGeometryVerified": False,
        "sourceVertexCount": 4, "persistedProxyVertexCount": 4,
        "maxWorldVertexError": 0.0, "maxWorldNormalError": 0.0, "maxWorldTangentError": 0.0,
        "transformedTopologyMatches": True, "transformedUvMatches": True,
        "transformedColorsMatch": True, "transformedNormalsMatch": True, "transformedTangentsMatch": True,
        "sourceUvChannelVertexCounts": [4, 0, 0, 0, 4, 0, 0, 4],
        "proxyUvChannelVertexCounts": [4, 0, 0, 0, 4, 0, 0, 4],
        "renderedUvChannelVertexCounts": [],
        "sourceUvChannelDimensions": [2, 0, 0, 0, 2, 0, 0, 3],
        "proxyUvChannelDimensions": [2, 0, 0, 0, 2, 0, 0, 3],
        "renderedUvChannelDimensions": [],
    }
    order = {"sourceId": "sort-a", "node": "icon", "nativeId": "sort-native-a", "sourceSortOrder": 7,
             "enabledInSource": True, "actualSourceId": "sort-a", "actualNativeId": "sort-native-a",
             "actualSortOrder": 7, "actualEnabledInSource": True, "identityPresent": True,
             "identityComponentEnabled": False, "verified": True}
    root = {"sourceId": "scope-a", "node": "icon", "nativeId": "scope-native-a", "enabledInSource": False,
            "actualSourceId": "scope-a", "actualNativeId": "scope-native-a", "actualEnabledInSource": False,
            "identityPresent": True, "identityComponentEnabled": False, "verified": True}
    persistent = {"rootScope": "root", "readbackMode": "persistent", "provisional": False, "verified": True,
                  "persistentSnapshotVerified": True, "runtimeGeometryDeferred": True,
                  "initializedPresentationVerified": False, "sourceTreePreserved": True,
                  "structuralDiagnostics": [], "textSourcesVerified": True, "textSources": [],
                  "sourceMaskReferencesVerified": True,
                  "sourceMaskIdentitiesVerified": True, "sourceMaskIdentities": [],
                  "sourceBlockInputEventsVerified": True, "blockInputEvents": [],
                  "sourceGraphicsCovered": True, "layoutIgnored": True, "emptyRenderers": [],
                  "sourceFieldsPreserved": True, "sourceSortRootsPreserved": True,
                  "drawSequenceVerified": True, "graphics": [copy.deepcopy(graphic)], "masks": [],
                  "maskSourceIds": [], "sourceFields": [copy.deepcopy(order)], "sourceSortRoots": [copy.deepcopy(root)]}
    loaded = copy.deepcopy(persistent)
    loaded.update({"readbackMode": "initialized", "runtimeGeometryDeferred": False,
                   "initializedPresentationVerified": True})
    loaded["graphics"][0].update({"renderedMeshSha256": "2" * 64, "renderedUvChannelVertexCounts": [4, 0, 0, 0, 4, 0, 0, 4],
                                  "renderedUvChannelDimensions": [2, 0, 0, 0, 2, 0, 0, 3],
                                  "runtimeMeshVerified": True, "transformedGeometryVerified": True,
                                  "worldRectVerified": True, "transformedMeshMetricsVerified": True,
                                  "transformedMeshFingerprintVerified": False,
                                  "expectedTransformedMeshSha256": "3" * 64,
                                  "actualTransformedMeshSha256": "2" * 64,
                                  "worldMeasurementMethod": "CanvasRenderer.SetMesh-local+Transform.localToWorldMatrix.MultiplyPoint3x4",
                                  "transformedSourceMatrixExact": "1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1",
                                  "transformedProxyMatrixExact": "1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1",
                                  "transformedMatrixDifference": "firstIndex=-1;maxAbsDifference=0",
                                  "transformCaptureDiagnosticJson": json.dumps({
                                      "sourceComponentId": "sprite-a", "selectedPath": "fixture-exact-matrix",
                                      "sourceLocalToWorldMatrix": [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],
                                      "finalProxyLocalToWorldMatrix": [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]}),
                                  "proxyVisible": True})
    result = {"sourcePrefabs": [{"sourceId": "prefab-a", "staticSortFields": {
        "sourcePrefabId": "prefab-a", "prefabPath": plan["sourcePrefabs"][0]["path"],
        "verified": True, "persistentAsset": [persistent], "loadedInstance": [loaded]}}]}
    return plan, result


class StaticSortReadbackTests(unittest.TestCase):
    def test_snapshot_measures_vertices_in_persisted_world_matrix_space(self):
        proxy = (Path(__file__).parents[1] / "src/monkey/targets/UnityStaticSortQueueProxy.cs").read_text()
        self.assertIn("var sameLinearBasis = LinearBasisExactlyEquals(sourceTransform.localToWorldMatrix, proxyTransform.localToWorldMatrix)", proxy)
        self.assertIn("MatrixExactlyEquals(sourceMatrix, proxyMatrix) || sameLinearBasis || sourceAndProxyShareObservedUiPlane", proxy)
        self.assertIn("sourceMatrix.MultiplyPoint3x4(vertex)", proxy)
        self.assertIn("UnityStaticSortVertexPrecision.ImproveInitialLocalPoint(proxyMatrix.MultiplyPoint3x4", proxy)
        self.assertIn("STATIC_SORT_PROXY_VERTEX_OUTSIDE_SINGULAR_UI_PLANE:source=", proxy)
        self.assertIn("rootMeshIndexCount", proxy)
        self.assertIn("maxWorldVertexError <= .001f", proxy)

    def test_active_exact_empty_text_without_drawable_slots_keeps_typed_enumeration_carrier(self):
        proxy = (Path(__file__).parents[1] / "src/monkey/targets/UnityStaticSortQueueProxy.cs").read_text()
        self.assertIn("if (initialSlots.Count == 0)", proxy)
        self.assertIn("if (!IsExactEmptyTextSource(row, owner)", proxy)
        self.assertIn("STATIC_SORT_PROXY_TEXT_SLOT_DENOMINATOR_EMPTY", proxy)
        self.assertIn("AttachEmptyTextSlotProof(row, textOwner", proxy)
        self.assertIn("ReadEmptyTextSlotEnumerationIdentity(", proxy)
        self.assertIn("emptyTextSlotEnumerationVerified &&", proxy)

    def test_mixed_text_slots_allow_nondrawing_owner_slot_with_character_references(self):
        proxy = (Path(__file__).parents[1] / "src/monkey/targets/UnityStaticSortQueueProxy.cs").read_text()
        self.assertIn("var expectedDrawableSlots = enumeration.rows.Where(row => row.disposition == \"drawable\")", proxy)
        self.assertIn("placeholder.visibleCharacterReferences != 0", proxy)
        self.assertIn("placeholder.textInfoNondegenerateTriangleCount != 0", proxy)
        self.assertIn("placeholder.canvasNondegenerateTriangleCount != 0", proxy)
        self.assertNotIn("placeholder.characterReferences != 0", proxy)

    def test_spine_persistent_empty_pose_lookup_includes_inactive_prefab_ancestors(self):
        proxy = (Path(__file__).parents[1] / "src/monkey/targets/UnityStaticSortQueueProxy.cs").read_text()
        self.assertIn(
            "marker.GetComponentInParent<NativeStaticSortQueueProxyPresenter>(true)", proxy)
        self.assertIn("presenterProofArrayLength = presenterProofs.Length", proxy)
        self.assertIn("presenterMatchingProofCount = exactPresenterRows.Length", proxy)
        self.assertIn('";presenterFound=" + (presenter != null)', proxy)

    def test_inactive_mask_identity_is_covered_only_with_exact_typed_source_proof(self):
        plan, _ = fixture()
        queue = plan["staticSortQueue"][0]
        spec = copy.deepcopy(queue)
        spec["sourceChildOrder"] = [{"node": "root", "children": ["inactive_parent"]},
                                    {"node": "inactive_parent", "children": ["mask"]},
                                    {"node": "mask", "children": []}, {"node": "icon", "children": []}]
        spec["sourceNodeActive"] = [{"node": "root", "active": True},
                                    {"node": "inactive_parent", "active": False},
                                    {"node": "mask", "active": True}, {"node": "icon", "active": True}]
        expected = {"sourceId": "mask-source", "nativeId": "mask-native", "node": "mask", "maskType": 1,
                    "enabled": True, "inverted": False, "alphaThreshold": 0.0, "sourceFieldsJson": "{\"mask\":1}",
                    "spriteFrameUuid": None, "sourceMaterialId": None, "resolvedSourceMaterialId": None,
                    "sourceEffectId": None, "sourceEffectName": None, "sourceEffectDocumentSha256": None,
                    "unityMaskMaterialGuid": None, "unityMaskShaderPath": None, "unityMaskShaderSha256": None}
        plan["staticMasks"]["masks"] = [copy.deepcopy(expected)]
        actual = {"sourceId": "mask-source", "nativeId": "mask-native", "node": "mask",
                  "nativeMaskType": "UnityEngine.UI.Mask", "graphicType": "Monkey.StaticMaskSort.NativeStaticEllipseMaskGraphic",
                  "sourceFieldsJson": expected["sourceFieldsJson"], "spriteFrameUuid": None,
                  "sourceMaterialId": None, "resolvedSourceMaterialId": None, "sourceEffectId": None,
                  "sourceEffectName": None, "sourceEffectDocumentSha256": None,
                  "unityMaskMaterialGuid": None, "unityMaskShaderPath": None, "unityMaskShaderSha256": None,
                  "sourceMaskType": 1, "sourceEnabled": True, "sourceInverted": False,
                  "sourceActiveSelfExpected": True, "sourceActiveExpected": False,
                  "actualMaskEnabled": True, "actualGraphicEnabled": True, "actualRaycastTarget": False,
                  "sourceActiveSelf": True, "sourceActiveInHierarchy": False, "sourceSerializedActive": False,
                  "sourceSerializedActiveVerified": True, "sourceHierarchyActiveMatchesExpected": True,
                  "sourceReferenceVerified": True, "sourceIdentityVerified": True, "sourceGraphicTypeVerified": True,
                  "sourceMaskFieldsVerified": True, "sourceRenderContextDeferred": False,
                  "helperMaskReadbackVerified": True,
                  "sourceActivityStage": "persistent-serialized-scope", "sourceAlphaThreshold": 0.0,
                  "actualAlphaThreshold": 0.0, "verified": True}
        plan_row = {"sourceMaskIdentities": [copy.deepcopy(actual)], "sourceMaskIdentitiesVerified": True}
        self.assertEqual([], _check_source_mask_identities(spec, plan_row, "persistent", plan))
        jsonutility_empty = copy.deepcopy(plan_row)
        jsonutility_empty["sourceMaskIdentities"][0].update({
            "spriteFrameUuid": "", "unityMaskMaterialGuid": "", "unityMaskShaderPath": "",
            "unityMaskShaderSha256": "",
        })
        self.assertEqual([], _check_source_mask_identities(spec, jsonutility_empty, "persistent", plan))
        unexpected_optional_value = copy.deepcopy(jsonutility_empty)
        unexpected_optional_value["sourceMaskIdentities"][0]["unityMaskShaderPath"] = "Assets/unexpected.shader"
        self.assertTrue(_check_source_mask_identities(spec, unexpected_optional_value, "persistent", plan))
        loaded = copy.deepcopy(plan_row)
        loaded["sourceMaskIdentities"][0].update({"sourceActivityStage": "loaded-hierarchy",
                                                   "sourceActiveInHierarchy": False})
        self.assertEqual([], _check_source_mask_identities(spec, loaded, "loaded", plan))
        bad = copy.deepcopy(loaded)
        bad["sourceMaskIdentities"][0]["sourceActiveInHierarchy"] = True
        self.assertTrue(any("hierarchy activity differs" in message for message in
                            _check_source_mask_identities(spec, bad, "loaded", plan)))
        bad = copy.deepcopy(plan_row)
        bad["sourceMaskIdentities"][0]["sourceFieldsJson"] = "{}"
        self.assertTrue(any("component/node/fields differ" in message for message in
                            _check_source_mask_identities(spec, bad, "persistent", plan)))

    def test_persistent_inverted_mask_can_defer_only_missing_canvas_context(self):
        plan, _ = fixture()
        spec = copy.deepcopy(plan["staticSortQueue"][0])
        spec["sourceChildOrder"] = [{"node": "root", "children": ["mask"]}, {"node": "mask", "children": []}]
        spec["sourceNodeActive"] = [{"node": "root", "active": True}, {"node": "mask", "active": False}]
        fields = '{"__type__":"cc.Mask","_N$alphaThreshold":0,"_N$inverted":true}'
        expected = {"sourceId": "inverted-mask", "nativeId": "native-mask", "node": "mask", "maskType": 0,
                    "enabled": True, "inverted": True, "alphaThreshold": 0.0, "sourceFieldsJson": fields,
                    "spriteFrameUuid": "", "sourceMaterialId": "source-material", "resolvedSourceMaterialId": "internal:source-material",
                    "sourceEffectId": "internal:sprite", "sourceEffectName": "builtin-2d-sprite",
                    "sourceEffectDocumentSha256": "a" * 64, "unityMaskMaterialGuid": "", "unityMaskShaderPath": "",
                    "unityMaskShaderSha256": ""}
        plan["staticMasks"]["masks"] = [copy.deepcopy(expected)]
        actual = {"sourceId": "inverted-mask", "nativeId": "native-mask", "node": "mask",
                  "nativeMaskType": "UnityEngine.UI.Mask", "graphicType": "Monkey.StaticMaskSort.NativeStaticInvertedMaskGraphic",
                  **{key: expected[key] for key in ("sourceFieldsJson", "spriteFrameUuid", "sourceMaterialId",
                      "resolvedSourceMaterialId", "sourceEffectId", "sourceEffectName", "sourceEffectDocumentSha256",
                      "unityMaskMaterialGuid", "unityMaskShaderPath", "unityMaskShaderSha256")},
                  "sourceMaskType": 0, "sourceEnabled": True, "sourceInverted": True,
                  "sourceActiveSelfExpected": False, "sourceActiveExpected": False, "actualMaskEnabled": True,
                  "actualGraphicEnabled": True, "actualRaycastTarget": False, "sourceActiveSelf": False,
                  "sourceActiveInHierarchy": False, "sourceSerializedActive": False, "sourceSerializedActiveVerified": True,
                  "sourceHierarchyActiveMatchesExpected": True, "sourceReferenceVerified": True,
                  "sourceIdentityVerified": True, "sourceGraphicTypeVerified": True, "sourceMaskFieldsVerified": True,
                  "sourceRenderContextDeferred": True, "helperMaskReadbackVerified": False,
                  "sourceActivityStage": "persistent-serialized-scope", "sourceAlphaThreshold": 0.0,
                  "actualAlphaThreshold": 0.0, "verified": True}
        row = {"sourceMaskIdentities": [copy.deepcopy(actual)], "sourceMaskIdentitiesVerified": True}
        self.assertEqual([], _check_source_mask_identities(spec, row, "persistent", plan))
        bad = copy.deepcopy(row)
        bad["sourceMaskIdentities"][0]["sourceMaskFieldsVerified"] = False
        self.assertTrue(any("typed identity/activity proof differs" in message
                            for message in _check_source_mask_identities(spec, bad, "persistent", plan)))
        bad = copy.deepcopy(row)
        bad["sourceMaskIdentities"][0]["sourceRenderContextDeferred"] = False
        self.assertTrue(any("typed identity/activity proof differs" in message
                            for message in _check_source_mask_identities(spec, bad, "persistent", plan)))

    def test_block_input_owned_surface_requires_exact_typed_clear_alpha_contract(self):
        plan, _ = fixture()
        queue = plan["staticSortQueue"][0]
        block = {"sourceId": "input-a", "type": "cc.BlockInputEvents", "node": "input-node", "enabled": True}
        plan["components"] = [block]
        queue["sourceChildOrder"] = [{"node": "root", "children": ["input-node", "icon"]}]
        queue["sourceNodeActive"] = [{"node": "root", "active": True},
                                     {"node": "input-node", "active": True}, {"node": "icon", "active": True}]
        expected = {"sourceComponentId": "input-a", "node": "input-node", "sourceType": "cc.BlockInputEvents",
                    "sourceEnabled": True, "sourceActive": True,
                    "expectedSourceGraphicComponentId": None, "expectedSourceGraphicType": None}
        queue["sourceBlockInputEvents"] = [copy.deepcopy(expected)]
        for mode, deferred in (("persistent", True), ("loaded", False)):
            actual = {"sourceComponentId": "input-a", "sourceNode": "input-node", "surfaceType": "NativeInputBlockerSurface",
                      "expectedSourceGraphicComponentId": "", "expectedSourceGraphicType": "",
                      "nativeSourceGraphicType": "NativeInputBlockerSurface", "sourceEnabled": True, "sourceActive": True,
                      "sourceReferenceVerified": True, "blockerPresent": True, "blockerUnique": True,
                      "sourceSerializedActive": True, "sourceSerializedActiveVerified": True,
                      "sourceHierarchyActiveMatchesExpected": True, "sourceActiveSelf": True,
                      "sourceActiveInHierarchy": True,
                      "blockerEnabledMatches": True, "surfaceReferenceVerified": True, "surfaceOwnerMatches": True,
                      "surfaceOwnedMatches": True, "surfaceEnabledMatches": True, "surfaceRaycastMatches": True,
                      "surfaceEnabledActual": True, "surfaceRaycastActual": True,
                      "surfaceImplementationVerified": True, "sourceNoDrawStateVerified": False,
                      "clearAlphaMeshVerified": not deferred,
                      "surfaceMeshDeferred": deferred, "surfaceMeshVertexCount": -1 if deferred else 4,
                      "surfaceMeshIndexCount": 0 if deferred else 6, "verified": True}
            row = {"blockInputEvents": [copy.deepcopy(actual)], "sourceBlockInputEventsVerified": True}
            self.assertEqual([], _check_block_input_events(queue, row, mode, plan))
            bad = copy.deepcopy(row)
            if deferred:
                bad["blockInputEvents"][0]["clearAlphaMeshVerified"] = True
            else:
                bad["blockInputEvents"][0]["clearAlphaMeshVerified"] = False
            self.assertTrue(_check_block_input_events(queue, bad, mode, plan))
            bad = copy.deepcopy(row)
            bad["blockInputEvents"][0]["expectedSourceGraphicComponentId"] = "unexpected-source-graphic"
            self.assertTrue(_check_block_input_events(queue, bad, mode, plan))
            bad = copy.deepcopy(row)
            bad["blockInputEvents"].append(copy.deepcopy(actual))
            self.assertTrue(any("denominator" in message for message in _check_block_input_events(queue, bad, mode, plan)))

    def test_inactive_block_input_surface_is_proven_nonrendering_without_inventing_mesh(self):
        plan, _ = fixture()
        queue = copy.deepcopy(plan["staticSortQueue"][0])
        plan["components"] = [{"sourceId": "input-inactive", "type": "cc.BlockInputEvents",
                                "node": "input-node", "enabled": True}]
        queue["sourceChildOrder"] = [{"node": "root", "children": ["input-node", "icon"]}]
        queue["sourceNodeActive"] = [{"node": "root", "active": True},
                                     {"node": "input-node", "active": False}, {"node": "icon", "active": True}]
        expected = {"sourceComponentId": "input-inactive", "node": "input-node", "sourceType": "cc.BlockInputEvents",
                    "sourceEnabled": True, "sourceActive": False,
                    "expectedSourceGraphicComponentId": None, "expectedSourceGraphicType": None}
        queue["sourceBlockInputEvents"] = [copy.deepcopy(expected)]
        actual = {"sourceComponentId": "input-inactive", "sourceNode": "input-node",
                  "surfaceType": "NativeInputBlockerSurface", "expectedSourceGraphicComponentId": "",
                  "expectedSourceGraphicType": "", "nativeSourceGraphicType": "NativeInputBlockerSurface",
                  "sourceEnabled": True, "sourceActive": False, "sourceReferenceVerified": True,
                  "blockerPresent": True, "blockerUnique": True, "sourceSerializedActive": False,
                  "sourceSerializedActiveVerified": True, "sourceHierarchyActiveMatchesExpected": True,
                  "sourceActiveSelf": False, "sourceActiveInHierarchy": False, "blockerEnabledMatches": True,
                  "surfaceReferenceVerified": True, "surfaceOwnerMatches": True, "surfaceOwnedMatches": True,
                  "surfaceEnabledMatches": True, "surfaceRaycastMatches": True, "surfaceImplementationVerified": True,
                  "sourceNoDrawStateVerified": True, "surfaceEnabledActual": False, "surfaceRaycastActual": False,
                  "clearAlphaMeshVerified": False, "surfaceMeshDeferred": False, "surfaceMeshVertexCount": 0,
                  "surfaceMeshIndexCount": 0, "verified": True}
        for mode in ("persistent", "loaded"):
            row = {"blockInputEvents": [copy.deepcopy(actual)], "sourceBlockInputEventsVerified": True}
            self.assertEqual([], _check_block_input_events(queue, row, mode, plan))
            bad = copy.deepcopy(row)
            bad["blockInputEvents"][0]["surfaceRaycastActual"] = True
            self.assertTrue(any("actually disabled and non-raycast" in message
                                for message in _check_block_input_events(queue, bad, mode, plan)))
            bad = copy.deepcopy(row)
            bad["blockInputEvents"][0]["sourceActive"] = True
            self.assertTrue(_check_block_input_events(queue, bad, mode, plan))

    def test_block_input_reused_sprite_remains_in_renderer_contract(self):
        plan, _ = fixture()
        queue = plan["staticSortQueue"][0]
        plan["components"] = [
            {"sourceId": "input-a", "type": "cc.BlockInputEvents", "node": "icon", "enabled": True},
            {"sourceId": "sprite-a", "type": "cc.Sprite", "node": "icon", "enabled": True, "convertible": True},
        ]
        expected = {"sourceComponentId": "input-a", "node": "icon", "sourceType": "cc.BlockInputEvents",
                    "sourceEnabled": True, "sourceActive": True,
                    "expectedSourceGraphicComponentId": "sprite-a", "expectedSourceGraphicType": "UnityEngine.UI.Image"}
        queue["sourceBlockInputEvents"] = [copy.deepcopy(expected)]
        actual = {"sourceComponentId": "input-a", "sourceNode": "icon", "surfaceType": "UnityEngine.UI.Image",
                  "expectedSourceGraphicComponentId": "sprite-a", "expectedSourceGraphicType": "UnityEngine.UI.Image",
                  "nativeSourceGraphicType": "UnityEngine.UI.Image", "sourceEnabled": True, "sourceActive": True,
                  "sourceReferenceVerified": True, "blockerPresent": True, "blockerUnique": True,
                  "sourceSerializedActive": True, "sourceSerializedActiveVerified": True,
                  "sourceHierarchyActiveMatchesExpected": True, "sourceActiveSelf": True,
                  "sourceActiveInHierarchy": True,
                  "blockerEnabledMatches": True, "surfaceReferenceVerified": True, "surfaceOwnerMatches": True,
                  "surfaceOwnedMatches": True, "surfaceEnabledMatches": True, "surfaceRaycastMatches": True,
                  "surfaceEnabledActual": True, "surfaceRaycastActual": True,
                  "surfaceImplementationVerified": True, "sourceNoDrawStateVerified": False,
                  "clearAlphaMeshVerified": True, "surfaceMeshDeferred": False,
                  "surfaceMeshVertexCount": 4, "surfaceMeshIndexCount": 6, "verified": True}
        row = {"blockInputEvents": [actual], "sourceBlockInputEventsVerified": True}
        self.assertEqual([], _check_block_input_events(queue, row, "loaded", plan))
        bad = copy.deepcopy(row)
        bad["blockInputEvents"][0]["surfaceOwnedMatches"] = False
        self.assertTrue(any("incorrectly treated as input-only" in message or "actual typed" in message
                            for message in _check_block_input_events(queue, bad, "loaded", plan)))

    def test_inactive_reused_sprite_preserves_original_surface_fields_and_raycast(self):
        plan, _ = fixture()
        queue = copy.deepcopy(plan["staticSortQueue"][0])
        plan["components"] = [
            {"sourceId": "input-inactive", "type": "cc.BlockInputEvents", "node": "icon", "enabled": True},
            {"sourceId": "sprite-inactive", "type": "cc.Sprite", "node": "icon", "enabled": True, "convertible": True},
        ]
        queue["sourceChildOrder"] = [{"node": "root", "children": ["icon"]}]
        queue["sourceNodeActive"] = [{"node": "root", "active": True}, {"node": "icon", "active": False}]
        queue["sourceBlockInputEvents"] = [{
            "sourceComponentId": "input-inactive", "node": "icon", "sourceType": "cc.BlockInputEvents",
            "sourceEnabled": True, "sourceActive": False,
            "expectedSourceGraphicComponentId": "sprite-inactive",
            "expectedSourceGraphicType": "UnityEngine.UI.Image",
        }]
        row = {
            "blockInputEvents": [{
                "sourceComponentId": "input-inactive", "sourceNode": "icon",
                "surfaceType": "UnityEngine.UI.Image", "nativeSourceGraphicType": "UnityEngine.UI.Image",
                "expectedSourceGraphicComponentId": "sprite-inactive",
                "expectedSourceGraphicType": "UnityEngine.UI.Image",
                "sourceEnabled": True, "sourceActive": False,
                "sourceReferenceVerified": True, "blockerPresent": True, "blockerUnique": True,
                "sourceSerializedActive": False, "sourceSerializedActiveVerified": True,
                "sourceHierarchyActiveMatchesExpected": True, "sourceActiveSelf": False,
                "sourceActiveInHierarchy": False, "blockerEnabledMatches": True,
                "surfaceReferenceVerified": True, "surfaceOwnerMatches": True,
                "surfaceOwnedMatches": True, "surfaceEnabledMatches": True,
                "surfaceRaycastMatches": True, "surfaceEnabledActual": True,
                "surfaceRaycastActual": False, "surfaceImplementationVerified": True,
                "sourceNoDrawStateVerified": False, "clearAlphaMeshVerified": True,
                "surfaceMeshDeferred": False, "surfaceMeshVertexCount": 4,
                "surfaceMeshIndexCount": 6, "verified": True,
            }],
            "sourceBlockInputEventsVerified": True,
        }
        for mode in ("persistent", "loaded"):
            self.assertEqual([], _check_block_input_events(queue, row, mode, plan))
            bad = copy.deepcopy(row)
            bad["blockInputEvents"][0]["surfaceRaycastActual"] = True
            bad["blockInputEvents"][0]["surfaceRaycastMatches"] = False
            bad["blockInputEvents"][0]["verified"] = False
            self.assertTrue(_check_block_input_events(queue, bad, mode, plan))

    def test_accepts_persistent_fields_and_all_eight_loaded_uv_channels(self):
        plan, result = fixture()
        self.assertEqual([], verify(plan, result))

    def test_rejects_source_and_native_sort_order_disagreement(self):
        plan, result = fixture()
        result["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]["sourceFields"][0]["actualSortOrder"] = 8
        self.assertTrue(any("actual sort order differs" in row["message"] for row in verify(plan, result)))

    def test_rejects_proxy_that_loses_inherited_canvas_group_alpha(self):
        plan, result = fixture()
        result["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]["graphics"][0]["proxyInheritedAlpha"] = 1.0
        self.assertTrue(any("CanvasGroup/CanvasRenderer alpha evidence differs" in row["message"] for row in verify(plan, result)))

    def test_rejects_identity_carrier_enabled_on_source_tree(self):
        plan, result = fixture()
        result["sourcePrefabs"][0]["staticSortFields"]["persistentAsset"][0]["sourceSortRoots"][0]["identityComponentEnabled"] = True
        self.assertTrue(any("persistent typed identity readback differs" in row["message"] for row in verify(plan, result)))

    def test_rejects_world_vertex_error_even_when_rendered_mesh_matches_proxy(self):
        plan, result = fixture()
        result["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]["graphics"][0]["maxWorldVertexError"] = 0.002
        self.assertTrue(any("transformed mesh diagnostics differ" in row["message"] for row in verify(plan, result)))

    def test_loaded_geometry_requires_canvas_matrix_measurement_and_transform_provenance(self):
        plan, result = fixture()
        graphic = result["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]["graphics"][0]
        graphic["maxWorldVertexError"] = 0.0005
        graphic["transformedVertexDiagnostic"] = (
            "index=1;sourceLocal=0,0,0;sourceWorld=0,0,0;"
            "proxyLocal=0,0,0;proxyWorld=0.0005,0,0;distance=0.0005")
        self.assertEqual([], verify(plan, result))
        # Loaded instances can inherit a host transform absent from the saved
        # prefab asset; both captures remain measured and mapped by source ID.
        inherited_context = copy.deepcopy(result)
        capture = json.loads(inherited_context["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]
                             ["graphics"][0]["transformCaptureDiagnosticJson"])
        capture["finalProxyLocalToWorldMatrix"][3] = 1.0
        inherited_row = inherited_context["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]["graphics"][0]
        inherited_row["transformCaptureDiagnosticJson"] = json.dumps(capture)
        self.assertEqual([], verify(plan, inherited_context))
        bad = copy.deepcopy(result)
        bad["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]["graphics"][0]["worldMeasurementMethod"] = "TransformPoint"
        self.assertTrue(any("local-mesh/world-matrix measurement proof is incomplete" in row["message"]
                            for row in verify(plan, bad)))
        bad = copy.deepcopy(result)
        capture = json.loads(bad["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]["graphics"][0]["transformCaptureDiagnosticJson"])
        capture["sourceComponentId"] = "other-source"
        bad["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]["graphics"][0]["transformCaptureDiagnosticJson"] = json.dumps(capture)
        self.assertTrue(any("local-mesh/world-matrix measurement proof is incomplete" in row["message"]
                            for row in verify(plan, bad)))
        bad = copy.deepcopy(result)
        bad["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]["graphics"][0]["transformedVertexDiagnostic"] = ""
        self.assertTrue(any("omit the measured source/proxy points" in row["message"]
                            for row in verify(plan, bad)))

    def test_rejects_collected_native_structural_diagnostic(self):
        plan, result = fixture()
        result["sourcePrefabs"][0]["staticSortFields"]["persistentAsset"][0]["structuralDiagnostics"] = [
            "STATIC_SORT_PROXY_EMPTY_RENDERER_READBACK_INVALID: source=fixture"
        ]
        self.assertTrue(any("native readback reports structural failures" in row["message"] for row in verify(plan, result)))

    def test_text_slot_readback_matches_exact_persistent_assets_and_proxy(self):
        spec = {"renderers": [{"sourceComponentId": "label-a", "sourceType": "cc.Label"}]}
        text = {"sourceComponentId": "label-a", "materialSlot": 1, "ownerGuid": "a" * 32,
                "ownerScopeVerified": True,
                "fontAssetGuid": "b" * 32, "fontAssetLocalFileId": 11, "spriteAssetGuid": None,
                "spriteAssetLocalFileId": 0, "materialGuid": "c" * 32, "materialLocalFileId": 13,
                "proxyMaterialGuid": "c" * 32, "proxyMaterialLocalFileId": 13,
                "ownerFontMaterialGuid": "8" * 32, "ownerFontMaterialLocalFileId": 18,
                "ownerFontMaterialFingerprint": "3" * 64, "sourceMaterialFingerprint": "4" * 64,
                "bakedProxyMaterialFingerprint": "4" * 64, "shaderGuid": "d" * 32,
                "textureGuid": "e" * 32, "proxyMeshGuid": "f" * 32,
                "ownerLocalFileId": 12, "materialLocalFileId": 13, "shaderLocalFileId": 14,
                "textureLocalFileId": 15, "proxyMeshLocalFileId": 16,
                "sourceMeshSha256": "1" * 64, "proxyMeshSha256": "2" * 64,
                "textSlotEnumeration": slot_enumeration("label-a", [slot_row(0, "empty-placeholder"), slot_row(1, "drawable")]),
                "textInfoCharacterAssetEvidenceSha256": "7" * 64,
                "persistentTextSlotContractVerified": True,
                "persistentReferencesVerified": True, "fontAssetVerified": True, "spriteAssetVerified": True,
                "ownerFontMaterialVerified": True, "fallbackFontAssetVerified": True,
                "fallbackFontMaterialVerified": True, "fallbackAtlasVerified": True,
                "tmpFallbackDescriptorVerified": True, "transientFallbackVerified": True,
                "proxyMaterialVerified": True,
                "materialVerified": True, "shaderVerified": True, "textureVerified": True,
                "bakedProxyMeshVerified": True, "verified": True, "generatedSlotResolved": False}
        graphic = {"sourceComponentId": "label-a", "textMaterialSlot": 1, "meshAssetGuid": "f" * 32,
                   "proxyMeshSha256": "2" * 64, "materialGuid": "c" * 32, "textureGuid": "e" * 32}
        readback = {"textSources": [{"sourceNode": "label-node", "readbackMode": "persistent",
                                     "sourceComponentId": "label-a", "materialSlot": 1, "evidence": text}],
                    "textSourcesVerified": True, "graphics": [graphic]}
        spec["renderers"][0]["node"] = "label-node"
        self.assertEqual([], _check_text_sources(spec, readback, "persistent"))
        placeholder = text["textSlotEnumeration"]["rows"][0]
        placeholder.update({"characterReferences": 1, "visibleCharacterReferences": 0,
                            "textInfoVertexCount": 4, "textInfoTriangleIndexCount": 6,
                            "textInfoNondegenerateTriangleCount": 0, "canvasVertexCount": 0,
                            "canvasTriangleIndexCount": 0, "canvasNondegenerateTriangleCount": 0})
        self.assertEqual([], _check_text_sources(spec, readback, "persistent"))
        placeholder["textInfoNondegenerateTriangleCount"] = 1
        self.assertTrue(any("placeholder lacks exact slot-0 zero-draw proof" in error
                            for error in _check_text_sources(spec, readback, "persistent")))
        placeholder["textInfoNondegenerateTriangleCount"] = 0
        readback["textSources"][0]["evidence"]["persistentTextSlotContractVerified"] = False
        self.assertTrue(any("persistent TMP mapped owner" in error
                            for error in _check_text_sources(spec, readback, "persistent")))
        readback["textSources"][0]["evidence"]["persistentTextSlotContractVerified"] = True
        readback["textSources"][0]["evidence"]["textureGuid"] = "0" * 32
        self.assertTrue(any("do not match exactly one proxy graphic" in error
                            for error in _check_text_sources(spec, readback, "persistent")))
        readback["textSources"][0]["evidence"]["textureGuid"] = "e" * 32
        readback["textSources"][0]["evidence"]["textSlotEnumeration"]["rows"][0]["canvasNondegenerateTriangleCount"] = 1
        self.assertTrue(any("placeholder lacks exact slot-0 zero-draw proof" in error
                            for error in _check_text_sources(spec, readback, "persistent")))
        readback["textSources"][0]["evidence"]["textSlotEnumeration"]["rows"][0]["canvasNondegenerateTriangleCount"] = 0
        readback["textSources"].clear()
        self.assertTrue(any("TMP source component denominator differs" in error
                            for error in _check_text_sources(spec, readback, "persistent")))

    def test_loaded_text_slot_uses_exact_source_map_without_assetdb_owner_id(self):
        spec = {"renderers": [{"sourceComponentId": "label-a", "sourceType": "cc.RichText", "node": "label-node"}]}
        evidence = {"sourceComponentId": "label-a", "materialSlot": 0, "ownerGuid": None, "ownerLocalFileId": 0,
                    "ownerScopeVerified": True, "fontAssetGuid": "b" * 32, "fontAssetLocalFileId": 11,
                    "spriteAssetGuid": None, "spriteAssetLocalFileId": 0, "materialGuid": "c" * 32,
                    "proxyMaterialGuid": "c" * 32, "proxyMaterialLocalFileId": 13,
                    "ownerFontMaterialGuid": "8" * 32, "ownerFontMaterialLocalFileId": 18,
                    "ownerFontMaterialFingerprint": "3" * 64, "sourceMaterialFingerprint": "4" * 64,
                    "bakedProxyMaterialFingerprint": "4" * 64,
                    "shaderGuid": "d" * 32, "textureGuid": "e" * 32, "proxyMeshGuid": "f" * 32,
                    "materialLocalFileId": 13, "shaderLocalFileId": 14, "textureLocalFileId": 15,
                    "proxyMeshLocalFileId": 16, "sourceMeshSha256": "1" * 64, "proxyMeshSha256": "2" * 64,
                    "textSlotEnumeration": slot_enumeration("label-a", [slot_row(0, "drawable")]),
                    "currentTextSlotEnumeration": initialized_slot_enumeration(
                        slot_enumeration("label-a", [slot_row(0, "drawable")])),
                    "textInfoCharacterAssetEvidenceSha256": "7" * 64,
                    "persistentReferencesVerified": True, "fontAssetVerified": True, "spriteAssetVerified": True,
                    "ownerFontMaterialVerified": True, "fallbackFontAssetVerified": True,
                    "fallbackFontMaterialVerified": True, "fallbackAtlasVerified": True,
                    "tmpFallbackDescriptorVerified": True, "transientFallbackVerified": True,
                    "proxyMaterialVerified": True,
                    "materialVerified": True, "shaderVerified": True, "textureVerified": True,
                    "bakedProxyMeshVerified": True, "verified": True, "generatedSlotResolved": True,
                    "sourceStateVerified": True, "sourceMeshVerified": True}
        graphic = {"sourceComponentId": "label-a", "textMaterialSlot": 0, "meshAssetGuid": "f" * 32,
                   "sourceMeshSha256": "1" * 64, "proxyMeshSha256": "2" * 64,
                   "materialGuid": "c" * 32, "textureGuid": "e" * 32}
        result = {"textSources": [{"sourceNode": "label-node", "readbackMode": "loaded",
                                    "sourceComponentId": "label-a", "materialSlot": 0, "evidence": evidence}],
                  "textSourcesVerified": True, "graphics": [graphic]}
        self.assertEqual([], _check_text_sources(spec, result, "loaded"))
        evidence.update({"sourceMeshRegeneratedFromCurrentTmpVerified": True,
                         "sourceMeshPositionPairEvidenceSha256": "a" * 64,
                         "sourceMeshRegenerationEvidenceSha256": "b" * 64,
                         "currentSourceMeshSha256": "7" * 64})
        self.assertTrue(any("lacks matching strict proxy geometry proof" in error
                            for error in _check_text_sources(spec, result, "loaded")))
        graphic.update({"transformedGeometryVerified": True, "maxWorldVertexError": 0.0009,
                        "currentTextSourceMeshSha256": "7" * 64,
                        "transformedTopologyMatches": True, "transformedUvMatches": True,
                        "transformedColorsMatch": True, "transformedNormalsMatch": True,
                        "transformedTangentsMatch": True})
        self.assertEqual([], _check_text_sources(spec, result, "loaded"))
        graphic["sourceMeshSha256"] = "8" * 64
        self.assertTrue(any("lacks matching strict proxy geometry proof" in error
                            for error in _check_text_sources(spec, result, "loaded")))
        graphic["sourceMeshSha256"] = "1" * 64
        graphic["proxyMeshSha256"] = "9" * 64
        self.assertTrue(any("lacks matching strict proxy geometry proof" in error
                            for error in _check_text_sources(spec, result, "loaded")))
        graphic["proxyMeshSha256"] = "2" * 64
        graphic["maxWorldVertexError"] = 0.001001
        self.assertTrue(any("lacks matching strict proxy geometry proof" in error
                            for error in _check_text_sources(spec, result, "loaded")))
        graphic["maxWorldVertexError"] = 0.0009
        graphic["transformedTangentsMatch"] = False
        self.assertTrue(any("lacks matching strict proxy geometry proof" in error
                            for error in _check_text_sources(spec, result, "loaded")))
        graphic["transformedTangentsMatch"] = True
        evidence["sourceMeshRegeneratedFromCurrentTmpVerified"] = False
        evidence["currentTextSlotEnumeration"]["rows"][0]["characterAssetEvidenceSha256"] = "0" * 64
        self.assertTrue(any("stable text/asset/mesh evidence" in error
                            for error in _check_text_sources(spec, result, "loaded")))
        evidence["currentTextSlotEnumeration"]["rows"][0]["characterAssetEvidenceSha256"] = "7" * 64
        evidence["ownerScopeVerified"] = False
        self.assertTrue(any("loaded TMP owner does not match" in error for error in _check_text_sources(spec, result, "loaded")))

    def test_tmp_fallback_bake_requires_exact_sdk_descriptor_and_asset_provenance(self):
        spec = {"renderers": [{"sourceComponentId": "label-cjk", "sourceType": "cc.Label", "node": "label-node"}]}
        evidence = {"sourceComponentId": "label-cjk", "materialSlot": 1, "ownerGuid": None, "ownerLocalFileId": 0,
                    "ownerScopeVerified": True, "fontAssetGuid": "b" * 32, "fontAssetLocalFileId": 11,
                    "spriteAssetGuid": None, "spriteAssetLocalFileId": 0, "materialGuid": None,
                    "materialLocalFileId": 0, "proxyMaterialGuid": "c" * 32, "proxyMaterialLocalFileId": 13,
                    "ownerFontMaterialGuid": "8" * 32, "ownerFontMaterialLocalFileId": 18,
                    "fallbackFontAssetGuid": "6" * 32, "fallbackFontAssetLocalFileId": 20,
                    "fallbackFontMaterialGuid": "7" * 32, "fallbackFontMaterialLocalFileId": 21,
                    "fallbackAtlasGuid": "5" * 32, "fallbackAtlasLocalFileId": 22,
                    "tmpFallbackAlgorithm": "tmpro-fallback-font-material-v1",
                    "ownerFontMaterialFingerprint": "3" * 64, "fallbackFontMaterialFingerprint": "4" * 64,
                    "sourceMaterialFingerprint": "9" * 64, "transientFallbackFingerprint": "9" * 64,
                    "bakedProxyMaterialFingerprint": "9" * 64, "shaderGuid": "d" * 32,
                    "textureGuid": "e" * 32, "proxyMeshGuid": "f" * 32,
                    "ownerStyleVerified": True, "ownerStyleProfile": "",
                    "ownerStyleSourceComponentId": "", "persistentFallbackVariantRegistered": False,
                    "ownerLocalFileId": 0, "shaderLocalFileId": 14, "textureLocalFileId": 15,
                    "proxyMeshLocalFileId": 16, "sourceMeshSha256": "1" * 64, "proxyMeshSha256": "2" * 64,
                    "textSlotEnumeration": slot_enumeration("label-cjk", [slot_row(0, "empty-placeholder"), slot_row(1, "drawable")]),
                    "currentTextSlotEnumeration": initialized_slot_enumeration(
                        slot_enumeration("label-cjk", [slot_row(0, "empty-placeholder"), slot_row(1, "drawable")])),
                    "textInfoCharacterAssetEvidenceSha256": "7" * 64,
                    "persistentReferencesVerified": True, "ownerFontMaterialVerified": True,
                    "fallbackFontAssetVerified": True, "fallbackFontMaterialVerified": True,
                    "fallbackAtlasVerified": True, "tmpFallbackDescriptorVerified": True,
                    "transientFallbackVerified": True, "proxyMaterialVerified": True,
                    "fontAssetVerified": True, "spriteAssetVerified": True, "materialVerified": True,
                    "shaderVerified": True, "textureVerified": True, "bakedProxyMeshVerified": True,
                    "verified": True, "generatedSlotResolved": True, "sourceStateVerified": True,
                    "sourceMeshVerified": True}
        evidence["textSlotEnumeration"]["rows"][1]["sourceGraphicMaterialFingerprint"] = "9" * 64
        evidence["currentTextSlotEnumeration"] = initialized_slot_enumeration(evidence["textSlotEnumeration"])
        graphic = {"sourceComponentId": "label-cjk", "textMaterialSlot": 1, "meshAssetGuid": "f" * 32,
                   "proxyMeshSha256": "2" * 64, "materialGuid": "c" * 32, "textureGuid": "e" * 32}
        result = {"textSources": [{"sourceNode": "label-node", "readbackMode": "loaded",
                                    "sourceComponentId": "label-cjk", "materialSlot": 1, "evidence": evidence}],
                  "textSourcesVerified": True, "graphics": [graphic]}
        self.assertEqual([], _check_text_sources(spec, result, "loaded"))
        evidence["transientFallbackFingerprint"] = "0" * 64
        self.assertTrue(any("SDK fallback descriptor" in error for error in _check_text_sources(spec, result, "loaded")))

    def test_tmp_outline_fallback_profile_requires_source_style_proof(self):
        spec = {"renderers": [{"sourceComponentId": "label-cjk", "sourceType": "cc.Label", "node": "label-node"}]}
        evidence = {
            "sourceComponentId": "label-cjk", "materialSlot": 1, "ownerGuid": None, "ownerLocalFileId": 0,
            "ownerScopeVerified": True, "fontAssetGuid": "b" * 32, "fontAssetLocalFileId": 11,
            "spriteAssetGuid": None, "spriteAssetLocalFileId": 0, "materialGuid": None,
            "materialLocalFileId": 0, "proxyMaterialGuid": "c" * 32, "proxyMaterialLocalFileId": 13,
            "ownerFontMaterialGuid": "8" * 32, "ownerFontMaterialLocalFileId": 18,
            "fallbackFontAssetGuid": "6" * 32, "fallbackFontAssetLocalFileId": 20,
            "fallbackFontMaterialGuid": "7" * 32, "fallbackFontMaterialLocalFileId": 21,
            "fallbackAtlasGuid": "5" * 32, "fallbackAtlasLocalFileId": 22,
            "tmpFallbackAlgorithm": "tmpro-fallback-font-material-v1+native-static-text-outline-v1",
            "ownerFontMaterialFingerprint": "3" * 64, "fallbackFontMaterialFingerprint": "4" * 64,
            "sourceMaterialFingerprint": "9" * 64, "transientFallbackFingerprint": "9" * 64,
            "bakedProxyMaterialFingerprint": "9" * 64, "shaderGuid": "d" * 32,
            "textureGuid": "e" * 32, "proxyMeshGuid": "f" * 32,
            "ownerLocalFileId": 0, "shaderLocalFileId": 14, "textureLocalFileId": 15,
            "proxyMeshLocalFileId": 16, "sourceMeshSha256": "1" * 64, "proxyMeshSha256": "2" * 64,
            "textSlotEnumeration": slot_enumeration("label-cjk", [slot_row(0, "empty-placeholder"), slot_row(1, "drawable")]),
            "currentTextSlotEnumeration": initialized_slot_enumeration(
                slot_enumeration("label-cjk", [slot_row(0, "empty-placeholder"), slot_row(1, "drawable")])),
            "textInfoCharacterAssetEvidenceSha256": "7" * 64,
            "persistentReferencesVerified": True, "ownerFontMaterialVerified": True,
            "fallbackFontAssetVerified": True, "fallbackFontMaterialVerified": True,
            "fallbackAtlasVerified": True, "tmpFallbackDescriptorVerified": True,
            "transientFallbackVerified": True, "proxyMaterialVerified": True,
            "fontAssetVerified": True, "spriteAssetVerified": True, "materialVerified": True,
            "shaderVerified": True, "textureVerified": True, "bakedProxyMeshVerified": True,
            "verified": True, "generatedSlotResolved": True, "sourceStateVerified": True,
            "sourceMeshVerified": True, "persistentFallbackVariantRegistered": True,
            "ownerStyleVerified": True, "ownerStyleProfile": "native-static-text-outline-font-material-v1",
            "ownerStyleOutlineWidth": 1.25,
            "ownerStyleOutlineColor": {"r": 0.1, "g": 0.2, "b": 0.3, "a": 1.0},
            "ownerStyleSourceComponentId": "label-cjk", "ownerStyleSourceFontAssetGuid": "a" * 32,
            "ownerStyleSourceFontAssetLocalFileId": 30, "ownerStyleSourceFontMaterialGuid": "9" * 32,
            "ownerStyleSourceFontMaterialLocalFileId": 31, "ownerStyleSourceFontMaterialFingerprint": "2" * 64,
        }
        evidence["textSlotEnumeration"]["rows"][1]["sourceGraphicMaterialFingerprint"] = "9" * 64
        evidence["currentTextSlotEnumeration"] = initialized_slot_enumeration(evidence["textSlotEnumeration"])
        graphic = {"sourceComponentId": "label-cjk", "textMaterialSlot": 1, "meshAssetGuid": "f" * 32,
                   "proxyMeshSha256": "2" * 64, "materialGuid": "c" * 32, "textureGuid": "e" * 32}
        result = {"textSources": [{"sourceNode": "label-node", "readbackMode": "loaded",
                                   "sourceComponentId": "label-cjk", "materialSlot": 1, "evidence": evidence}],
                  "textSourcesVerified": True, "graphics": [graphic]}
        self.assertEqual([], _check_text_sources(spec, result, "loaded"))
        evidence["ownerStyleSourceComponentId"] = "other-label"
        self.assertTrue(any("SDK fallback descriptor" in error for error in _check_text_sources(spec, result, "loaded")))

    def test_rejects_loss_of_uv4_uv7_or_native_canvas_mesh_channels(self):
        plan, result = fixture()
        result["sourcePrefabs"][0]["staticSortFields"]["persistentAsset"][0]["graphics"][0]["proxyUvChannelVertexCounts"][4] = 0
        self.assertTrue(any("UV channels 0–7" in row["message"] for row in verify(plan, result)))
        plan, result = fixture()
        result["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]["graphics"][0]["renderedUvChannelDimensions"][7] = 2
        self.assertTrue(any("CanvasRenderer UV channels" in row["message"] for row in verify(plan, result)))

    def test_float_transform_accepts_only_measured_position_error_and_exact_other_channels(self):
        plan, result = fixture()
        loaded = result["sourcePrefabs"][0]["staticSortFields"]["loadedInstance"][0]
        graphic = loaded["graphics"][0]
        self.assertEqual([], verify(plan, result))
        graphic["maxWorldVertexError"] = 0.001001
        self.assertTrue(any("transformed mesh diagnostics differ" in row["message"] for row in verify(plan, result)))
        graphic["maxWorldVertexError"] = 0.0001
        graphic["transformedUvMatches"] = False
        self.assertTrue(any("transformed mesh diagnostics differ" in row["message"] for row in verify(plan, result)))
        graphic["transformedUvMatches"] = True
        graphic["expectedTransformedMeshSha256"] = "2" * 64
        self.assertTrue(any("fingerprint evidence is incomplete" in row["message"] for row in verify(plan, result)))

    def test_null_sprite_uses_a_persistent_no_draw_carrier_not_a_fabricated_mesh(self):
        plan, result = fixture()
        spec = plan["staticSortQueue"][0]
        empty_spec = {"node": "newicon", "sourceComponentId": "sprite-empty", "sourceType": "cc.Sprite",
                      "expectedGraphicType": "UnityEngine.UI.Image", "sourceEnabled": True, "sourceActive": True,
                      "sourceTextureBound": False, "sourceTextEmpty": False, "sourceFontMissing": False}
        spec["renderers"].append(empty_spec)
        spec["drawEvents"].append({"kind": "renderer", "node": "newicon", "sourceComponentId": "sprite-empty"})
        empty = {"sourceComponentId": "sprite-empty", "sourceNode": "newicon", "sourceType": "cc.Sprite",
                 "sourceComponentType": "UnityEngine.UI.Image", "noDrawReason": "source-sprite-frame-null-native-image-disabled-zero-mesh",
                 "carrierGuid": "b" * 32, "carrierLocalFileId": 124, "sourceEnabled": True, "sourceActive": True,
                 "sourceActiveSelf": True, "sourceActivityMatchesExpected": True,
                 "sourceSerializedActive": True, "sourceSerializedActiveVerified": True,
                 "sourceHierarchyActiveMatchesExpected": True, "sourceActivityStage": "persistent-serialized-scope",
                 "sourceActiveInHierarchy": True, "nativeGraphicEnabled": False, "nativeComponentEnabled": False,
                 "sourceTextureBound": False, "nativeTextureBound": False, "sourceTextEmpty": False,
                 "nativeTextEmpty": False, "sourceFontMissing": False, "nativeFontMissing": False,
                 "sourceMeshPresent": False, "sourceMeshVertexCount": 0, "sourceCanvasMaterialCount": 1,
                 "actualQueueIndex": 1, "carrierPresent": True, "sourceReferenceVerified": True,
                 "carrierAssetIdentityVerified": True, "carrierOwnerScopeVerified": False,
                 "typedFieldsVerified": True, "sourceCommandsEmpty": False, "nativeCommandsEmpty": False,
                 "verified": True}
        binding = result["sourcePrefabs"][0]["staticSortFields"]
        loaded_empty = copy.deepcopy(empty)
        loaded_empty.update({"carrierGuid": "", "carrierLocalFileId": 0, "carrierAssetIdentityVerified": False,
                             "carrierOwnerScopeVerified": True,
                             "sourceActivityStage": "loaded-hierarchy-plus-serialized-scope"})
        binding["persistentAsset"][0]["emptyRenderers"] = [copy.deepcopy(empty)]
        binding["loadedInstance"][0]["emptyRenderers"] = [copy.deepcopy(loaded_empty)]
        self.assertEqual([], verify(plan, result))

        stale = copy.deepcopy(empty)
        stale.update({"noDrawReason": "source-sprite-frame-null-native-image-disabled-no-material",
                      "sourceMeshPresent": False, "sourceMeshVertexCount": 0, "sourceCanvasMaterialCount": 0})
        loaded_stale = copy.deepcopy(stale)
        loaded_stale.update({"carrierGuid": "", "carrierLocalFileId": 0, "carrierAssetIdentityVerified": False,
                             "carrierOwnerScopeVerified": True,
                             "sourceActivityStage": "loaded-hierarchy-plus-serialized-scope"})
        binding["persistentAsset"][0]["emptyRenderers"] = [copy.deepcopy(stale)]
        binding["loadedInstance"][0]["emptyRenderers"] = [copy.deepcopy(loaded_stale)]
        self.assertEqual([], verify(plan, result))
        stale["sourceCanvasMaterialCount"] = 1
        loaded_stale["sourceCanvasMaterialCount"] = 1
        binding["persistentAsset"][0]["emptyRenderers"] = [copy.deepcopy(stale)]
        binding["loadedInstance"][0]["emptyRenderers"] = [copy.deepcopy(loaded_stale)]
        self.assertTrue(any("empty-renderer" in row["message"] or "renderer" in row["message"]
                            for row in verify(plan, result)))
        loaded_stale["sourceCanvasMaterialCount"] = 0
        loaded_stale["carrierOwnerScopeVerified"] = False
        binding["persistentAsset"][0]["emptyRenderers"] = [copy.deepcopy(stale)]
        binding["loadedInstance"][0]["emptyRenderers"] = [copy.deepcopy(loaded_stale)]
        self.assertTrue(any("empty-renderer" in row["message"] or "renderer" in row["message"]
                            for row in verify(plan, result)))
        binding["loadedInstance"][0]["emptyRenderers"][0]["nativeGraphicEnabled"] = True
        self.assertTrue(any("empty renderer typed evidence differs" in row["message"] for row in verify(plan, result)))

    def test_empty_text_graphics_and_disabled_sources_keep_typed_field_evidence(self):
        plan, result = fixture()
        spec = plan["staticSortQueue"][0]
        label = {"node": "empty-label", "sourceComponentId": "label-empty", "sourceType": "cc.Label",
                 "expectedGraphicType": "TMPro.TextMeshProUGUI", "sourceEnabled": True, "sourceActive": True,
                 "sourceTextureBound": False, "sourceText": "", "nativeTextExpectation": "",
                 "sourceTextEmpty": True, "sourceFontMissing": False}
        graphics_fields = '{"__type__":"cc.Graphics","_materials":[{"__uuid__":"material-id"}]}'
        import hashlib
        fields_sha = hashlib.sha256(graphics_fields.encode("utf-8")).hexdigest()
        native_graphics = {"node": "graphics", "sourceComponentId": "graphics-empty", "sourceType": "cc.Graphics",
                           "expectedGraphicType": "NativeStaticGraphics", "sourceEnabled": True, "sourceActive": True,
                           "sourceCommandsEmpty": True, "sourceDrawingCommands": "not-serialized-empty-in-fixed-state",
                           "sourceFieldsJson": graphics_fields, "sourceFieldsSha256": fields_sha,
                           "sourceMaterialGuids": ["c" * 32]}
        spec["renderers"].extend([label, native_graphics])
        disabled = {"node": "disabled", "sourceComponentId": "sprite-disabled", "sourceType": "cc.Sprite",
                    "expectedGraphicType": "UnityEngine.UI.Image", "sourceEnabled": False, "sourceActive": True,
                    "sourceTextureBound": True, "sourceTextEmpty": False, "sourceFontMissing": False}
        spec["nonDrawRenderers"] = [disabled]
        spec["drawEvents"].extend([
            {"kind": "renderer", "node": label["node"], "sourceComponentId": label["sourceComponentId"]},
            {"kind": "renderer", "node": native_graphics["node"], "sourceComponentId": native_graphics["sourceComponentId"]},
        ])

        def carrier(sid, node, native_type, reason, queue, **extra):
            return {"sourceComponentId": sid, "sourceNode": node, "sourceType": extra.pop("sourceType"),
                    "sourceComponentType": native_type, "noDrawReason": reason, "carrierGuid": "d" * 32,
                    "carrierLocalFileId": 125, "sourceEnabled": extra.pop("sourceEnabled"),
                    "sourceActive": True, "sourceActiveSelf": True, "sourceActivityMatchesExpected": True,
                    "sourceSerializedActive": True, "sourceSerializedActiveVerified": True,
                    "sourceHierarchyActiveMatchesExpected": True, "sourceActivityStage": "persistent-serialized-scope",
                    "sourceActiveInHierarchy": True, "carrierPresent": True,
                    "carrierAssetIdentityVerified": True, "carrierOwnerScopeVerified": False,
                    "sourceReferenceVerified": True, "typedFieldsVerified": True, "verified": True,
                    "actualQueueIndex": queue, "sourceMeshPresent": False, "sourceMeshVertexCount": 0,
                    "nativeGraphicEnabled": False, "nativeComponentEnabled": False,
                    "sourceTextureBound": False, "nativeTextureBound": False,
                    "sourceTextEmpty": True, "nativeTextEmpty": True,
                    "sourceFontMissing": False, "nativeFontMissing": False,
                    "sourceCommandsEmpty": False, "nativeCommandsEmpty": False, **extra}

        label_row = carrier("label-empty", "empty-label", "TMPro.TextMeshProUGUI", "source-text-empty-zero-mesh", 2,
                            sourceType="cc.Label", sourceEnabled=True, sourceText="", nativeText="",
                            sourceTextureBound=False, sourceTextEmpty=True, nativeTextEmpty=True,
                            nativeGraphicEnabled=True)
        empty_hash = hashlib.sha256(b"").hexdigest()
        slot_row = {"slot": 0, "characterReferences": 0, "visibleCharacterReferences": 0,
                    "textInfoMaterialMissing": True, "textInfoVertexCount": 0, "textInfoTriangleIndexCount": 0,
                    "textInfoNondegenerateTriangleCount": 0, "canvasVertexCount": 0,
                    "canvasTriangleIndexCount": 0, "canvasNondegenerateTriangleCount": 0,
                    "disposition": "empty-placeholder", "sourceAssetKind": "font", "sourceAssetGuid": "b" * 32,
                    "sourceAssetLocalFileId": 11, "atlasGuid": "e" * 32, "atlasLocalFileId": 15,
                    "textInfoMaterialFingerprint": "", "sourceGraphicMaterialFingerprint": "",
                    "characterEvidenceSha256": "a" * 64, "characterAssetEvidenceSha256": "c" * 64,
                    "sourceMeshSha256": None}
        from src.monkey.prefab_static_sort_readback import _empty_text_slot_row_hash
        slot_row["evidenceSha256"] = _empty_text_slot_row_hash(slot_row)
        enumeration = {"sourceComponentId": "label-empty", "sourceTextSha256": empty_hash, "slotCount": 1,
                       "verified": True, "rows": [slot_row]}
        enumeration["evidenceSha256"] = hashlib.sha256(
            ("label-empty|" + empty_hash + "|1|" + slot_row["evidenceSha256"]).encode("utf-8")).hexdigest()
        label_row.update({"emptyTextSlotEnumerationVerified": True,
                          "emptyTextSlotEnumerationProof": {"sourceComponentId": "label-empty",
                              "ownerScopeVerified": True, "persistentReferencesVerified": True, "verified": True,
                              "slotEnumeration": copy.deepcopy(enumeration), "currentSlotEnumeration": None}})
        graphics_row = carrier("graphics-empty", "graphics", "NativeStaticGraphics",
                               "source-graphics-command-stream-proven-empty", 3,
                               sourceType="cc.Graphics", sourceEnabled=True, sourceCommandsEmpty=True,
                               nativeCommandsEmpty=True, sourceDrawingCommands="not-serialized-empty-in-fixed-state",
                               sourceFieldsSha256=fields_sha, sourceMaterialGuids=["c" * 32],
                               actualSourceMaterialGuids=["c" * 32], nativeComponentEnabled=False,
                               sourceTextEmpty=False, nativeTextEmpty=False)
        disabled_row = carrier("sprite-disabled", "disabled", "UnityEngine.UI.Image", "source-renderer-disabled", -1,
                               sourceType="cc.Sprite", sourceEnabled=False, sourceTextureBound=True, nativeTextureBound=True,
                               sourceTextEmpty=False, nativeTextEmpty=False)
        binding = result["sourcePrefabs"][0]["staticSortFields"]
        persistent_rows = [copy.deepcopy(label_row), copy.deepcopy(graphics_row), copy.deepcopy(disabled_row)]
        loaded_rows = copy.deepcopy(persistent_rows)
        for row in loaded_rows:
            row.update({"carrierGuid": "", "carrierLocalFileId": 0,
                        "carrierAssetIdentityVerified": False, "carrierOwnerScopeVerified": True,
                        "sourceActivityStage": "loaded-hierarchy-plus-serialized-scope"})
        binding["persistentAsset"][0]["emptyRenderers"] = persistent_rows
        binding["loadedInstance"][0]["emptyRenderers"] = loaded_rows
        loaded_label = binding["loadedInstance"][0]["emptyRenderers"][0]
        loaded_label["emptyTextSlotEnumerationProof"]["currentSlotEnumeration"] = copy.deepcopy(enumeration)
        self.assertEqual([], verify(plan, result))
        persistent_label = binding["persistentAsset"][0]["emptyRenderers"][0]
        persistent_label["emptyTextSlotEnumerationProof"]["currentSlotEnumeration"] = {
            "sourceComponentId": "", "sourceTextSha256": "", "slotCount": 0,
            "verified": False, "evidenceSha256": "", "rows": [],
        }
        label["sourceText"] = None
        label["nativeTextExpectation"] = None
        self.assertEqual([], verify(plan, result))
        invalid_empty = copy.deepcopy(persistent_label)
        invalid_empty["emptyTextSlotEnumerationProof"]["slotEnumeration"]["rows"][0]["characterReferences"] = 1
        binding["persistentAsset"][0]["emptyRenderers"][0] = invalid_empty
        self.assertTrue(any("empty renderer typed evidence differs" in row["message"] for row in verify(plan, result)))
        binding["persistentAsset"][0]["emptyRenderers"][0] = persistent_label
        invalid = copy.deepcopy(binding["loadedInstance"][0]["emptyRenderers"][0])
        invalid["emptyTextSlotEnumerationProof"]["currentSlotEnumeration"]["rows"][0]["disposition"] = "drawable"
        binding["loadedInstance"][0]["emptyRenderers"][0] = invalid
        self.assertTrue(any("empty renderer typed evidence differs" in row["message"] for row in verify(plan, result)))
        binding["loadedInstance"][0]["emptyRenderers"][0] = loaded_label
        invalid = copy.deepcopy(binding["persistentAsset"][0]["emptyRenderers"][0])
        invalid["sourceText"] = "nonempty"
        binding["persistentAsset"][0]["emptyRenderers"][0] = invalid
        self.assertTrue(any("empty renderer typed evidence differs" in row["message"] for row in verify(plan, result)))
        binding["persistentAsset"][0]["emptyRenderers"][0] = label_row
        binding["persistentAsset"][0]["emptyRenderers"][1]["actualSourceMaterialGuids"] = []
        self.assertTrue(any("empty renderer typed evidence differs" in row["message"] for row in verify(plan, result)))

    def test_persistent_activity_uses_serialized_scope_chain_while_loaded_requires_hierarchy(self):
        expected = {"node": "icon", "sourceComponentId": "sprite-empty", "sourceType": "cc.Sprite",
                    "expectedGraphicType": "UnityEngine.UI.Image", "sourceEnabled": True, "sourceActive": True,
                    "sourceTextureBound": False, "sourceTextEmpty": False, "sourceFontMissing": False}
        actual = {"sourceNode": "icon", "sourceType": "cc.Sprite", "sourceComponentType": "UnityEngine.UI.Image",
                  "sourceEnabled": True, "sourceActive": True, "sourceActiveSelf": True,
                  "sourceSerializedActive": True, "sourceSerializedActiveVerified": True,
                  "sourceHierarchyActiveMatchesExpected": False, "sourceActivityMatchesExpected": True,
                  "sourceActivityStage": "persistent-serialized-scope", "sourceActiveInHierarchy": False,
                  "sourceTextureBound": False, "nativeTextureBound": False, "sourceText": "",
                  "nativeTextExpectation": "", "sourceTextEmpty": False, "sourceFontMissing": False,
                  "sourceReferenceVerified": True, "typedFieldsVerified": True, "carrierPresent": True,
                  "carrierAssetIdentityVerified": True, "carrierOwnerScopeVerified": False,
                  "carrierGuid": "f" * 32, "carrierLocalFileId": 412, "verified": True,
                  "noDrawReason": "source-sprite-frame-null-native-image-disabled-no-material",
                  "nativeGraphicEnabled": False, "sourceMeshPresent": False, "sourceMeshVertexCount": 0,
                  "sourceCanvasMaterialCount": 0}
        self.assertTrue(_empty_renderer_matches(expected, actual, "persistent"))

        ancestor_inactive = copy.deepcopy(actual)
        ancestor_inactive.update({"sourceSerializedActive": False, "sourceActivityMatchesExpected": False})
        self.assertFalse(_empty_renderer_matches(expected, ancestor_inactive, "persistent"))

        loaded_inactive = copy.deepcopy(actual)
        loaded_inactive.update({"sourceActivityStage": "loaded-hierarchy-plus-serialized-scope",
                                "sourceActivityMatchesExpected": False,
                                "carrierGuid": "", "carrierLocalFileId": 0,
                                "carrierAssetIdentityVerified": False, "carrierOwnerScopeVerified": True})
        self.assertFalse(_empty_renderer_matches(expected, loaded_inactive, "loaded"))

    def test_rejects_incomplete_or_duplicate_persistent_queue_rows(self):
        plan, result = fixture()
        binding = result["sourcePrefabs"][0]["staticSortFields"]
        binding["persistentAsset"] = []
        self.assertTrue(any("persistent queue scope count differs" in row["message"] for row in verify(plan, result)))
        plan, result = fixture()
        binding = result["sourcePrefabs"][0]["staticSortFields"]
        binding["loadedInstance"].append(copy.deepcopy(binding["loadedInstance"][0]))
        self.assertTrue(any("loaded queue scope count differs" in row["message"] for row in verify(plan, result)))

    def test_creator_verifies_persistent_and_initialized_source_sort_fields(self):
        spec = {"rootScope": "root", "sourcePrefabId": "prefab-c", "prefabPath": "db://assets/A.prefab",
                "sourceOriginalDrawEvents": [{"kind": "renderer", "node": "icon", "sourceComponentId": "sprite"}],
                "sourceDrawEvents": [{"kind": "renderer", "node": "icon", "sourceComponentId": "sprite"}],
                "sourceSortOrderFields": [{"sourceId": "order", "nativeId": "native-order", "node": "icon",
                                            "sortOrder": 4, "enabled": False}],
                "sourceSortRoots": [{"sourceId": "sortroot", "nativeId": "native-root", "node": "root", "enabled": True}],
                "renderers": [{"sourceComponentId": "sprite", "node": "icon"}],
                "masks": [{"sourceId": "mask-27", "nativeId": "native-mask-27", "node": "node-27",
                           "maskType": 0, "enabled": True, "inverted": False, "alphaThreshold": 0.1,
                           "spriteFrameUuid": None},
                          {"sourceId": "mask-31", "nativeId": "native-mask-31", "node": "node-31",
                           "maskType": 1, "enabled": True, "inverted": True, "alphaThreshold": 0.35,
                           "spriteFrameUuid": None},
                          {"sourceId": "mask-8", "nativeId": "native-mask-8", "node": "node-8",
                           "maskType": 0, "enabled": True, "inverted": False, "alphaThreshold": 0.05,
                           "spriteFrameUuid": None}],
                "nonDrawRenderers": [], "sourceNonDrawRenderers": []}
        plan = {"staticSortQueue": [spec], "sourcePrefabs": [{"sourceId": "prefab-c", "path": spec["prefabPath"]}]}
        order = {"sourceId": "order", "expectedSourceId": "order", "nativeId": "native-order",
                 "expectedNativeId": "native-order", "node": "icon", "sourceSortOrder": 4,
                 "effectiveSourceSortOrder": 0, "enabledInSource": False, "renderedOnNode": False,
                 "componentUuid": "component-uuid-order", "nativeClass": "MonkeyStaticSortOrderField", "verified": True}
        sortroot = {"sourceId": "sortroot", "expectedSourceId": "sortroot", "nativeId": "native-root",
                    "expectedNativeId": "native-root", "node": "root", "enabledInSource": True,
                    "componentUuid": "component-uuid-root", "nativeClass": "CreatorStaticSortRootField", "verified": True}
        graphic = {"sourceComponentId": "sprite", "sourceNode": "icon", "sourceFingerprint": "fingerprint",
                   "proxyFingerprint": "fingerprint", "originalLayer": 8, "proxyLayer": 8,
                   "opacityVerified": True, "verified": True}
        persistent = {"rootScope": "root", "presentationMode": "persistent", "verified": True,
                      "sourceTreePreserved": True, "sourceFieldsPreserved": True, "sourceSortRootsPreserved": True,
                      "sourceLayersPreserved": True, "drawSequenceVerified": True,
                      "sourceQueueProjectionVerified": True,
                      "sourceOriginalDrawEvents": copy.deepcopy(spec["sourceOriginalDrawEvents"]),
                      "sourceNonDrawSourceMappings": [], "sourceNonDrawRenderers": [],
                      "sourceSortOrderFields": [order], "sourceSortRoots": [sortroot], "graphics": [graphic],
                      "masks": [creator_mask_row("mask-8", "native-mask-8", "node-8", mask_type=0, threshold=0.05),
                                creator_mask_row("mask-27", "native-mask-27", "node-27", mask_type=0, threshold=0.1),
                                creator_mask_row("mask-31", "native-mask-31", "node-31", mask_type=1,
                                                 inverted=True, threshold=0.35)]}
        initialized = copy.deepcopy(persistent)
        initialized.update({"presentationMode": "initialized", "sourceSuppressed": True,
                            "nestedProxyRootsDisabled": True})
        result = {"sourcePrefabs": [{"sourceId": "prefab-c", "path": spec["prefabPath"],
                                     "staticSortQueue": {"persistent": persistent, "initialized": initialized}}]}
        self.assertEqual([], verify_creator(plan, result))
        result["sourcePrefabs"][0]["staticSortQueue"]["initialized"]["masks"].reverse()
        self.assertEqual([], verify_creator(plan, result))
        persistent_masks = result["sourcePrefabs"][0]["staticSortQueue"]["persistent"]["masks"]
        persistent_masks[0] = copy.deepcopy(persistent_masks[1])
        self.assertTrue(any("mask source ID mapping" in row["message"] or "mask readback IDs" in row["message"]
                            for row in verify_creator(plan, result)))
        result["sourcePrefabs"][0]["staticSortQueue"]["persistent"]["masks"] = [
            creator_mask_row("mask-27", "native-mask-27", "node-27", mask_type=0, threshold=0.1),
            creator_mask_row("mask-31", "native-mask-31", "node-31", mask_type=1, inverted=True, threshold=0.35),
            creator_mask_row("mask-8", "native-mask-8", "node-8", mask_type=0, threshold=0.05)]
        result["sourcePrefabs"][0]["staticSortQueue"]["initialized"]["masks"].pop()
        self.assertTrue(any("mask evidence count differs" in row["message"] for row in verify_creator(plan, result)))
        result["sourcePrefabs"][0]["staticSortQueue"]["initialized"]["masks"] = copy.deepcopy(
            result["sourcePrefabs"][0]["staticSortQueue"]["persistent"]["masks"])
        result["sourcePrefabs"][0]["staticSortQueue"]["persistent"]["masks"][0]["checks"]["alphaThreshold"] = False
        self.assertTrue(any("mask typed evidence differs" in row["message"] for row in verify_creator(plan, result)))
        result["sourcePrefabs"][0]["staticSortQueue"]["persistent"]["masks"][0]["checks"]["alphaThreshold"] = True
        result["sourcePrefabs"][0]["staticSortQueue"]["persistent"]["sourceSortOrderFields"][0]["componentUuid"] = ""
        self.assertTrue(any("SortOrder typed field differs" in row["message"] for row in verify_creator(plan, result)))

    def test_creator_projection_validates_original_empty_graphics_event_and_mapping(self):
        import hashlib
        raw = {"__type__": "cc.Graphics", "_materials": [{"__uuid__": "source-material"}]}
        fields_json = '{"__type__":"cc.Graphics","_materials":[{"__uuid__":"source-material"}]}'
        fields_sha = hashlib.sha256(fields_json.encode("utf-8")).hexdigest()
        event = {"kind": "renderer", "node": "graphics-node", "sourceComponentId": "graphics-source"}
        spec = {"rootScope": "root", "sourcePrefabId": "prefab-g", "prefabPath": "db://assets/G.prefab",
                "sourceOriginalDrawEvents": [event], "sourceDrawEvents": [], "renderers": [],
                "sourceSortOrderFields": [], "sourceSortRoots": [], "masks": [],
                "sourceNodeActive": {"graphics-node": True},
                "nonDrawRenderers": [{"sourceId": "graphics-source", "nativeId": "native-graphics", "node": "graphics-node",
                    "sourceType": "cc.Graphics", "expectedNativeType": "Graphics", "sourceEnabled": True,
                    "sourceActive": True, "sourceFields": raw, "sourceFieldsJson": fields_json,
                    "sourceFieldsSha256": fields_sha, "sourceSpriteFrameUuid": None, "sourceText": None,
                    "sourceNeedsSpriteBinding": False,
                    "nativeTextExpectation": None, "sourceTextEmpty": False, "sourceFontId": None,
                    "creatorMarkup": None, "nativeFontAssetId": None, "nativeFallbackAssetIds": [],
                    "targetSystemFontFamily": None, "noDrawReason": "empty-command-stream",
                    "nativeEnabledExpected": False, "initialCommandStreamEmpty": True,
                    "sourceDrawingCommands": "not-serialized-empty-in-fixed-state", "sourceMaterialIds": ["source-material"]}],
                "sourceNonDrawRenderers": [{"sourceComponentId": "graphics-source", "node": "graphics-node",
                    "disposition": "source-render-event", "sourceEventIndex": 0,
                    "noDrawReason": "empty-command-stream"}]}
        native = {"sourceId": "graphics-source", "nativeId": "native-graphics", "node": "graphics-node",
            "sourceType": "cc.Graphics", "expectedNativeType": "Graphics", "actualNativeType": "Graphics",
            "componentUuid": "component-uuid-graphics", "sourceEnabled": True, "sourceActive": True,
            "componentEnabled": False, "nativeEnabledExpected": False, "nodeActive": True, "effectiveActive": True,
            "sourceFieldsJson": fields_json, "sourceFieldsSha256": fields_sha,
            "sourceSpriteFrameUuid": None, "nativeSpriteFrameUuid": None, "sourceText": None,
            "sourceNeedsSpriteBinding": False,
            "actualText": None, "sourceFontId": None, "nativeFontAssetId": None, "nativeFallbackAssetIds": [],
            "targetSystemFontFamily": None, "creatorMarkup": None, "noDrawReason": "empty-command-stream",
            "sourceTextEmpty": False, "nativeTextExpectation": None, "initialCommandStreamEmpty": True,
            "sourceDrawingCommands": "not-serialized-empty-in-fixed-state", "sourceMaterialIds": ["source-material"],
            "graphicsPathCount": 0, "nativeMaterialUuid": "f0416e68-0200-4b77-a926-4f9d16e494da",
            "nativeEffectUuid": "1c02ae6f-4492-4915-b8f8-7492a3b1e4cd", "nativeMaterialVerified": True,
            "verified": True}
        persistent = {"rootScope": "root", "presentationMode": "persistent", "verified": True,
                      "sourceTreePreserved": True, "sourceFieldsPreserved": True, "sourceSortRootsPreserved": True,
                      "sourceLayersPreserved": True, "drawSequenceVerified": True,
                      "sourceQueueProjectionVerified": True, "sourceOriginalDrawEvents": [copy.deepcopy(event)],
                      "sourceNonDrawSourceMappings": [{**copy.deepcopy(spec["sourceNonDrawRenderers"][0]), "verified": True}],
                      "sourceNonDrawRenderers": [copy.deepcopy(native)], "sourceSortOrderFields": [],
                      "sourceSortRoots": [], "graphics": [], "masks": []}
        initialized = copy.deepcopy(persistent)
        initialized.update({"presentationMode": "initialized", "sourceSuppressed": True,
                            "nestedProxyRootsDisabled": True})
        plan = {"staticSortQueue": [spec], "sourcePrefabs": [{"sourceId": "prefab-g", "path": spec["prefabPath"]}]}
        result = {"sourcePrefabs": [{"sourceId": "prefab-g", "path": spec["prefabPath"],
                                     "staticSortQueue": {"persistent": persistent, "initialized": initialized}}]}
        self.assertEqual([], verify_creator(plan, result))
        persistent["sourceNonDrawSourceMappings"][0]["sourceEventIndex"] = 4
        self.assertTrue(any("index/node/reason differs" in row["message"] for row in verify_creator(plan, result)))
        persistent["sourceNonDrawSourceMappings"][0]["sourceEventIndex"] = 0
        persistent["sourceNonDrawSourceMappings"].append(copy.deepcopy(persistent["sourceNonDrawSourceMappings"][0]))
        self.assertTrue(any("mapping count differs" in row["message"] or "duplicates source ID" in row["message"]
                            for row in verify_creator(plan, result)))
        persistent["sourceNonDrawSourceMappings"] = [copy.deepcopy(spec["sourceNonDrawRenderers"][0] | {"verified": True})]
        persistent["sourceNonDrawRenderers"] = []
        self.assertTrue(any("native non-draw renderer source IDs differ" in row["message"]
                            for row in verify_creator(plan, result)))

    def test_spine_empty_owner_delegation_requires_typed_child_renderers(self):
        from src.monkey.prefab_static_sort_readback import _check_spine_owner_delegations
        source_id = "source-spine"
        spec = {"renderers": [{"sourceComponentId": source_id, "node": "spine-node", "sourceType": "sp.Skeleton"}]}
        graphics = [
            {"sourceComponentId": source_id, "sourceNode": "spine-node", "nativeGraphicType": "UnityEngine.UI.RawImage",
             "generatedSourceChild": True, "vertexCount": 18, "submeshIndex": 0},
            {"sourceComponentId": source_id, "sourceNode": "spine-node", "nativeGraphicType": "UnityEngine.UI.RawImage",
             "generatedSourceChild": True, "vertexCount": 6, "submeshIndex": 0},
        ]
        proof = {"sourceComponentId": source_id, "sourceNode": "spine-node",
            "sourceGraphicType": "Spine.Unity.SkeletonGraphic", "sourceIdentityComponentId": source_id,
            "sourceDataAssetId": "spineAsset:test-source",
            "sourceDataAssetPath": "Assets/Game/Content/Spine/Test/Test_SkeletonData.asset",
            "sourceBindingPlanPath": "Assets/Game/Editor/Conversion/spine-native-binding-plan.json",
            "sourceBindingPlanSha256": "f" * 64, "sourceManifestSha256": "1" * 64,
            "sourceDataAssetGuid": "a" * 32, "rootMeshVertexCount": 0, "rootMeshSubmeshCount": -1,
            "rootCanvasMaterialCount": 0, "rootMeshWasMissing": True, "rootMeshDelegated": True,
            "sourceIdentityVerified": True, "sourceDataReferenceVerified": True,
            "childRendererListVerified": True, "childReferencesPersistent": True, "verified": True,
            "delegatedChildPaths": ["root/spine/segment-0", "root/spine/segment-1"],
            "delegatedChildGraphicTypes": ["UnityEngine.UI.RawImage"] * 2,
            "childMeshVertexCounts": [18, 6], "childMeshSubmeshCounts": [1, 1],
            "childCanvasMaterialCounts": [1, 1], "delegatedChildTextureGuids": ["b" * 32, "c" * 32],
            "delegatedChildMaterialGuids": ["d" * 32, "e" * 32]}
        row = {"graphics": graphics, "spineOwnerDelegations": [copy.deepcopy(proof)]}
        spine_plan = {"spineNativeStage": {"sourceManifestSha256": proof["sourceManifestSha256"],
            "nativeBindingPlanPath": proof["sourceBindingPlanPath"],
            "nativeBindingPlanSha256": proof["sourceBindingPlanSha256"],
            "components": [{"sourceComponentId": source_id, "sourceHasStaticDataReference": True,
                            "sourceDataAssetId": proof["sourceDataAssetId"]}],
            "dataAssets": [{"sourceAssetId": proof["sourceDataAssetId"],
                            "skeletonDataAssetPath": proof["sourceDataAssetPath"]}]}}
        self.assertEqual([], _check_spine_owner_delegations(spec, row, "persistent", spine_plan))
        wrong_binding = copy.deepcopy(row)
        wrong_binding["spineOwnerDelegations"][0]["sourceDataAssetId"] = "spineAsset:other"
        self.assertTrue(any("owner/registered-renderer typed proof" in message
                            for message in _check_spine_owner_delegations(spec, wrong_binding, "persistent", spine_plan)))
        row["spineOwnerDelegations"][0]["sourceDataReferenceVerified"] = False
        self.assertTrue(any("owner/registered-renderer typed proof" in message
                            for message in _check_spine_owner_delegations(spec, row, "persistent", spine_plan)))
        row["spineOwnerDelegations"] = [copy.deepcopy(proof), copy.deepcopy(proof)]
        self.assertTrue(any("source ID repeats" in message
                            for message in _check_spine_owner_delegations(spec, row, "persistent", spine_plan)))
        row["spineOwnerDelegations"] = [copy.deepcopy(proof)]
        row["graphics"] = graphics[:1]
        self.assertTrue(any("do not cover delegated native renderers" in message
                            for message in _check_spine_owner_delegations(spec, row, "loaded", spine_plan)))
        row["graphics"] = graphics
        row["spineOwnerDelegations"] = []
        self.assertTrue(any("lacks owner delegation proof" in message
                            for message in _check_spine_owner_delegations(spec, row, "persistent", spine_plan)))

        # Production plans carry only binding-plan pins, so the independent
        # candidate bytes must crosslink the exact source component and asset.
        external = {"components": {source_id: {"sourceComponentId": source_id,
                    "sourcePrefabId": "prefab-spine", "sourceNodeId": "source-node-id",
                    "sourceHasStaticDataReference": True, "sourceDataAssetId": proof["sourceDataAssetId"]}},
                    "dataAssets": {proof["sourceDataAssetId"]: {"sourceAssetId": proof["sourceDataAssetId"],
                    "skeletonDataAssetPath": proof["sourceDataAssetPath"]}}}
        spec["sourcePrefabId"] = "prefab-spine"
        row["spineOwnerDelegations"] = [copy.deepcopy(proof)]
        self.assertEqual([], _check_spine_owner_delegations(spec, row, "persistent", spine_plan, external))
        wrong_path = copy.deepcopy(external)
        wrong_path["dataAssets"][proof["sourceDataAssetId"]]["skeletonDataAssetPath"] = "Assets/other.asset"
        self.assertTrue(any("owner/registered-renderer typed proof" in message for message in
                            _check_spine_owner_delegations(spec, row, "persistent", spine_plan, wrong_path)))

    def test_spine_native_binding_bytes_are_sha_pinned_and_crosslinked(self):
        import hashlib
        from src.monkey.prefab_static_sort_readback import _load_spine_binding_contract, _spine_source_binding_fields_match
        source_manifest = "1" * 64
        source_binding_hash = "2" * 64
        components = [{"sourceComponentId": "component-a", "sourcePrefabId": "prefab-a",
            "sourceNodeId": "node-a", "sourceHasStaticDataReference": True,
            "sourceDataAssetId": "source-asset-a", "staticDataState": "exact_data_asset_required",
            "targetFieldBindings": []},
            {"sourceComponentId": "component-null", "sourcePrefabId": "prefab-a",
            "sourceNodeId": "node-null", "sourceHasStaticDataReference": False,
            "sourceDataAssetId": None, "staticDataState": "source_uuid_absent_component_preserved_unbound",
            "targetFieldBindings": []}]
        data_assets = [{"sourceAssetId": "source-asset-a", "skeletonDataAssetPath": "Assets/Game/Content/Spine/A.asset"}]
        payload = {"contract": "monkey-spine-native-binding/1", "sourceManifestSha256": source_manifest,
            "sourceNativeBindingPlanSha256": source_binding_hash, "componentCount": len(components),
            "dataAssetCount": len(data_assets), "components": components, "dataAssets": data_assets}
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        stage = {"nativeBindingPlanPath": "Assets/Game/Editor/Conversion/spine-native-binding-plan.json",
            "nativeBindingPlanSha256": hashlib.sha256(raw).hexdigest(),
            "sourceNativeBindingPlanSha256": source_binding_hash, "sourceManifestSha256": source_manifest,
            "componentCount": len(components)}
        plan = {"sourceManifestSha256": source_manifest, "spineNativeStage": stage,
                "components": [{"sourceId": component["sourceComponentId"], "node": component["sourceNodeId"],
                                "type": "sp.Skeleton"} for component in components]}
        binding, errors = _load_spine_binding_contract(plan, raw)
        self.assertEqual([], errors)
        self.assertEqual("Assets/Game/Content/Spine/A.asset",
                         binding["dataAssets"]["source-asset-a"]["skeletonDataAssetPath"])
        fields_component = {"targetFieldBindings": [
            {"member": "startingAnimation", "stringValue": "idle"},
            {"member": "startingLoop", "boolValue": True},
            {"member": "pmaVertexColors", "boolValue": False},
            {"member": "initialSkinName", "stringValue": "default"},
            {"member": "timeScale", "numberValue": 1.0}]}
        self.assertTrue(_spine_source_binding_fields_match({"startingAnimation": "idle", "startingLoop": "True",
            "pmaVertexColors": "False", "initialSkinName": "default", "timeScale": "1"}, fields_component))
        self.assertFalse(_spine_source_binding_fields_match({"startingAnimation": "other", "startingLoop": "True",
            "pmaVertexColors": "False", "initialSkinName": "default", "timeScale": "1"}, fields_component))
        self.assertTrue(_load_spine_binding_contract(plan, raw + b" ")[1])
        bad_pin = copy.deepcopy(plan)
        bad_pin["spineNativeStage"]["sourceNativeBindingPlanSha256"] = "3" * 64
        self.assertTrue(_load_spine_binding_contract(bad_pin, raw)[1])
        duplicate = copy.deepcopy(payload)
        duplicate["components"].append(copy.deepcopy(duplicate["components"][0]))
        duplicate["componentCount"] += 1
        duplicate_raw = json.dumps(duplicate, separators=(",", ":")).encode("utf-8")
        duplicate_plan = copy.deepcopy(plan)
        duplicate_plan["spineNativeStage"]["nativeBindingPlanSha256"] = hashlib.sha256(duplicate_raw).hexdigest()
        duplicate_plan["spineNativeStage"]["componentCount"] += 1
        duplicate_plan["components"].append(copy.deepcopy(duplicate_plan["components"][0]))
        self.assertTrue(any("repeats component" in error for error in
                            _load_spine_binding_contract(duplicate_plan, duplicate_raw)[1]))
        missing_map = copy.deepcopy(payload)
        missing_map["components"][0]["sourceDataAssetId"] = "unknown-asset"
        missing_raw = json.dumps(missing_map, separators=(",", ":")).encode("utf-8")
        missing_plan = copy.deepcopy(plan)
        missing_plan["spineNativeStage"]["nativeBindingPlanSha256"] = hashlib.sha256(missing_raw).hexdigest()
        self.assertTrue(any("data mapping is absent" in error for error in
                            _load_spine_binding_contract(missing_plan, missing_raw)[1]))
        bad_source_row = copy.deepcopy(plan)
        bad_source_row["components"][0]["node"] = "different-node"
        self.assertTrue(any("does not map to the import-plan source row" in error for error in
                            _load_spine_binding_contract(bad_source_row, raw)[1]))

        spec = {"sourcePrefabId": "prefab-a", "rootScope": "root-a", "renderers": [
            {"sourceComponentId": "component-a", "node": "node-a", "sourceType": "sp.Skeleton"}]}
        plan_with_queue = copy.deepcopy(plan)
        plan_with_queue["sourcePrefabs"] = [{"sourceId": "prefab-a", "path": "Assets/P.prefab"}]
        plan_with_queue["staticSortQueue"] = [spec]
        queue_rows = [{"rootScope": "root-a"}]
        result = {"sourcePrefabs": [{"sourceId": "prefab-a", "path": "Assets/P.prefab",
            "staticSortFields": {"sourcePrefabId": "prefab-a", "prefabPath": "Assets/P.prefab",
                "persistentAsset": copy.deepcopy(queue_rows), "loadedInstance": copy.deepcopy(queue_rows)}}]}
        missing_plan_diagnostics = verify(plan_with_queue, result)
        self.assertTrue(any("frozen Spine native binding-plan bytes/hash are absent" in row["message"]
                            for row in missing_plan_diagnostics))

    def test_spine_nondraw_owner_requires_exact_inactive_registered_children(self):
        from src.monkey.prefab_static_sort_readback import _check_spine_non_draw_children
        source_id = "source-spine-inactive"
        spec = {"nonDrawRenderers": [{"sourceComponentId": source_id, "node": "spine-node",
                                      "sourceType": "sp.Skeleton", "sourceEnabled": True,
                                      "sourceActive": False}]}
        child = {"sourceComponentId": source_id, "sourceNode": "spine-node", "noDrawReason": "inactive-source",
            "sourceIdentityComponentId": source_id, "sourceDataAssetId": "spineAsset:fixture",
            "sourceDataAssetPath": "Assets/Game/Content/Spine/Fixture.asset", "sourceDataAssetGuid": "a" * 32,
            "childPath": "3/0", "childGraphicType": "UnityEngine.UI.RawImage",
            "childMaterialGuid": "b" * 32, "childTextureGuid": "c" * 32,
            "sourceOwnerEnabled": True, "sourceNodeActive": False,
            "sourceChildEnabled": True, "sourceChildActiveSelf": True, "sourceChildActiveInHierarchy": False,
            "targetChildEnabled": True, "targetChildActiveInHierarchy": False,
            "sourceIdentityVerified": True, "sourceDataReferenceVerified": True,
            "registeredChildVerified": True, "childReferencePersistent": True,
            "childNoDrawVerified": True, "sourceChildMeshVertexCount": 12,
            "sourceChildMeshSubmeshCount": 1, "sourceChildMaterialCount": 1, "verified": True}
        row = {"spineNonDrawChildren": [copy.deepcopy(child)]}
        self.assertEqual([], _check_spine_non_draw_children(spec, row, "persistent"))
        row["spineNonDrawChildren"][0]["sourceChildActiveInHierarchy"] = True
        row["spineNonDrawChildren"][0]["targetChildActiveInHierarchy"] = True
        self.assertTrue(any("can still draw" in message
                            for message in _check_spine_non_draw_children(spec, row, "loaded")))
        row["spineNonDrawChildren"] = [copy.deepcopy(child)]
        row["spineNonDrawChildren"][0]["registeredChildVerified"] = False
        self.assertTrue(any("owner/child source identity or resource proof differs" in message
                            for message in _check_spine_non_draw_children(spec, row, "persistent")))

    def test_spine_inactive_owner_with_empty_registered_list_keeps_data_identity_and_no_draw_proof(self):
        from src.monkey.prefab_static_sort_readback import _check_spine_non_draw_children
        source_id = "gameAsset:fixture#57"
        spec = {"nonDrawRenderers": [{"sourceComponentId": source_id, "node": "spine-node",
                                      "sourceType": "sp.Skeleton", "sourceEnabled": True,
                                      "sourceActive": False}]}
        owner = {
            "sourceComponentId": source_id, "sourceNode": "spine-node",
            "noDrawReason": "inactive-owner-no-registered-renderers",
            "sourceIdentityComponentId": source_id, "sourceDataAssetId": "spineAsset:fixture",
            "sourceDataAssetPath": "Assets/Game/Content/Spine/Effect/fixture.asset",
            "sourceDataAssetGuid": "a" * 32, "childPath": None, "childGraphicType": None,
            "childMaterialGuid": None, "childTextureGuid": None,
            "sourceOwnerEnabled": True, "sourceNodeActive": False,
            "sourceIdentityVerified": True, "sourceDataReferenceVerified": True,
            "registeredChildVerified": True, "childReferencePersistent": True,
            "childNoDrawVerified": True, "ownerOnlyNoRegisteredChildren": True,
            "ownerRendererListReadable": True, "ownerRendererListEmpty": True,
            "ownerRootMeshEmpty": True, "ownerRootMeshVertexCount": -1,
            "ownerRootMeshSubmeshCount": -1, "ownerRootMeshIndexCount": 0,
            "ownerRootCanvasMaterialCount": 0, "ownerRootMeshSha256": None,
            "currentOwnerRendererListReadable": True, "currentOwnerRendererListEmpty": True,
            "currentOwnerRootMeshEmpty": True, "currentOwnerRootMeshVertexCount": 0,
            "currentOwnerRootMeshSubmeshCount": 0, "currentOwnerRootMeshIndexCount": 0,
            "currentOwnerRootCanvasMaterialCount": 0, "currentOwnerRootMeshSha256": "",
            "ownerRootMeshCaptureAndCurrentFingerprintAbsent": True,
            "sourceChildMeshVertexCount": -1, "sourceChildMeshSubmeshCount": -1,
            "sourceChildMaterialCount": -1, "verified": True,
        }
        row = {"spineNonDrawChildren": [copy.deepcopy(owner)]}
        self.assertEqual([], _check_spine_non_draw_children(spec, row, "persistent"))
        self.assertEqual([], _check_spine_non_draw_children(spec, row, "loaded"))
        roundtripped_empty_hash = copy.deepcopy(row)
        roundtripped_empty_hash["spineNonDrawChildren"][0]["ownerRootMeshSha256"] = ""
        self.assertEqual([], _check_spine_non_draw_children(spec, roundtripped_empty_hash, "persistent"))
        for key, value in (("sourceDataAssetGuid", ""), ("ownerRendererListEmpty", False),
                           ("ownerRootCanvasMaterialCount", 1), ("ownerRootMeshVertexCount", 4),
                           ("sourceActive", True), ("childGraphicType", "UnityEngine.UI.RawImage"),
                           ("ownerRootMeshSha256", "a" * 64),
                           ("currentOwnerRootMeshVertexCount", 4),
                           ("currentOwnerRootMeshSubmeshCount", 1),
                           ("currentOwnerRootCanvasMaterialCount", 1),
                           ("sourceDataAssetPath", "")):
            bad = copy.deepcopy(row)
            field = "sourceNodeActive" if key == "sourceActive" else key
            bad["spineNonDrawChildren"][0][field] = value
            self.assertTrue(_check_spine_non_draw_children(spec, bad, "persistent"), key)

    def test_spine_source_null_data_owner_requires_pinned_fields_and_no_render_children(self):
        from src.monkey.prefab_static_sort_readback import (
            _check_spine_null_data_owners, _check_spine_non_draw_children)
        source_id = "source-spine-null"
        spec = {"nonDrawRenderers": [{"sourceComponentId": source_id, "node": "spine-node",
                                      "sourceType": "sp.Skeleton", "sourceEnabled": True,
                                      "sourceActive": False}]}
        plan = {"sourceManifestSha256": "f" * 64,
                "spineNativeStage": {"sourceManifestSha256": "f" * 64,
                                     "sourceNativeBindingPlanSha256": "a" * 64},
                "components": [{"sourceId": source_id, "node": "spine-node", "type": "sp.Skeleton",
                                "enabled": True}]}
        proof = {"sourceComponentId": source_id, "sourceNode": "spine-node",
            "sourceStaticDataState": "source_uuid_absent_component_preserved_unbound",
            "sourceBindingPlanPath": "Assets/Game/Editor/Conversion/spine-native-source-binding-plan.json",
            "sourceBindingPlanSha256": "a" * 64, "sourceManifestSha256": "f" * 64,
            "sourceMaterialClosureStatus": "no-serialized-skeleton-data-no-render-material-closure",
            "rootMaterialEvidence": "count=0;sourceBaseIsGraphicDefault=True;slotMatchesMaterialForRendering=False",
            "rootMeshSha256": None, "rootMeshGeometryEvidence": "empty-render-mesh",
            "sourceIdentityComponentId": source_id,
            "sourceTargetFieldsJson": '["initialSkinName=","pmaVertexColors=False","startingAnimation=","startingLoop=True","timeScale=1"]',
            "expectedFieldsJson": '["initialSkinName=","pmaVertexColors=False","startingAnimation=","startingLoop=True","timeScale=0"]',
            "actualFieldsJson": '["initialSkinName=","pmaVertexColors=False","startingAnimation=","startingLoop=True","timeScale=0"]',
            "sourceHasStaticDataReference": False, "sourceDataAssetIdNull": False, "sourcePlanVerified": True,
            "sourceIdentityVerified": True, "sourceNodeInactive": True, "nativeDataReferenceNull": True,
            "sourceNodeActive": False, "sourceOwnerEnabled": True, "sourceSerializedActive": False,
            "sourceSerializedActiveVerified": True, "sourceActivityStage": "persistent-serialized-scope",
            "nativeRootMeshEmpty": True, "nativeRootMeshDefaultGraphicQuad": False,
            "rootCanvasDefaultMaterialOnly": True, "registeredRendererListEmpty": True,
            "mappedStaticFieldsVerified": True, "sourceBehaviorBoundaryVerified": True,
            "dynamicAssignmentUnverified": True, "sourceTimeScale": 1.0, "nativeTimeScale": 0.0,
            "sourceTimeScaleVerified": True, "sourceIdentityTimeScaleVerified": True, "persistentVisiblePose": True,
            "rootMeshVertexCount": 0, "rootMeshSubmeshCount": 0, "rootMeshIndexCount": 0,
            "rootCanvasMaterialCount": 0, "rootExtraMaterialModifierCount": 0,
            "rootSourceBaseDefaultMaterial": True, "rootMaterialSlotMatchesGraphicRendering": False,
            "registeredRendererCount": 0, "verified": True}
        empty_carrier = {"sourceComponentId": source_id, "noDrawReason": "source-node-inactive",
            "sourceEnabled": True, "sourceActive": False, "sourceActivityMatchesExpected": True,
            "sourceNoDrawEvidenceVerified": False, "sourceSpineNullDataProofVerified": False,
            "sourceSpineNullDataRootFallbackQuad": False, "sourceSpineNullDataRootMeshCacheAbsent": False,
            "spineNullDataRootMeshSha256": "", "sourceGraphicSuppressedByPresenter": False,
            "nativeGraphicEnabled": True, "nativeComponentEnabled": True, "sourceMeshPresent": False,
            "sourceMeshVertexCount": 0, "sourceCanvasMaterialCount": 0}
        row = {"spineNullDataOwners": [copy.deepcopy(proof)], "spineNullDataOwnersVerified": True,
               "spineNonDrawChildren": [], "emptyRenderers": [empty_carrier], "graphics": []}
        self.assertEqual([], _check_spine_null_data_owners(spec, row, "persistent", plan))
        self.assertEqual([], _check_spine_non_draw_children(spec, row, "persistent", plan))
        null_binding = {"components": {source_id: {"sourceComponentId": source_id,
            "sourcePrefabId": "prefab-null", "sourceNodeId": "spine-node", "sourceHasStaticDataReference": False,
            "sourceDataAssetId": None, "staticDataState": "source_uuid_absent_component_preserved_unbound",
            "targetFieldBindings": [{"member": "startingAnimation", "stringValue": "", "valueType": "string"},
                {"member": "startingLoop", "boolValue": True, "valueType": "bool"},
                {"member": "pmaVertexColors", "boolValue": False, "valueType": "bool"},
                {"member": "initialSkinName", "stringValue": "", "valueType": "string"},
                {"member": "timeScale", "numberValue": 1.0, "valueType": "number"}]}}, "dataAssets": {}}
        spec["sourcePrefabId"] = "prefab-null"
        self.assertEqual([], _check_spine_null_data_owners(spec, row, "persistent", plan, null_binding))
        wrong_null_mapping = copy.deepcopy(null_binding)
        wrong_null_mapping["components"][source_id]["sourceDataAssetId"] = "fabricated-data"
        self.assertTrue(_check_spine_null_data_owners(spec, row, "persistent", plan, wrong_null_mapping))
        bad = copy.deepcopy(row)
        bad["spineNullDataOwners"][0]["sourceBindingPlanSha256"] = "b" * 64
        self.assertTrue(_check_spine_null_data_owners(spec, bad, "persistent", plan))
        bad = copy.deepcopy(row)
        bad["spineNullDataOwners"][0]["nativeDataReferenceNull"] = False
        self.assertTrue(_check_spine_null_data_owners(spec, bad, "loaded", plan))
        bad = copy.deepcopy(row)
        bad["spineNullDataOwners"][0]["sourceDataAssetIdNull"] = "false"
        self.assertTrue(_check_spine_null_data_owners(spec, bad, "persistent", plan))
        bad = copy.deepcopy(row)
        bad["spineNullDataOwners"][0]["sourceTargetFieldsJson"] = '["startingAnimation=","startingLoop=True","timeScale=0"]'
        self.assertTrue(_check_spine_null_data_owners(spec, bad, "persistent", plan))
        bad = copy.deepcopy(row)
        bad["spineNullDataOwners"][0]["nativeTimeScale"] = 1.0
        self.assertTrue(_check_spine_null_data_owners(spec, bad, "persistent", plan))
        default_spec = {"renderers": [{"sourceComponentId": source_id, "node": "spine-node",
                                       "sourceType": "sp.Skeleton", "sourceEnabled": True,
                                       "sourceActive": True}]}
        default_plan = copy.deepcopy(plan)
        default_proof_row = copy.deepcopy(proof)
        default_proof_row.update({"sourceNodeActive": True, "sourceNodeInactive": False,
            "sourceSerializedActive": True, "sourceActivityStage": "persistent-serialized-scope",
            "nativeRootMeshEmpty": False, "nativeRootMeshDefaultGraphicQuad": True,
            "rootMeshVertexCount": 4, "rootMeshSubmeshCount": 1, "rootMeshIndexCount": 6,
            "rootMeshSha256": "d" * 64,
            "rootMeshGeometryEvidence": "vertexCount=4;submeshes=1;indices=6;triangleOrderExact=True;rectCornersExact=True",
            "rootCanvasMaterialCount": 1, "rootCanvasDefaultMaterialOnly": True,
            "rootSourceBaseDefaultMaterial": True, "rootMaterialSlotMatchesGraphicRendering": True,
            "rootMaterialEvidence": "count=1;sourceBaseIsGraphicDefault=True;slotMatchesMaterialForRendering=True"})
        fallback_carrier = {"sourceComponentId": source_id,
            "noDrawReason": "source-spine-data-reference-absent-no-source-renderable-output",
            "sourceNoDrawEvidenceVerified": True, "sourceSpineNullDataProofVerified": True,
            "sourceSpineNullDataRootFallbackQuad": True, "sourceSpineNullDataRootMeshCacheAbsent": True,
            "spineNullDataRootMeshSha256": "d" * 64, "sourceGraphicSuppressedByPresenter": False,
            "nativeGraphicEnabled": True, "nativeComponentEnabled": True, "sourceMeshPresent": False,
            "sourceMeshVertexCount": 0, "sourceCanvasMaterialCount": 0}
        default_only = {"spineNullDataOwners": [default_proof_row], "spineNullDataOwnersVerified": True,
                        "spineNonDrawChildren": [], "emptyRenderers": [fallback_carrier], "graphics": []}
        self.assertEqual([], _check_spine_null_data_owners(default_spec, default_only, "persistent", default_plan))
        default_loaded = copy.deepcopy(default_only)
        default_loaded["spineNullDataOwners"][0]["sourceActivityStage"] = "loaded-hierarchy-plus-serialized-scope"
        default_loaded["emptyRenderers"][0]["sourceGraphicSuppressedByPresenter"] = True
        self.assertEqual([], _check_spine_null_data_owners(default_spec, default_loaded, "loaded", default_plan))
        bad = copy.deepcopy(default_loaded)
        bad["emptyRenderers"][0]["sourceGraphicSuppressedByPresenter"] = False
        self.assertTrue(_check_spine_null_data_owners(default_spec, bad, "loaded", default_plan))
        bad = copy.deepcopy(default_only)
        bad["graphics"] = [{"sourceComponentId": source_id}]
        self.assertTrue(_check_spine_null_data_owners(default_spec, bad, "persistent", default_plan))
        bad = copy.deepcopy(default_only)
        bad["spineNullDataOwners"][0]["rootCanvasDefaultMaterialOnly"] = False
        self.assertTrue(_check_spine_null_data_owners(default_spec, bad, "persistent", default_plan))
        bad = copy.deepcopy(default_only)
        bad["spineNullDataOwners"][0]["rootMeshIndexCount"] = 3
        self.assertTrue(_check_spine_null_data_owners(default_spec, bad, "persistent", default_plan))
        bad = copy.deepcopy(default_only)
        bad["spineNullDataOwners"][0]["rootCanvasMaterialCount"] = 2
        self.assertTrue(_check_spine_null_data_owners(default_spec, bad, "persistent", default_plan))
        bad = copy.deepcopy(default_only)
        bad["spineNullDataOwners"][0]["rootMaterialSlotMatchesGraphicRendering"] = False
        self.assertTrue(_check_spine_null_data_owners(default_spec, bad, "persistent", default_plan))
        bad = copy.deepcopy(default_only)
        bad["spineNullDataOwners"][0]["rootExtraMaterialModifierCount"] = 1
        self.assertTrue(_check_spine_null_data_owners(spec, bad, "persistent", plan))
        bad = copy.deepcopy(row)
        bad["spineNonDrawChildren"] = [{"sourceComponentId": source_id}]
        self.assertTrue(_check_spine_non_draw_children(spec, bad, "persistent", plan))
        active_spec = {"renderers": [{"sourceComponentId": source_id, "node": "spine-node",
                                      "sourceType": "sp.Skeleton", "sourceEnabled": True,
                                      "sourceActive": True}]}
        active_plan = copy.deepcopy(plan)
        active_plan["components"][0]["node"] = "spine-node"
        active_proof = copy.deepcopy(proof)
        active_proof.update({"sourceNodeActive": True, "sourceNodeInactive": False,
                             "sourceSerializedActive": True,
                             "sourceActivityStage": "loaded-hierarchy-plus-serialized-scope"})
        active_carrier = {"sourceComponentId": source_id,
            "noDrawReason": "source-spine-data-reference-absent-no-source-renderable-output",
            "sourceNoDrawEvidenceVerified": True, "sourceSpineNullDataProofVerified": True,
            "sourceSpineNullDataRootFallbackQuad": False, "sourceSpineNullDataRootMeshCacheAbsent": False,
            "spineNullDataRootMeshSha256": "", "sourceGraphicSuppressedByPresenter": True,
            "nativeGraphicEnabled": True, "nativeComponentEnabled": True, "sourceMeshPresent": False,
            "sourceMeshVertexCount": 0, "sourceCanvasMaterialCount": 0}
        active_row = {"spineNullDataOwners": [active_proof], "spineNullDataOwnersVerified": True,
                      "emptyRenderers": [active_carrier], "graphics": []}
        self.assertEqual([], _check_spine_null_data_owners(active_spec, active_row, "loaded", active_plan))
        active_proof["nativeDataReferenceNull"] = False
        self.assertTrue(_check_spine_null_data_owners(active_spec, active_row, "loaded", active_plan))

    def test_spine_nonnull_data_empty_fixed_pose_keeps_typed_draw_event(self):
        from src.monkey.prefab_static_sort_readback import _check_spine_empty_pose_owners
        source_id = "source-spine-empty-fixed-pose"
        source_manifest = "f" * 64
        binding_hash = "a" * 64
        spec = {"renderers": [{"sourceComponentId": source_id, "node": "spine-node",
                               "sourceType": "sp.Skeleton", "sourceEnabled": True, "sourceActive": True}]}
        plan = {"sourceManifestSha256": source_manifest,
                "components": [{"sourceId": source_id, "node": "spine-node", "type": "sp.Skeleton"}],
                "spineNativeStage": {"sourceManifestSha256": source_manifest,
                                     "sourceNativeBindingPlanSha256": "c" * 64,
                                     "nativeBindingPlanSha256": binding_hash}}
        source_fields = '["initialSkinName=default","pmaVertexColors=False","startingAnimation=appear","startingLoop=False","timeScale=1"]'
        expected_fields = '["initialSkinName=default","pmaVertexColors=False","startingAnimation=appear","startingLoop=False","timeScale=0"]'
        proof = {"sourceComponentId": source_id, "sourceNode": "spine-node",
            "sourceDataAssetId": "spineAsset:exact-source-data", "sourceDataAssetPath":
                "Assets/Game/Content/Spine/UI/Test/source_SkeletonData.asset", "sourceDataAssetGuid": "b" * 32,
            "sourceBindingPlanPath": "Assets/Game/Editor/Conversion/spine-native-binding-plan.json",
            "sourceBindingPlanSha256": binding_hash, "sourceManifestSha256": source_manifest,
            "sourceSkin": "default", "actualSkin": "default", "runtimeDefaultSkinName": "default",
            "sourceSkinRuntimeVerified": True, "defaultSkinRuntimeNull": False,
            "sourceAnimation": "appear", "actualAnimation": "appear",
            "sourceTargetFieldsJson": source_fields, "expectedFieldsJson": expected_fields, "actualFieldsJson": expected_fields,
            "sourceHasStaticDataReference": True, "sourcePlanVerified": True, "sourceIdentityVerified": True,
            "sourceDataReferenceVerified": True, "sourceTimeScaleVerified": True, "sourceIdentityTimeScaleVerified": True,
            "persistentVisiblePose": True, "sourceBusinessBehaviorDisabled": True, "sourceCallbacksExecuted": False,
            "mappedStaticFieldsVerified": True, "sdkPoseInitialized": True, "sdkDataIdentityVerified": True,
            "fixedPoseVerified": True, "noDrawableAttachmentPoseVerified": True, "rootMeshEmpty": True,
            "registeredRendererListEmpty": True, "helperReadbackVerified": True, "verified": True,
            "presenterProofCardinalityVerified": True, "presenterOwnerReferenceVerified": True,
            "presenterDataAssetReferenceVerified": True, "presenterSourceIdentityVerified": True,
            "presenterSkinEvidenceVerified": True, "presenterFieldEvidenceVerified": True,
            "storedCaptureProofVerified": True, "storedSkinRepresentationVerified": True,
            "loadedPoseVerified": True,
            "fixedPoseSlotCount": 41, "fixedPoseAttachmentCount": 18, "fixedPoseDrawableAttachmentCount": 0,
            "presentationInstructionCount": 0, "presentationCanvasRendererCount": 0,
            "rootMeshVertexCount": 0, "rootMeshSubmeshCount": 0, "rootCanvasMaterialCount": 1,
            "registeredRendererCount": 0, "sourceTimeScale": 1.0, "nativeTimeScale": 0.0, "actualTrackTime": 0.0}
        marker = {"sourceComponentId": source_id, "sourceNode": "spine-node", "sourceEnabled": True,
                  "sourceActive": True, "actualQueueIndex": 15, "spineEmptyPoseProof": {"sourceComponentId": source_id}}
        row = {"emptyRenderers": [{**marker, "noDrawReason": "source-spine-fixed-pose-no-renderable-attachments"}],
               "spineEmptyPoseOwners": [copy.deepcopy(proof)], "spineEmptyPoseOwnersVerified": True}
        self.assertEqual([], _check_spine_empty_pose_owners(spec, row, "persistent", plan))
        spec["sourcePrefabId"] = "prefab-spine"
        pose_component = {"sourceComponentId": source_id, "sourcePrefabId": "prefab-spine",
            "sourceNodeId": "spine-node", "sourceHasStaticDataReference": True,
            "sourceDataAssetId": proof["sourceDataAssetId"], "staticDataState": "exact_data_asset_required",
            "targetFieldBindings": [{"member": "startingAnimation", "stringValue": "appear", "valueType": "string"},
                {"member": "startingLoop", "boolValue": False, "valueType": "bool"},
                {"member": "pmaVertexColors", "boolValue": False, "valueType": "bool"},
                {"member": "initialSkinName", "stringValue": "default", "valueType": "string"},
                {"member": "timeScale", "numberValue": 1.0, "valueType": "number"}]}
        pose_bindings = {"components": {source_id: pose_component}, "dataAssets": {
            proof["sourceDataAssetId"]: {"sourceAssetId": proof["sourceDataAssetId"],
                "skeletonDataAssetPath": proof["sourceDataAssetPath"]}}}
        self.assertEqual([], _check_spine_empty_pose_owners(spec, row, "persistent", plan, pose_bindings))
        wrong_pose_bindings = copy.deepcopy(pose_bindings)
        wrong_pose_bindings["components"][source_id]["targetFieldBindings"][0]["stringValue"] = "different"
        self.assertTrue(_check_spine_empty_pose_owners(spec, row, "persistent", plan, wrong_pose_bindings))
        bad = copy.deepcopy(row)
        bad["spineEmptyPoseOwners"][0]["sourceDataAssetId"] = None
        self.assertTrue(_check_spine_empty_pose_owners(spec, bad, "persistent", plan))
        wrong_binding_hash = copy.deepcopy(row)
        wrong_binding_hash["spineEmptyPoseOwners"][0]["sourceBindingPlanSha256"] = "c" * 64
        self.assertTrue(_check_spine_empty_pose_owners(spec, wrong_binding_hash, "persistent", plan))
        bad = copy.deepcopy(row)
        bad["spineEmptyPoseOwners"][0]["fixedPoseDrawableAttachmentCount"] = 1
        self.assertTrue(_check_spine_empty_pose_owners(spec, bad, "loaded", plan))
        bad = copy.deepcopy(row)
        bad["emptyRenderers"][0]["actualQueueIndex"] = -1
        self.assertTrue(_check_spine_empty_pose_owners(spec, bad, "persistent", plan))
        alias = copy.deepcopy(row)
        alias_proof = alias["spineEmptyPoseOwners"][0]
        alias_proof["actualSkin"] = ""
        alias_proof["defaultSkinRuntimeNull"] = True
        alias["emptyRenderers"][0]["spineEmptyPoseProof"]["actualSkin"] = ""
        alias["emptyRenderers"][0]["spineEmptyPoseProof"]["defaultSkinRuntimeNull"] = True
        self.assertEqual([], _check_spine_empty_pose_owners(spec, alias, "persistent", plan))
        alias["spineEmptyPoseOwners"][0]["runtimeDefaultSkinName"] = "other"
        self.assertTrue(_check_spine_empty_pose_owners(spec, alias, "persistent", plan))

    def test_non_spine_markers_accept_only_null_or_all_default_empty_pose_placeholder(self):
        from src.monkey.prefab_static_sort_readback import _empty_spine_pose_placeholder
        strings = ("sourceComponentId", "sourceNode", "sourceDataAssetId", "sourceDataAssetPath",
            "sourceDataAssetGuid", "sourceBindingPlanPath", "sourceBindingPlanSha256", "sourceManifestSha256",
            "sourceSkin", "sourceAnimation", "actualSkin", "runtimeDefaultSkinName", "actualAnimation",
            "sourceTargetFieldsJson", "expectedFieldsJson", "actualFieldsJson")
        booleans = ("sourceHasStaticDataReference", "sourcePlanVerified", "sourceIdentityVerified",
            "sourceDataReferenceVerified", "sourceTimeScaleVerified", "sourceIdentityTimeScaleVerified",
            "persistentVisiblePose", "sourceBusinessBehaviorDisabled", "sourceCallbacksExecuted",
            "mappedStaticFieldsVerified", "sdkPoseInitialized", "sdkDataIdentityVerified",
            "sourceSkinRuntimeVerified", "defaultSkinRuntimeNull", "fixedPoseVerified",
            "noDrawableAttachmentPoseVerified", "rootMeshEmpty", "registeredRendererListEmpty",
            "helperReadbackVerified", "verified", "presenterFound", "presenterProofCardinalityVerified",
            "presenterOwnerReferenceVerified", "presenterDataAssetReferenceVerified", "presenterSourceIdentityVerified",
            "presenterSkinEvidenceVerified", "presenterFieldEvidenceVerified", "storedCaptureProofVerified",
            "storedSkinRepresentationVerified", "loadedPoseVerified", "currentOwnerPresent", "currentOwnerTypeMatches",
            "currentOwnerEnabledMatches", "currentOwnerReferenceMatchesStored", "currentOwnerNodeMappingMatches",
            "currentSourceIdentityMatches", "currentSourceSerializedActivityVerified",
            "currentSourceSerializedActivityMatchesExpected", "currentSourceHierarchyActivityMatchesExpected",
            "currentDataAssetPresent", "currentDataAssetReferenceMatchesStored", "currentDataAssetIdentityVerified",
            "currentDataAssetIdMatchesStored", "currentDataAssetPathMatchesStored", "currentDataAssetGuidMatchesStored",
            "currentBindingPlanPathMatchesStored", "currentBindingPlanHashMatchesStored", "currentManifestMatchesStored",
            "currentOwnerEnabled", "expectedOwnerEnabled", "sourceSerializedEffectiveActive",
            "expectedSerializedEffectiveActive", "sourceHierarchyActive", "expectedHierarchyActive")
        counts = ("fixedPoseSlotCount", "fixedPoseAttachmentCount", "fixedPoseDrawableAttachmentCount",
            "presentationInstructionCount", "presentationCanvasRendererCount", "rootMeshVertexCount",
            "rootMeshSubmeshCount", "rootCanvasMaterialCount", "registeredRendererCount",
            "presenterProofArrayLength", "presenterMatchingProofCount")
        strings += ("diagnostic", "currentOwnerType", "currentOwnerIdentityComponentId", "currentSourceIdentityComponentType",
            "currentDataAssetType", "currentDataAssetPath", "currentDataAssetGuid", "currentDataAssetId",
            "currentBindingPlanPath", "currentBindingPlanSha256", "currentSourceManifestSha256")
        proof = {key: "" for key in strings} | {key: False for key in booleans} | {key: 0 for key in counts} | {
            "sourceTimeScale": 0.0, "nativeTimeScale": 0.0, "actualTrackTime": 0.0}
        self.assertTrue(_empty_spine_pose_placeholder(None))
        self.assertTrue(_empty_spine_pose_placeholder(proof))
        for key, value in (("sourceComponentId", "source-id"), ("sourceBindingPlanPath", "Assets/plan.json"),
                           ("sourceSkin", "default"), ("runtimeDefaultSkinName", "default"),
                           ("sourceTargetFieldsJson", "[]"), ("verified", True),
                           ("presenterFound", True), ("presenterProofArrayLength", 1),
                           ("currentOwnerType", "Spine.Unity.SkeletonGraphic")):
            bad = copy.deepcopy(proof)
            bad[key] = value
            self.assertFalse(_empty_spine_pose_placeholder(bad), key)
        bad = copy.deepcopy(proof)
        bad["unexpectedEvidence"] = True
        self.assertFalse(_empty_spine_pose_placeholder(bad))

    def test_creator_nondraw_sprite_requires_exact_binding_policy_and_native_frame(self):
        from src.monkey.prefab_static_sort_readback import _creator_non_draw_errors
        def case(source_frame, needs_binding, source_asset_id, image_uuid, resolved_frame,
                 enabled, source_enabled=True, actual_frame="__expected__", saved_image_uuid=None,
                 saved_frame_uuid=None):
            fields = {"__type__": "cc.Sprite"}
            if source_frame is not None:
                fields["_spriteFrame"] = {"__uuid__": source_frame}
            fields_json = __import__("json").dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            fields_hash = __import__("hashlib").sha256(fields_json.encode("utf-8")).hexdigest()
            expected = {"sourceId": "sprite-id", "nativeId": "sprite-native", "node": "sprite-node",
                "sourceType": "cc.Sprite", "expectedNativeType": "Sprite", "sourceEnabled": source_enabled,
                "sourceActive": True, "nativeEnabledExpected": enabled, "sourceNeedsSpriteBinding": needs_binding,
                "sourceFields": fields, "sourceFieldsJson": fields_json, "sourceFieldsSha256": fields_hash,
                "sourceSpriteFrameUuid": source_frame, "sourceTextureBound": source_frame is not None,
                "sourceSpriteFrameAssetId": source_asset_id, "nativeSpriteImageUuidExpected": image_uuid,
                "sourceText": None, "sourceTextEmpty": False,
                "nativeTextExpectation": None, "sourceFontId": None, "nativeFontAssetId": None,
                "nativeFallbackAssetIds": [], "targetSystemFontFamily": None, "creatorMarkup": None,
                "noDrawReason": "null-sprite-frame" if needs_binding else "disabled-source" if not source_enabled else "invalid-active-draw"}
            actual = {"sourceId": "sprite-id", "nativeId": "sprite-native", "node": "sprite-node",
                "sourceType": "cc.Sprite", "expectedNativeType": "Sprite", "actualNativeType": "Sprite",
                "componentUuid": "native-component-sprite", "sourceEnabled": source_enabled, "sourceActive": True,
                "componentEnabled": enabled, "nativeEnabledExpected": enabled, "sourceNeedsSpriteBinding": needs_binding,
                "nodeActive": True, "effectiveActive": True, "noDrawReason": expected["noDrawReason"],
                "sourceFieldsJson": fields_json, "sourceFieldsSha256": fields_hash,
                "sourceSpriteFrameUuid": source_frame,
                "sourceSpriteFrameAssetId": source_asset_id, "nativeSpriteImageUuidExpected": image_uuid,
                "nativeSpriteFrameUuid": resolved_frame if actual_frame == "__expected__" else actual_frame,
                "nativeSpriteFrameUuidExpected": resolved_frame, "sourceText": None, "actualText": None,
                "sourceTextEmpty": False, "nativeTextExpectation": None, "sourceFontId": None,
                "nativeFontAssetId": None, "nativeFallbackAssetIds": [], "targetSystemFontFamily": None,
                "creatorMarkup": None, "verified": True}
            spec = {"nonDrawRenderers": [expected], "sourceNodeActive": {"sprite-node": True}}
            assets = [] if source_asset_id is None else [{"sourceId": source_asset_id, "kind": "sprite",
                "uuid": image_uuid if saved_image_uuid is None else saved_image_uuid,
                "spriteFrameUuid": resolved_frame if saved_frame_uuid is None else saved_frame_uuid}]
            return _creator_non_draw_errors(spec, {"sourceNonDrawRenderers": [actual]}, assets)

        image_uuid = "12345678-1234-4234-8234-1234567890ab"
        sprite_frame_uuid = "12345678-1234-4234-8234-1234567890ab@f9941"
        self.assertEqual([], case(None, True, None, None, None, False))
        self.assertEqual([], case("source-frame", False, "fixture:frame", image_uuid, sprite_frame_uuid,
                                  False, source_enabled=False))
        self.assertTrue(case(None, True, "fixture:frame", image_uuid, sprite_frame_uuid, False))
        self.assertTrue(case("source-frame", False, "fixture:frame", image_uuid, sprite_frame_uuid, False,
                             source_enabled=False, actual_frame="wrong-native-frame"))
        self.assertTrue(case("source-frame", False, "fixture:frame", image_uuid, sprite_frame_uuid, False,
                             source_enabled=False, saved_image_uuid="ffffffff-ffff-4fff-8fff-ffffffffffff"))
        self.assertTrue(case("source-frame", False, "fixture:frame", image_uuid, sprite_frame_uuid, False,
                             source_enabled=False, saved_frame_uuid="12345678-1234-4234-8234-1234567890ab@other"))
        self.assertTrue(case("source-frame", True, None, None, None, False))

    def test_creator_verifier_resolves_native_frame_through_saved_image_asset_rows(self):
        import hashlib
        import json
        source_id = "fixture:prefab#1/components/0"
        source_event = {"kind": "renderer", "node": "sprite-node", "sourceComponentId": source_id}
        source_frame = "fixture-source-frame"
        asset_id = "fixture:frame-asset"
        image_uuid = "12345678-1234-4234-8234-1234567890ab"
        frame_uuid = "12345678-1234-4234-8234-1234567890ab@f9941"
        source_fields = {"__type__": "cc.Sprite", "_spriteFrame": {"__uuid__": source_frame}}
        fields_json = json.dumps(source_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fields_hash = hashlib.sha256(fields_json.encode("utf-8")).hexdigest()
        nondraw = {"sourceId": source_id, "nativeId": "native-sprite", "node": "sprite-node",
            "sourceType": "cc.Sprite", "expectedNativeType": "Sprite", "sourceEnabled": False,
            "sourceActive": True, "sourceNeedsSpriteBinding": False, "nativeEnabledExpected": False,
            "sourceFields": source_fields, "sourceFieldsJson": fields_json, "sourceFieldsSha256": fields_hash,
            "sourceSpriteFrameUuid": source_frame, "sourceTextureBound": True,
            "sourceSpriteFrameAssetId": asset_id, "nativeSpriteImageUuidExpected": image_uuid,
            "sourceText": None, "sourceTextEmpty": False, "nativeTextExpectation": None,
            "sourceFontId": None, "nativeFontAssetId": None, "nativeFallbackAssetIds": [],
            "targetSystemFontFamily": None, "creatorMarkup": None, "noDrawReason": "disabled-source"}
        mapping = {"sourceComponentId": source_id, "node": "sprite-node", "disposition": "source-render-event",
                   "sourceEventIndex": 0, "noDrawReason": "disabled-source"}
        spec = {"rootScope": "root", "sourcePrefabId": "fixture:prefab", "prefabPath": "db://assets/Fixture.prefab",
            "sourceOriginalDrawEvents": [source_event], "sourceDrawEvents": [], "renderers": [], "masks": [],
            "sourceSortOrderFields": [], "sourceSortRoots": [], "nonDrawRenderers": [nondraw],
            "sourceNonDrawRenderers": [mapping], "sourceNodeActive": {"sprite-node": True}}
        plan = {"staticSortQueue": [spec], "sourcePrefabs": [{"sourceId": spec["sourcePrefabId"], "path": spec["prefabPath"]}]}
        native = {"sourceId": source_id, "nativeId": "native-sprite", "node": "sprite-node",
            "sourceType": "cc.Sprite", "expectedNativeType": "Sprite", "actualNativeType": "Sprite",
            "componentUuid": "native-component-sprite", "sourceEnabled": False, "sourceActive": True,
            "componentEnabled": False, "nativeEnabledExpected": False, "sourceNeedsSpriteBinding": False,
            "nodeActive": True, "effectiveActive": True, "noDrawReason": "disabled-source",
            "sourceFieldsJson": fields_json, "sourceFieldsSha256": fields_hash,
            "sourceSpriteFrameUuid": source_frame, "nativeSpriteFrameUuid": frame_uuid,
            "sourceSpriteFrameAssetId": asset_id, "nativeSpriteImageUuidExpected": image_uuid,
            "nativeSpriteFrameUuidExpected": frame_uuid, "sourceText": None, "actualText": None,
            "sourceTextEmpty": False, "nativeTextExpectation": None, "sourceFontId": None,
            "nativeFontAssetId": None, "nativeFallbackAssetIds": [], "targetSystemFontFamily": None,
            "creatorMarkup": None, "verified": True}
        asset = {"sourceId": asset_id, "kind": "sprite", "uuid": image_uuid, "spriteFrameUuid": frame_uuid}
        persistent = {"rootScope": "root", "presentationMode": "persistent", "verified": True,
            "sourceTreePreserved": True, "sourceFieldsPreserved": True, "sourceSortRootsPreserved": True,
            "sourceLayersPreserved": True, "drawSequenceVerified": True, "sourceQueueProjectionVerified": True,
            "sourceOriginalDrawEvents": [source_event], "sourceNonDrawSourceMappings": [{**mapping, "verified": True}],
            "sourceNonDrawRenderers": [native], "sourceSortOrderFields": [], "sourceSortRoots": [],
            "graphics": [], "masks": []}
        initialized = {**persistent, "presentationMode": "initialized", "sourceSuppressed": True,
                       "nestedProxyRootsDisabled": True}
        saved = {"assets": [asset], "sourcePrefabs": [{"sourceId": spec["sourcePrefabId"], "path": spec["prefabPath"],
            "staticSortQueue": {"persistent": persistent, "initialized": initialized}}]}
        self.assertEqual([], verify_creator(plan, saved))
        saved["assets"][0]["uuid"] = "ffffffff-ffff-4fff-8fff-ffffffffffff"
        self.assertTrue(any("saved ImageAsset/SpriteFrame identity mapping differs" in row["message"]
                            for row in verify_creator(plan, saved)))

    def test_negative_z_reflection_keeps_rect_axes_and_depth_vertices(self):
        # Neutral matrix proof for the Unity decomposition used by
        # CopyWorldRect: source basis (X,Y,-Z) must stay (X,Y,-Z), rather than
        # Matrix4x4.rotation/lossyScale redistributing reflection into X/Y.
        source_basis = ((1, 0, 0), (0, 1, 0), (0, 0, -1))
        signed_scale = (1, 1, -1)
        reconstructed_basis = ((1 * signed_scale[0], 0, 0),
                               (0, 1 * signed_scale[1], 0),
                               (0, 0, 1 * signed_scale[2]))
        self.assertEqual(source_basis, reconstructed_basis)
        rect_corners = [(-55, -55, 0), (55, -55, 0), (55, 55, 0), (-55, 55, 0)]
        source_world = [(x, y, -z) for x, y, z in rect_corners]
        proxy_world = [(x * signed_scale[0], y * signed_scale[1], z * signed_scale[2])
                       for x, y, z in rect_corners]
        self.assertEqual(source_world, proxy_world)
        source_depth_vertex = (0.25, -0.5, 2.0)
        proxy_depth_vertex = (source_depth_vertex[0] * signed_scale[0],
                              source_depth_vertex[1] * signed_scale[1],
                              source_depth_vertex[2] * signed_scale[2])
        self.assertEqual((0.25, -0.5, -2.0), proxy_depth_vertex)
        helper = Path(__file__).parents[1] / "src/monkey/targets/UnityStaticSortQueueProxy.cs"
        text = helper.read_text(encoding="utf-8")
        self.assertIn("Vector3.Dot(z, forward)", text)
        self.assertIn("MatrixNear(local, reconstructed, 1e-4f)", text)
        zero_depth_source = ((1, 0, 0), (0, 1, 0), (0, 0, 0))
        zero_depth_proxy = ((1, 0, 0), (0, 1, 0), (0, 0, 0))
        self.assertEqual(zero_depth_source, zero_depth_proxy)
        self.assertIn("z.sqrMagnitude == 0f ? 0f", text)
        self.assertNotIn("z.magnitude <= 1e-8f", text)

    def test_zero_depth_parent_uses_invertible_ui_plane_for_position_and_mesh(self):
        # A parent scaled to Z=0 has a singular 4x4 inverse but retains a
        # perfectly usable two-axis UI plane. Reconstruct a rotated/scaled
        # child through the same Gram-system plane map.
        px = (0.8660254, 0.5, 0.0)
        py = (-1.5, 2.5980762, 0.0)
        origin = (11.0, -4.0, 0.0)

        def dot(a, b):
            return sum(x * y for x, y in zip(a, b))

        def add(a, b):
            return tuple(x + y for x, y in zip(a, b))

        def scale(a, factor):
            return tuple(x * factor for x in a)

        def solve_plane(vector):
            xx, xy, yy = dot(px, px), dot(px, py), dot(py, py)
            determinant = xx * yy - xy * xy
            dx, dy = dot(px, vector), dot(py, vector)
            u = (dx * yy - dy * xy) / determinant
            v = (dy * xx - dx * xy) / determinant
            reconstructed = add(scale(px, u), scale(py, v))
            return (u, v), reconstructed

        local_position = (5.0, -7.0)
        world_position = add(origin, add(scale(px, local_position[0]), scale(py, local_position[1])))
        found_position, reconstructed_position = solve_plane(tuple(a - b for a, b in zip(world_position, origin)))
        self.assertAlmostEqual(local_position[0], found_position[0], places=5)
        self.assertAlmostEqual(local_position[1], found_position[1], places=5)
        self.assertAlmostEqual(0.0, math.dist(world_position, add(origin, reconstructed_position)), places=5)

        angle = math.radians(31.0)
        relative_right = (1.2 * math.cos(angle), 1.2 * math.sin(angle))
        relative_up = (-0.7 * math.sin(angle), 0.7 * math.cos(angle))
        source_right = add(scale(px, relative_right[0]), scale(py, relative_right[1]))
        source_up = add(scale(px, relative_up[0]), scale(py, relative_up[1]))
        mapped_right, rebuilt_right = solve_plane(source_right)
        mapped_up, rebuilt_up = solve_plane(source_up)
        self.assertAlmostEqual(relative_right[0], mapped_right[0], places=5)
        self.assertAlmostEqual(relative_right[1], mapped_right[1], places=5)
        self.assertAlmostEqual(relative_up[0], mapped_up[0], places=5)
        self.assertAlmostEqual(relative_up[1], mapped_up[1], places=5)
        self.assertAlmostEqual(0.0, math.dist(source_right, rebuilt_right), places=5)
        self.assertAlmostEqual(0.0, math.dist(source_up, rebuilt_up), places=5)
        helper = Path(__file__).parents[1] / "src/monkey/targets/UnityStaticSortQueueProxy.cs"
        text = helper.read_text(encoding="utf-8")
        self.assertIn("TrySolvePlaneCoordinates", text)
        self.assertIn("CopyWorldRectOnSingularPlane", text)
        self.assertIn("InverseTransformPointForUiPlane", text)

    def test_graphic_collection_stops_at_every_source_node_boundary(self):
        # Neutral traversal fixture: a disabled/inactive source child owns its
        # own non-draw row and must not be absorbed into the parent's TMP mesh.
        source_child_nodes = {"inactive_sprite", "disabled_label"}
        owner_children = ["inactive_sprite", "disabled_label", "generated_tmp_segment"]

        def collect(children):
            collected = []
            for child in children:
                if child in source_child_nodes:
                    continue
                if child == "generated_tmp_segment":
                    collected.append(child)
                    continue
                raise ValueError("unclassified child graphic: " + child)
            return collected

        self.assertEqual(["generated_tmp_segment"], collect(owner_children))
        with self.assertRaisesRegex(ValueError, "unclassified child graphic: foreign_image"):
            collect(owner_children + ["foreign_image"])
        helper = Path(__file__).parents[1] / "src/monkey/targets/UnityStaticSortQueueProxy.cs"
        text = helper.read_text(encoding="utf-8")
        self.assertIn("if (sourceNode != null && sourceNode != row.node) continue;", text)
        self.assertIn(";childPath=", text)
        self.assertIn(";graphicTypes=", text)

    def test_non_draw_carrier_accepts_inactive_but_enabled_and_rejects_active_enabled(self):
        valid_non_draw = {"sourceEnabled": True, "sourceActive": False}
        invalid_non_draw = {"sourceEnabled": True, "sourceActive": True}
        should_reject = lambda spec: spec["sourceEnabled"] and spec["sourceActive"]
        self.assertFalse(should_reject(valid_non_draw))
        self.assertTrue(should_reject(invalid_non_draw))
        helper = Path(__file__).parents[1] / "src/monkey/targets/UnityStaticSortQueueProxy.cs"
        text = helper.read_text(encoding="utf-8")
        self.assertIn("row.sourceEnabled && row.sourceActive", text)

    def test_richtext_source_markup_and_native_projection_are_separate(self):
        expected = {"sourceComponentId": "rich-empty", "node": "rich-node", "sourceType": "cc.RichText",
                    "expectedGraphicType": "TMPro.TextMeshProUGUI", "sourceEnabled": True,
                    "sourceActive": False, "sourceText": "<color=#fff></color>",
                    "nativeTextExpectation": "<color=#fff></color>", "sourceTextEmpty": True,
                    "sourceFontMissing": False, "sourceTextureBound": False}
        actual = {"sourceNode": "rich-node", "sourceType": "cc.RichText",
                  "sourceComponentType": "TMPro.TextMeshProUGUI", "sourceEnabled": True,
                  "sourceActive": False, "sourceActiveInHierarchy": False,
                  "sourceActiveSelf": True, "sourceActivityMatchesExpected": True,
                  "sourceSerializedActive": False, "sourceSerializedActiveVerified": True,
                  "sourceHierarchyActiveMatchesExpected": True, "sourceActivityStage": "persistent-serialized-scope",
                  "sourceText": "<color=#fff></color>", "nativeTextExpectation": "<color=#fff></color>",
                  "nativeText": "<color=#fff></color>", "sourceTextEmpty": True, "nativeTextEmpty": True,
                  "nativeGraphicEnabled": True,
                  "sourceFontMissing": False, "nativeFontMissing": False,
                  "sourceTextureBound": False, "sourceReferenceVerified": True,
                  "typedFieldsVerified": True, "carrierPresent": True, "verified": True,
                  "carrierAssetIdentityVerified": True, "carrierOwnerScopeVerified": False,
                  "carrierGuid": "e" * 32, "carrierLocalFileId": 126,
                  "carrierLocalFileId": 126, "noDrawReason": "source-node-inactive"}
        self.assertTrue(_empty_renderer_matches(expected, actual, "persistent"))
        expected["sourceText"] = "<color=#fff>source</color>"
        expected["nativeTextExpectation"] = "<color=#0f0>target</color>"
        actual["sourceText"] = expected["sourceText"]
        actual["nativeTextExpectation"] = expected["nativeTextExpectation"]
        actual["nativeText"] = expected["nativeTextExpectation"]
        self.assertTrue(_empty_renderer_matches(expected, actual, "persistent"))
        actual["nativeText"] = actual["sourceText"]
        self.assertFalse(_empty_renderer_matches(expected, actual, "persistent"))
        actual["nativeText"] = expected["nativeTextExpectation"]
        actual["sourceActivityMatchesExpected"] = False
        self.assertFalse(_empty_renderer_matches(expected, actual, "persistent"))


if __name__ == "__main__":
    unittest.main()
