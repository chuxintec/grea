import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "src/monkey/targets/UnityStaticSortQueueProxy.cs"


class UnityStaticSortCaptureScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def block(self, start, end):
        a = self.source.index(start)
        b = self.source.index(end, a)
        return self.source[a:b]

    def test_nested_presenters_restore_source_cull_before_hiding_proxy_roots(self):
        scope = self.block("sealed class NestedProxyCaptureScope", "static void EnsureSourceGraphicMeshReady")
        self.assertLess(scope.index("presenters[i].enabled = false"), scope.index("roots[i].SetActive(false)"))
        self.assertIn("if (presenters[i] != null) presenters[i].enabled = presenterEnabledBefore[i];", scope)
        self.assertIn("if (roots[i] != null) roots[i].SetActive(rootActiveBefore[i]);", scope)
        self.assertIn("!IsGeneratedSortProxyRoot(roots[i].transform)", scope)

    def test_capture_prepares_typed_sources_and_keeps_spine_and_tmp_child_mesh_owners(self):
        prepare = self.block("static void EnsureSourceGraphicMeshReady", "static void InitializeSourceSpineStaticPose")
        self.assertLess(prepare.index("IsSpineCanvasSubmesh"), prepare.index("graphic.SetAllDirty()"))
        self.assertIn("IsGeneratedTextSubmesh(graphic.gameObject)", prepare)
        self.assertIn("tmp.ForceMeshUpdate(true, false)", prepare)
        self.assertIn("InitializeSourceSpineStaticPose(sourceRoot)", self.source)

    def test_image_capture_rebuilds_culled_scroll_content_mesh_and_restores_viewport_cull(self):
        prepare = self.block("static void EnsureSourceGraphicMeshReady", "static void InitializeSourceSpineStaticPose")
        self.assertIn("var cullBefore = renderer.cull", prepare)
        self.assertIn("if (graphic is Image && cullBefore) renderer.cull = false", prepare)
        self.assertIn("graphic.Rebuild(CanvasUpdate.PreRender)", prepare)
        self.assertIn("if (graphic is Image) renderer.cull = cullBefore", prepare)
        self.assertIn("STATIC_SORT_PROXY_SOURCE_IMAGE_CULL_RESTORE_FAILED", prepare)
        diagnostics = self.block("static string SourceGraphicMeshDiagnostic(", "static ProxySpineOwnerDelegation CreateSpineOwnerDelegation(")
        self.assertIn("rendererCull=", diagnostics)
        self.assertIn("activeInHierarchy=", diagnostics)
        self.assertIn("maskAncestors=", diagnostics)

    def test_capture_scope_wraps_creation_and_commits_after_outer_suppression(self):
        wrapper = self.block("public static ProxyQueueReadback CreateStaticSortQueueProxy(",
                             "static ProxyQueueReadback CreateStaticSortQueueProxyCore(")
        core = self.block("static ProxyQueueReadback CreateStaticSortQueueProxyCore(",
                          "public static ProxyQueueReadback ReadStaticSortQueueProxy(")
        self.assertIn("using (var capture = new NestedProxyCaptureScope", wrapper)
        self.assertIn("PrepareSourceGeometryForCapture(spec, sourceNodes, sourceRoot)", core)
        self.assertLess(core.index("presenter.InitializePresentation()"), core.index("nestedCapture.Commit()"))

    def test_readback_keeps_failed_rows_and_continues_across_siblings(self):
        read = self.block("static ProxyQueueReadback ReadProxy(", "\n    }\n\n}")
        self.assertIn("if (empty != null) emptyGraphics.Add(empty);", read)
        self.assertIn("structuralDiagnostics.Add(\"STATIC_SORT_PROXY_EMPTY_RENDERER_READBACK_INVALID", read)
        self.assertIn("foreach (Transform child in node) if (!Visit(child)) childrenOK = false;", read)
        self.assertIn("structuralDiagnostics = structuralDiagnostics.ToArray()", read)
        self.assertIn("STATIC_SORT_PROXY_GRAPHIC_READBACK_INVALID", read)
        self.assertIn("STATIC_SORT_PROXY_MASK_READBACK_INVALID", read)

    def test_text_owner_slot_coverage_uses_resolved_source_graphic_identity(self):
        coverage = self.block("static bool ValidateSourceGraphicCoverage(", "static NativeStaticSortQueueProxyGraphic CreateProxyGraphic(")
        self.assertIn("ResolveGeneratedSlot(textIdentity, expectedTextOwner", coverage)
        self.assertIn("slotBinding.sourceGraphic == (expectedTextOwner as Graphic)", coverage)
        self.assertIn("textIdentity.sourceOwner == expectedTextOwner", coverage)
        self.assertNotIn("textIdentity.GetComponent<Graphic>() !=", coverage)
        self.assertIn(";phase=\" +", coverage)
        self.assertIn('"capture-in-memory", null, blockInputRows', self.source)
        self.assertIn('provisional ? "pre-save-provisional" : verifyRuntimeGeometry ? "loaded" : "persistent"', self.source)

    def test_persistent_text_coverage_uses_saved_typed_slot_proof_without_live_generated_slot_resolution(self):
        coverage = self.block("static bool ValidateSourceGraphicCoverage(", "static NativeStaticSortQueueProxyGraphic CreateProxyGraphic(")
        self.assertIn("if (!requireGeneratedTextSlots)", coverage)
        self.assertIn("textSourceVerified.TryGetValue(textIdentity", coverage)
        self.assertIn("savedSlot.sourceMeshSha256", coverage)
        self.assertIn("if (textIdentity.materialSlot == 0) boundGraphics.Add(expectedTextOwner as Graphic)", coverage)
        self.assertIn("if (!UnityStaticSortTextSource.ResolveGeneratedSlot(textIdentity, expectedTextOwner", coverage)

    def test_non_draw_marker_readback_distinguishes_persistent_id_from_loaded_owner_scope(self):
        empty = self.block("static ProxyEmptyRendererReadback ReadEmptyRenderer(", "static string SourceNullSpriteProofDiagnostic(")
        self.assertIn("carrierAssetIdentityVerified = carrierPersistent", empty)
        self.assertIn("carrierOwnerScopeVerified = carrierOwnerScopeVerified", empty)
        self.assertIn("loadedReadback ? carrierOwnerScopeVerified : carrierPersistent", empty)
        self.assertIn("nullSpriteNoMaterialReason || nullSpriteZeroMeshReason", empty)
        self.assertIn("materialCount == 0", empty)

    def test_retained_non_draw_marker_is_kept_out_of_draw_event_sort_only_with_exact_non_draw_identity(self):
        sorter = self.block("static void SortGeneratedProxyChildrenBySourceEvent(", "static Mesh SnapshotSubmesh(")
        retained = sorter[sorter.index('if (marker.kind == "retainedNonDraw")'):]
        self.assertIn("spec.nonDrawRenderers", retained)
        self.assertIn("nonDrawMatches.Length != 1", retained)
        self.assertIn("rendererOrder.ContainsKey(marker.sourceComponentId)", retained)
        self.assertIn("marker.queueIndex != -1", retained)
        self.assertIn("eventIndex = Int32.MaxValue", retained)
        self.assertIn('else if (marker.kind == "renderer" || marker.kind == "emptyRenderer")', sorter)
        self.assertIn("STATIC_SORT_PROXY_EVENT_SORT_RENDERER_EVENT_MISSING", sorter)

    def test_persistent_tmp_generated_child_snapshot_uses_typed_slot_and_asset_readback(self):
        read = self.block("static ProxyQueueReadback ReadProxy(", "\n    }\n\n}")
        self.assertIn("proxy.sourceGraphic == (Graphic)textIdentity.sourceOwner", read)
        self.assertIn("textOwnerGraphicReferenceValid", read)
        self.assertIn("persistentTextEvidence.proxyMaterialGuid == actualMaterialGuid", read)
        self.assertIn("persistentTextEvidence.bakedProxyMaterialFingerprint == proxyMaterialFingerprint", read)
        self.assertIn("persistentTextEvidence.textureGuid == actualTextureGuid", read)
        self.assertIn("var sourceMaterialMatches = textIdentity != null && !verifyRuntimeGeometry ?", read)

    def test_native_structure_and_presentation_aggregate_gates_emit_named_failures(self):
        read = self.block("static ProxyQueueReadback ReadProxy(", "\n    }\n\n}")
        for key in ("rootMarkerVerified", "prefabPathVerified", "sourceActivePreserved",
                    "rendererDenominatorVerified", "presenterReferencesVerified", "maskRowsVerified",
                    "nativeStructureVerified", "graphicsStaticSnapshotVerified",
                    "graphicsRuntimeGeometryVerified", "sourceMaskIdentitiesVerified", "aggregateDiagnostics"):
            self.assertIn(key, read)
        self.assertIn("rendererDenominatorVerified=false;expectedDraw=", read)
        self.assertIn("persistentSnapshotVerified=false;nativeStructure=", read)
        self.assertIn("initializedPresentationVerified=false;persistentSnapshot=", read)

    def test_inactive_source_mask_identity_is_exact_and_phase_aware(self):
        helper = self.block("static ProxySourceMaskIdentityReadback[] ReadSourceMaskIdentities(",
                            "static bool ValidateSourceGraphicCoverage(")
        coverage = self.block("static bool ValidateSourceGraphicCoverage(",
                              "static NativeStaticSortQueueProxyGraphic CreateProxyGraphic(")
        self.assertIn("UnityStaticMaskSort.ReadStaticMask(maskSpec, node, resolveSprite)", helper)
        self.assertIn("sourceFieldsJson == row.sourceFieldsJson", helper)
        self.assertIn("!loadedPhase ||", helper)
        self.assertIn("!sourceMaskRow.sourceActiveExpected", coverage)
        self.assertIn("sourceIdentity.sourceId == sourceMaskRow.sourceId", coverage)
        integration = Path(__file__).parents[1] / "src/monkey/targets/UnityStaticSortQueueIntegration.cs"
        integration_text = integration.read_text(encoding="utf-8")
        self.assertIn("plan.staticMasks.masks", integration_text)
        self.assertIn("queue.sourceMaskIdentities = sourceMaskRows", integration_text)

    def test_source_tree_allows_only_sdk_registered_spine_generated_children(self):
        tree = self.block("static bool SourceTreeMatchesProxy(", "static void SortGeneratedProxyChildrenBySourceEvent(")
        helper = self.block("static bool TryGetGeneratedSpineSourceIdentity(", "static string TransformPath(")
        self.assertIn("TryGetGeneratedSpineSourceIdentity(spec, nodes, child", tree)
        self.assertIn('"<typed-generated-Spine:"', tree)
        self.assertIn("IsSpineCanvasSubmesh(child.gameObject, ownerGraphic)", helper)
        self.assertIn('row.sourceType == "sp.Skeleton" && row.node == resolvedOwnerNodeId', helper)
        self.assertIn("ownerGraphic.enabled != ownerSpec.sourceEnabled", helper)
        self.assertIn("mappedOwner.activeInHierarchy != ownerSpec.sourceActive", helper)
        self.assertNotIn("child.name == \"Renderer0\"", helper)

    def test_loaded_prefab_path_uses_exact_presenter_asset_scope_without_instance_asset_path(self):
        read = self.block("static ProxyQueueReadback ReadProxy(", "\n    }\n\n}")
        self.assertIn("AssetDatabase.GetAssetPath(prefabAsset) == spec.prefabPath", read)
        self.assertIn("verifyRuntimeGeometry ? loadedPrefabScopeOK", read)
        self.assertIn("presenter.sourcePrefabId == spec.sourcePrefabId", read)
        self.assertIn("presenter.sourceRoot == sourceRoot && presenter.proxyRoot == proxyRoot", read)
        self.assertIn("scopeProvenance.loadedScopeRoot == sourceRoot", read)
        self.assertIn("pinnedPersistentRoot == sourceRoot", read)
        self.assertIn("EditorUtility.IsPersistent(pinnedPersistentRoot)", read)
        self.assertIn("loadedSourceRootIsPersistent = sourceRoot != null && EditorUtility.IsPersistent(sourceRoot)", read)
        self.assertIn("pinnedPersistentRootPrefabPath == spec.prefabPath", read)

    def test_input_only_surface_exclusion_is_typed_and_owned_by_exact_blocker(self):
        presenter = Path(__file__).parents[1] / "src/monkey/targets/NativeStaticSortQueueProxyPresenter.cs"
        text = presenter.read_text(encoding="utf-8")
        source_graphics = text[text.index("IEnumerable<Graphic> SourceGraphics()"):text.index("bool IsGeneratedProxyRoot(")]
        self.assertIn("graphic is NativeInputBlockerSurface", source_graphics)
        self.assertIn("inputBlocker.OwnsSurface", source_graphics)
        self.assertIn("inputBlocker.Surface == graphic", source_graphics)
        self.assertNotIn("graphic.color.a", source_graphics)

    def test_block_input_events_have_typed_readback_and_coverage_proof(self):
        block_input = self.block("static ProxyBlockInputReadback[] ReadBlockInputEvents(",
                                 "static bool ValidateSourceGraphicCoverage(")
        coverage = self.block("static bool ValidateSourceGraphicCoverage(",
                              "static NativeStaticSortQueueProxyGraphic CreateProxyGraphic(")
        self.assertIn("blocker.OwnsSurface", block_input)
        self.assertIn("blocker.Surface", block_input)
        self.assertIn("clearMesh", block_input)
        self.assertIn("inputRow.verified", coverage)
        self.assertIn("blocker.Surface is NativeInputBlockerSurface", coverage)
        self.assertIn("sourceBlockInputEventsVerified", self.source)
        sync = self.block("static void SynchronizeBlockInputSourceActivity(",
                          "public static ProxyQueueReadback CreateStaticSortQueueProxy(")
        self.assertIn("SynchronizeSourceActivity(row.sourceEnabled, row.sourceActive)", sync)
        self.assertIn("SynchronizeBlockInputSourceActivity(spec, sourceNodes);", self.source)

    def test_loaded_geometry_reports_rect_and_exact_transformed_fingerprint_separately(self):
        self.assertIn("expectedTransformedMeshSha256, out actualTransformedMeshSha256", self.source)
        self.assertIn("worldRectVerified && transformedMeshMetricsVerified", self.source)
        self.assertIn("transformDiagnostics.maxWorldVertexError <= .001f", self.source)
        self.assertIn("transformedMeshFingerprintVerified = transformedMeshFingerprintVerified", self.source)
        self.assertIn("transformedMeshMetricsVerified = transformedMeshMetricsVerified", self.source)
        self.assertIn("expectedTransformedMeshSha256 = expectedTransformedMeshSha256", self.source)
        self.assertIn("actualTransformedMeshSha256 = actualTransformedMeshSha256", self.source)
        self.assertIn(";worldRect=", self.source)
        self.assertIn(";transformedFingerprint=", self.source)

    def test_world_vertex_precision_helper_runs_after_exact_ui_plane_inverse(self):
        snapshot = self.block("static Mesh SnapshotSubmesh(", "static Mesh PersistMesh(")
        self.assertIn("var desiredWorld = sourceMatrix.MultiplyPoint3x4(vertex)", snapshot)
        self.assertIn("Vector3.Distance(proxyMatrix.MultiplyPoint3x4(vertex), desiredWorld) <= .001f", snapshot)
        self.assertIn("return vertex", snapshot)
        self.assertIn("var initialLocal = InverseTransformPointForUiPlane(proxyTransform, desiredWorld", snapshot)
        self.assertIn("UnityStaticSortVertexPrecision.ImproveInitialLocalPoint(proxyMatrix.MultiplyPoint3x4", snapshot)
        self.assertIn("MatrixExactlyEquals(sourceMatrix, proxyMatrix) || sameLinearBasis || sourceAndProxyShareObservedUiPlane", snapshot)
        measure = self.block("static TransformedMeshDiagnostics MeasureTransformedMesh(", "static string UvValueDiagnostic(")
        self.assertIn("sourceMatrix.MultiplyPoint3x4(sourceVertices[index])", measure)
        self.assertIn("proxyMatrix.MultiplyPoint3x4(proxyVertices[index])", measure)
        self.assertIn("transformDiagnostics.maxWorldVertexError <= .001f", self.source)

    def test_rect_copy_preserves_exactly_collapsed_xy_axes(self):
        copy_rect = self.block("static void CopyWorldRect(", "static bool IsGeneratedTextSubmesh(")
        self.assertIn("if (sx == 0f && sy == 0f)", copy_rect)
        self.assertIn("else if (sx == 0f)", copy_rect)
        self.assertIn("else if (sy == 0f)", copy_rect)
        self.assertIn("proxy.localScale = new Vector3(sx, sy, signedZ)", copy_rect)
        self.assertIn("MatrixNear(local, reconstructed, 1e-4f)", copy_rect)
        plane = self.block("static bool TrySolvePlaneCoordinates(", "static Vector3 InverseTransformPointForUiPlane(")
        self.assertIn("var scale = Mathf.Max(xx, yy)", plane)
        self.assertIn("if (scale == 0f)", plane)
        self.assertIn("else if (xx >= yy)", plane)

    def test_direct_source_root_proxy_uses_exact_local_identity(self):
        copy_rect = self.block("static void CopyWorldRect(", "static bool IsGeneratedTextSubmesh(")
        identity = copy_rect[copy_rect.index("if (source.transform == parent)"):copy_rect.index("if (Mathf.Abs(parent.localToWorldMatrix.determinant)")]
        self.assertIn("proxy.anchorMin = source.pivot; proxy.anchorMax = source.pivot", identity)
        self.assertIn("proxy.localPosition = Vector3.zero", identity)
        self.assertIn("proxy.localRotation = Quaternion.identity", identity)
        self.assertIn("proxy.localScale = Vector3.one", identity)
        self.assertIn("if (!WorldRectMatches(source, proxy))", identity)
        self.assertIn("STATIC_SORT_PROXY_IDENTITY_CHILD_RECT_NOT_EXACT", identity)

    def test_same_parent_world_basis_copies_local_rect_trs_without_decomposition(self):
        copy_rect = self.block("static void CopyWorldRect(", "static bool IsGeneratedTextSubmesh(")
        self.assertIn("LinearBasisExactlyEquals(source.parent.localToWorldMatrix, parent.localToWorldMatrix)", copy_rect)
        self.assertIn("correctionSucceeded = TrySolveBasisTranslation(parent, parentOriginDelta, out localCorrection)", copy_rect)
        self.assertIn("var fixedAnchor = parent is RectTransform parentRect ? parentRect.pivot", copy_rect)
        self.assertIn("proxy.anchorMin = fixedAnchor; proxy.anchorMax = fixedAnchor", copy_rect)
        self.assertIn("proxy.localRotation = source.localRotation; proxy.localScale = source.localScale", copy_rect)
        self.assertIn("proxy.localPosition = source.localPosition + localCorrection", copy_rect)
        self.assertIn("proxy.position = source.position", copy_rect)
        self.assertIn("if (IsFinite(parentMatrix.determinant) && parentMatrix.determinant != 0f)", copy_rect)
        self.assertNotIn("proxy.localPosition = pivotLocal", copy_rect)
        self.assertIn("STATIC_SORT_PROXY_EQUAL_BASIS_RECT_NOT_EXACT", copy_rect)
        self.assertIn("established strict inverse/plane path below", copy_rect)
        self.assertNotIn("STATIC_SORT_PROXY_EQUAL_BASIS_ORIGIN_UNREPRESENTABLE", copy_rect)
        snapshot = self.block("static Mesh SnapshotSubmesh(", "static Mesh PersistMesh(")
        self.assertIn("var transformsIdentical = MatrixExactlyEquals(sourceTransform.localToWorldMatrix, proxyTransform.localToWorldMatrix)", snapshot)
        self.assertIn("sourceVertices.All(vertex => vertex.z == 0f)", snapshot)
        self.assertIn("ObservableUiPlaneExactlyEquals(sourceTransform.localToWorldMatrix, proxyTransform.localToWorldMatrix)", snapshot)
        self.assertIn("MatrixExactlyEquals(sourceMatrix, proxyMatrix) || sameLinearBasis || sourceAndProxyShareObservedUiPlane", snapshot)
        self.assertIn("if (transformsIdentical || sameLinearBasis || singularPlane) copy.normals = normals", snapshot)
        self.assertIn("if (transformsIdentical || sameLinearBasis || singularPlane) copy.tangents = tangents", snapshot)

    def test_same_basis_proxy_uses_captured_rect_size_instead_of_source_stretch_anchors(self):
        # Source and proxy parents share the same world basis but have different
        # RectTransform dimensions. The source is stretched with a sizeDelta;
        # using its captured rect.size under a fixed parent-pivot anchor keeps
        # the visible rectangle unchanged.
        source_parent_size = (500.0, 200.0)
        proxy_parent_size = (200.0, 500.0)
        source_size_delta = (-200.0, -80.0)
        source_rect_size = tuple(a + b for a, b in zip(source_parent_size, source_size_delta))
        source_pivot = (0.25, 0.75)
        source_local_position = (12.0, -7.0)
        source_corners = [
            (source_local_position[0] - source_pivot[0] * source_rect_size[0],
             source_local_position[1] - source_pivot[1] * source_rect_size[1]),
            (source_local_position[0] + (1 - source_pivot[0]) * source_rect_size[0],
             source_local_position[1] + (1 - source_pivot[1]) * source_rect_size[1]),
        ]
        proxy_corners = [
            (source_local_position[0] - source_pivot[0] * source_rect_size[0],
             source_local_position[1] - source_pivot[1] * source_rect_size[1]),
            (source_local_position[0] + (1 - source_pivot[0]) * source_rect_size[0],
             source_local_position[1] + (1 - source_pivot[1]) * source_rect_size[1]),
        ]
        self.assertNotEqual(source_parent_size, proxy_parent_size)
        self.assertEqual(source_corners, proxy_corners)
        copy_rect = self.block("static void CopyWorldRect(", "static bool IsGeneratedTextSubmesh(")
        same_basis = copy_rect[copy_rect.index("LinearBasisExactlyEquals(source.parent.localToWorldMatrix"):]
        self.assertIn("proxy.sizeDelta = source.rect.size", same_basis)
        self.assertNotIn("proxy.sizeDelta = source.sizeDelta", same_basis)
        self.assertIn("parentRect.pivot", same_basis)
        self.assertNotIn("source.anchorMin", same_basis)

    def test_only_bound_regular_image_mesh_is_rebuilt_during_loaded_readback(self):
        read = self.block("static ProxyQueueReadback ReadProxy(", "\n    }\n\n}")
        self.assertIn("verifyRuntimeGeometry && textIdentity == null && source is Image image && image.sprite != null", read)
        self.assertIn("EnsureLoadedRegularImageMeshReady(image)", read)
        self.assertNotIn("EnsureSourceGraphicMeshReady(source)", read)
        rebuild = self.block("static void EnsureLoadedRegularImageMeshReady(", "static Dictionary<string, OwnerFontStyleDescriptor>")
        self.assertIn("var cullBefore = renderer.cull", rebuild)
        self.assertIn("if (cullBefore) renderer.cull = false", rebuild)
        self.assertIn("renderer.cull = cullBefore", rebuild)

    def test_null_source_sprite_uses_typed_empty_carrier_and_boundness_mismatch_fails(self):
        core = self.block("static ProxyQueueReadback CreateStaticSortQueueProxyCore(",
                          "public static ProxyQueueReadback ReadStaticSortQueueProxy(")
        self.assertIn("(sourceImage.sprite != null) != row.sourceTextureBound", core)
        self.assertIn("STATIC_SORT_PROXY_SOURCE_NULL_SPRITE_NONDRAW_PROOF_FAILED", core)
        self.assertIn("TryCreateEmptyRendererCarrier(spec, row, sourceNodes, sourceNode", core)
        self.assertIn("TryGetSerializedEffectiveActive(queueSpec, sourceNodes, sourceNode", self.source)
        self.assertIn("SourceNullSpriteProofDiagnostic(row, sourceNode)", core)
        self.assertIn("source-sprite-frame-null-native-image-disabled-no-material", self.source)
        self.assertIn("sourceNode.GetComponent<Mask>() != null", self.source)
        self.assertIn("sourceNode.GetComponent<RectMask2D>() != null", self.source)

    def test_source_tree_failure_reports_exact_parent_child_path_and_identity_order(self):
        tree = self.block("static bool SourceTreeMatchesProxy(", "static Mesh SnapshotSubmesh(")
        self.assertIn("unmappedSourceChild;parent=", tree)
        self.assertIn(";path=", tree)
        self.assertIn(";components=", tree)
        self.assertIn("childOrderMismatch;parent=", tree)
        self.assertIn("STATIC_SORT_PROXY_SOURCE_TREE_MISMATCH", self.source)

    def test_spine_mesh_capture_occurs_after_generic_refresh_and_no_later_canvas_rebuild(self):
        core = self.block("static ProxyQueueReadback CreateStaticSortQueueProxyCore(",
                          "public static ProxyQueueReadback ReadStaticSortQueueProxy(")
        spineBranch = core.index('if (row.sourceType == "sp.Skeleton")')
        finalSpine = core.index('FinalizeSourceSpineStaticMesh(pendingSpineGraphics.Select', spineBranch)
        spineCapture = core.index("CreateProxyGraphic(sourceGraphic, pending.sourceOwnerGraphic", finalSpine)
        self.assertLess(spineBranch, finalSpine)
        self.assertLess(finalSpine, spineCapture)
        self.assertIn("SortGeneratedProxyChildrenBySourceEvent(spec, proxyRootObject.transform)", core)
        create = self.block("static NativeStaticSortQueueProxyGraphic CreateProxyGraphic(",
                            "public static ProxyQueueReadback CreateStaticSortQueueProxy(")
        self.assertNotIn("Canvas.ForceUpdateCanvases", create)
        read = self.block("static ProxyQueueReadback ReadProxy(", "\n    }\n\n}")
        self.assertIn('FinalizeSourceSpineStaticMesh(activeSpineOwners, provisional ? "pre-save-provisional-readback" : "loaded-readback")', read)
        self.assertLess(read.index("Canvas.ForceUpdateCanvases()"), read.index("foreach (var identity in proxyRoot"))
        self.assertLess(read.index("foreach (var identity in proxyRoot"), read.index("FinalizeSourceSpineStaticMesh(activeSpineOwners"))

    def test_full_rank_parent_delta_uses_only_finite_inverse_then_existing_corner_gate(self):
        solve = self.block("static bool TrySolveBasisTranslation(", "static bool TrySolvePlaneCoordinates(")
        self.assertIn("if (IsFinite(matrixDeterminant) && matrixDeterminant != 0f)", solve)
        self.assertIn("return IsFinite(localDelta)", solve)
        full_rank = solve[:solve.index("var axes =")]
        self.assertNotIn("sqrMagnitude <= 1e-12f", full_rank)
        copy_rect = self.block("static void CopyWorldRect(", "static bool IsGeneratedTextSubmesh(")
        self.assertIn("if (!WorldRectMatches(source, proxy))", copy_rect)
        self.assertIn("STATIC_SORT_PROXY_EQUAL_BASIS_RECT_NOT_EXACT", copy_rect)

    def test_tmp_capture_and_readback_use_persistent_owner_slot_bindings(self):
        prepare = self.block("static Dictionary<string, OwnerFontStyleDescriptor> PrepareSourceGeometryForCapture",
                             "static string OwnerFontMaterialPath")
        create = self.block("static NativeStaticSortQueueProxyGraphic CreateProxyGraphic(",
                            "public static ProxyQueueReadback CreateStaticSortQueueProxy(")
        core = self.block("static ProxyQueueReadback CreateStaticSortQueueProxyCore(",
                          "public static ProxyQueueReadback ReadStaticSortQueueProxy(")
        read = self.block("static ProxyQueueReadback ReadProxy(", "\n    }\n\n}")
        self.assertIn("UnityStaticSortTextSource.PrepareSource(textOwner", prepare)
        self.assertIn("CaptureOwnerFontMaterial(textOwner, row.sourceComponentId", prepare)
        self.assertLess(prepare.index("PrepareSource(textOwner, row.sourceComponentId"),
                        prepare.index("CaptureOwnerFontMaterial(textOwner, row.sourceComponentId"))
        self.assertGreater(prepare.rindex("PrepareSource(textOwner, row.sourceComponentId"),
                           prepare.index("CaptureOwnerFontMaterial(textOwner, row.sourceComponentId"))
        self.assertIn("CaptureAndRebindTextSlots(spec, row, textOwner, ownerStyle, out var textSlotEnumeration)", core)
        self.assertIn("RebindCapturedSlot(captureProofs[slot], owner, current.sourceGraphic", self.source)
        self.assertIn("GetCurrentSlots(owner, row.sourceComponentId", self.source)
        self.assertIn("CaptureFallbackMaterial(live, materialPath", self.source)
        self.assertLess(self.source.index("CaptureFallbackMaterial(live, materialPath"),
                        self.source.index("PrepareSource(owner, row.sourceComponentId", self.source.index("CaptureFallbackMaterial(live, materialPath")))
        capture_slots = core.index("CaptureAndRebindTextSlots(spec, row, textOwner, ownerStyle, out var textSlotEnumeration)")
        text_proxy = core.index("CreateProxyGraphic(sourceGraphic, sourceNode.GetComponent<Graphic>()", capture_slots)
        self.assertLess(capture_slots, text_proxy)
        self.assertIn("UnityStaticSortTextSource.Attach(proxyObject, textBinding, mesh, meshSha)", create)
        self.assertIn("UnityStaticSortTextSource.ReadPersistent", read)
        self.assertIn("UnityStaticSortTextSource.ReadInitialized", read)
        self.assertIn("textSources = textSourceReadbacks.ToArray()", read)

    def test_optional_mask_proof_strings_canonicalize_null_without_dropping_checks(self):
        for source_name in ("maskSpec", "sourceMask"):
            for field in ("sourceMaterialId", "resolvedSourceMaterialId", "sourceEffectId",
                          "sourceEffectName", "sourceEffectDocumentSha256"):
                self.assertIn(f"{field} = {source_name}.{field} ?? String.Empty", self.source)
        self.assertIn("maskIdentity.sourceFieldsJson == sourceMask.sourceFieldsJson", self.source)
        self.assertIn("maskIdentity.sourceAlphaThreshold == sourceMask.alphaThreshold", self.source)

    def test_empty_renderer_optional_fields_canonicalize_null_but_keep_raw_graphics_hash(self):
        empty = self.block("static ProxyEmptyRendererReadback ReadEmptyRenderer(", "static NativeStaticSortQueueProxyGraphic CreateProxyGraphic(")
        carrier = self.block("static bool TryCreateEmptyRendererCarrier(", "static bool GraphicsMaterialGuidsMatch(")
        self.assertIn("spec.sourceFieldsJson ?? String.Empty", carrier)
        self.assertIn("spec.sourceFieldsSha256 ?? String.Empty", carrier)
        self.assertIn("spec.sourceDrawingCommands ?? String.Empty", carrier)
        self.assertIn("String.Equals(marker.sourceFieldsJson ?? String.Empty, expectedSourceFieldsJson", empty)
        self.assertIn("HashText(expectedSourceFieldsJson) == expectedSourceFieldsSha256", empty)

    def test_inactive_sprite_image_enabled_bit_tracks_exact_source_frame_binding_policy(self):
        empty = self.block("static ProxyEmptyRendererReadback ReadEmptyRenderer(", "static NativeStaticSortQueueProxyGraphic CreateProxyGraphic(")
        carrier = self.block("static bool TryCreateEmptyRendererCarrier(", "static bool GraphicsMaterialGuidsMatch(")
        expected = "source.enabled != (spec.sourceEnabled && spec.sourceTextureBound)"
        self.assertIn(expected, carrier)
        self.assertIn("image.enabled == (spec.sourceEnabled && spec.sourceTextureBound)", empty)
        self.assertIn("(image.sprite != null) == spec.sourceTextureBound", empty)

    def test_rect_transform_capture_path_is_emitted_as_diagnostic_not_acceptance_flag(self):
        create = self.block("static NativeStaticSortQueueProxyGraphic CreateProxyGraphic(",
                            "public static ProxyQueueReadback CreateStaticSortQueueProxy(")
        copy_world = self.block("static void CopyWorldRect(RectTransform source, RectTransform proxy, Transform parent, string sourceId)",
                                "static bool IsGeneratedTextSubmesh(")
        self.assertIn("ProxyRectCopyCaptureDiagnostic", self.source)
        self.assertIn("sourceParentMatrix =", self.source)
        self.assertIn("targetParentMatrix =", self.source)
        self.assertIn("originCorrectionResidual", self.source)
        self.assertIn("CopyWorldRect(rt, proxyRect, parent, sourceComponentId, out var transformCaptureDiagnostic)", create)
        self.assertIn("proxy.transformCaptureDiagnosticJson = transformCaptureDiagnostic", create)
        self.assertIn("transformCaptureDiagnosticJson = proxy.transformCaptureDiagnosticJson", self.source)
        self.assertIn("UnityStaticSortVertexPrecision.TryGetRelativeMatrixFromCommonAncestor", copy_world)
        self.assertLess(copy_world.index("TryGetRelativeMatrixFromCommonAncestor"),
                        copy_world.index("parent.worldToLocalMatrix * source.localToWorldMatrix"))
        self.assertIn('"common-ancestor-trs"', copy_world)
        self.assertIn("sourceLocalToWorldMatrix", self.source)
        self.assertIn("finalProxyLocalToWorldMatrix", self.source)

    def test_spine_source_null_proof_matches_nested_source_plan_field_shape(self):
        self.assertIn("public SpineNullDataFields fields", self.source)
        self.assertIn("public SpineNullDataSourceField skeletonData", self.source)
        self.assertIn("sourceRow.fields.skeletonData.status != \"no_static_source_data_reference\"", self.source)
        self.assertNotIn("sourceRow.skeletonData.status", self.source)
        self.assertIn('if (name != "pmaVertexColors") return TryReadSpineMember(owner, name, out value)', self.source)
        self.assertIn('TryReadSpineMember(generator, "settings", out var settings)', self.source)
        self.assertIn('TryReadSpineMember(settings, "pmaVertexColors", out value)', self.source)

    def test_inactive_spine_owner_without_registered_children_has_typed_asset_no_draw_proof(self):
        capture = self.block("static ProxySpineNonDrawChild[] CaptureSpineNonDrawChildren(",
                             "static bool TryCreateEmptyRendererCarrier(")
        readback = self.block("static ProxySpineNonDrawChildReadback[] ReadSpineNonDrawChildren(",
                              "static ProxyQueueReadback ReadProxy(")
        self.assertIn("if (registered.Count == 0)", capture)
        self.assertIn("ownerInactiveOrDisabled", capture)
        self.assertIn("rootMeshEmpty", capture)
        self.assertIn("rootMaterialCount != 0", capture)
        self.assertIn('"inactive-owner-no-registered-renderers"', capture)
        self.assertIn("ownerOnlyNoRegisteredChildren", readback)
        self.assertIn("ownerOnlyProof.sourceDataAssetReference == dataAsset", readback)
        self.assertIn("ownerOnlyProof.sourceDataAssetGuid == (dataEvidence == null ? null : dataEvidence.dataAssetGuid)", readback)
        self.assertIn("var rootMeshFingerprintsAbsent", self.source)
        self.assertIn("String.IsNullOrEmpty(ownerOnlyProof.ownerRootMeshSha256)", self.source)
        self.assertIn("capturedRootMeshCountsEmpty", self.source)
        self.assertIn("currentRootMeshCountsEmpty", self.source)
        self.assertIn("currentOwnerRootMeshVertexCount = rootMesh == null ? -1 : rootMesh.vertexCount", self.source)
        self.assertIn("registered.Count == 0", readback)
        self.assertIn("noUnmappedChildGraphics", readback)

    def test_null_spine_default_ui_quad_is_recorded_as_suppressed_target_fallback(self):
        quad = self.block("static bool TryProveNullSpineDefaultGraphicQuad(",
                          "static bool SpineSkinRuntimeRepresentationMatches(")
        self.assertIn('owner.GetType().FullName != "Spine.Unity.SkeletonGraphic"', quad)
        self.assertIn("vertices.Length == 4", quad)
        self.assertIn("mesh.subMeshCount == 1", quad)
        self.assertIn("new[] { 0, 1, 2, 2, 3, 0 }", quad)
        self.assertIn("vertices.SequenceEqual(expected)", quad)
        self.assertIn("MeshFingerprint(mesh, 0)", quad)
        self.assertIn("!nullDataOwner.nativeRootMeshEmpty && !nullDataOwner.nativeRootMeshDefaultGraphicQuad", self.source)
        self.assertIn("source-spine-data-reference-absent-no-source-renderable-output", self.source)
        self.assertNotIn("CreateProxyGraphic(sourceGraphic, sourceGraphic", self.source)
        self.assertIn("sourceGraphicSuppressedByPresenter", self.source)
        self.assertIn("nativeRootMeshDefaultGraphicQuad", self.source)

    def test_spine_finalizer_requires_data_or_exact_typed_null_data_no_draw_proof(self):
        self.assertIn("TryReadSpineDataAsset(owner, out var sourceDataAsset)", self.source)
        self.assertIn("activeSpineOwners.Add(owner)", self.source)
        self.assertIn("TryBuildSpineNullDataOwnerProof(spec, row, sourceNode, sourceNodes", self.source)
        self.assertIn("STATIC_SORT_PROXY_SPINE_NULL_DATA_NO_DRAW_NOT_PROVEN_BEFORE_FINALIZE", self.source)
        self.assertIn("if (activeSpineOwners.Count > 0)", self.source)
        self.assertIn("target fallback quad through the Spine mesh finalizer", self.source)

    def test_null_spine_empty_mesh_hash_normalizes_only_absent_hash_identity(self):
        self.assertIn(
            "saved.nativeRootMeshEmpty == actualProof.nativeRootMeshEmpty",
            self.source)
        self.assertIn("actualProof.nativeRootMeshEmpty\n                          ? String.IsNullOrEmpty(saved.rootMeshSha256) && String.IsNullOrEmpty(actualProof.rootMeshSha256)",
                      self.source)
        self.assertIn("String.IsNullOrEmpty(savedNullDataProof.rootMeshSha256) && String.IsNullOrEmpty(currentNullDataProof.rootMeshSha256)", self.source)
        self.assertIn("savedTargetFallbackQuadNotCurrentlyPresent", self.source)
        self.assertIn('Check("rootMeshSha256", savedTargetFallbackQuadNotCurrentlyPresent ||', self.source)
        self.assertIn('savedProofDifferences = savedProofDifferences.ToArray()', self.source)


if __name__ == "__main__":
    unittest.main()
