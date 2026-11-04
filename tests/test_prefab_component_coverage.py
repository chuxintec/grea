import unittest

from monkey.prefab_component_coverage import assess


class ComponentCoverageTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "nodes": [{"sourceId": "node-a", "parent": None, "active": True}],
            "components": [{
                "sourceId": "component-a", "node": "node-a", "type": "cc.Sprite",
                "nativeType": "cc.Sprite", "convertible": True, "enabled": True,
                "spriteFrame": "asset:frame-a",
            }],
            "diagnostics": [],
        }
        self.native = {"components": [{
            "sourceId": "component-a", "type": "cc.Sprite", "componentUuid": "native-uuid-a",
        }]}

    def test_full_source_denominator_keeps_nonconvertible_unsupported_component(self):
        plan = {
            "nodes": self.plan["nodes"],
            "components": [self.plan["components"][0], {
                "sourceId": "unsupported-a", "node": "node-a", "type": "cc.CustomWidget",
                "nativeType": None, "convertible": False, "enabled": True,
            }],
            "diagnostics": [{"code": "COMPONENT_HANDOFF", "sourceId": "unsupported-a", "message": "not in profile"}],
        }
        result = assess(plan, self.native, "creator")
        self.assertEqual(result["sourceComponentCount"], 2)
        self.assertEqual(len(result["components"]), 2)
        row = next(row for row in result["components"] if row["sourceId"] == "unsupported-a")
        self.assertEqual(row["disposition"], "unsupported")
        self.assertEqual(row["sourceDiagnostics"][0]["code"], "COMPONENT_HANDOFF")
        self.assertEqual(result["nativeStaticValidation"], "fail")
        self.assertEqual(result["playerValidation"], "not_run")

    def test_missing_native_component_cannot_pass_from_convertible_source_plan(self):
        result = assess(self.plan, {"components": []}, "creator")
        self.assertEqual(result["components"][0]["disposition"], "missing")
        self.assertEqual(result["nativeStaticValidation"], "fail")
        self.assertTrue(any(row["code"] == "SOURCE_COMPONENT_WITHOUT_NATIVE_DISPOSITION" for row in result["diagnostics"]))

    def test_explicit_native_identity_failure_is_not_overridden_by_uuid(self):
        readback = {"components": [{
            "sourceId": "component-a", "type": "cc.Sprite", "componentUuid": "uuid-present",
            "sourceIdentityVerified": False, "persistent": True,
        }]}
        result = assess(self.plan, readback, "unity")
        self.assertEqual(result["components"][0]["disposition"], "missing")
        self.assertEqual(result["nativeStaticValidation"], "fail")

    def test_retained_only_does_not_promote_native_or_static_presentation(self):
        readback = {"retainedComponents": [{
            "sourceId": "component-a", "status": "verified", "verified": True,
            "sourceIdentityVerified": True, "representation": "opaque-source-evidence",
            "guid": "0123456789abcdef0123456789abcdef", "localFileId": 1, "persistent": True,
        }]}
        result = assess(self.plan, readback, "unity")
        self.assertEqual(result["components"][0]["disposition"], "retained")
        self.assertEqual(result["retentionValidation"], "pass")
        self.assertEqual(result["nativeStaticValidation"], "partial")
        self.assertNotEqual(result["staticPresentationValidation"]["status"], "pass")

    def test_static_fields_need_actual_identity_and_field_readback(self):
        plan = {**self.plan, "components": [{**self.plan["components"][0], "staticFieldBinding": {
            "fields": [{"sourceFieldName": "spriteFrame", "name": "spriteFrame"}],
        }}]}
        result = assess(plan, self.native, "creator")
        self.assertEqual(result["nativeStaticValidation"], "partial")
        readback = {**self.native, "staticFieldBindings": [{
            "sourceId": "component-a", "nativeIdentityVerified": True, "fieldsVerified": True,
            "fields": [{"sourceFieldName": "spriteFrame", "referenceVerified": True}],
        }]}
        result = assess(plan, readback, "creator")
        self.assertEqual(result["components"][0]["staticFieldStatus"], "verified")
        self.assertEqual(result["nativeStaticValidation"], "pass")
        self.assertEqual(result["staticPresentationValidation"]["status"], "partial")

    def test_verified_static_field_carrier_is_disabled_not_native_complete(self):
        plan = {"nodes": self.plan["nodes"], "components": [{
            "sourceId": "script-a", "node": "node-a", "type": "cc.Component",
            "nativeType": None, "convertible": False,
            "staticFieldBinding": {"fields": [{"sourceFieldName": "target", "name": "target"}]},
        }]}
        readback = {"staticFieldBindings": [{
            "sourceId": "script-a", "nativeIdentityVerified": True, "fieldsVerified": True,
            "fields": [{"sourceFieldName": "target", "verified": True}],
        }]}
        result = assess(plan, readback, "creator")
        self.assertEqual(result["components"][0]["disposition"], "disabled")
        self.assertEqual(result["components"][0]["staticFieldStatus"], "verified")
        self.assertEqual(result["nativeStaticValidation"], "partial")
        self.assertEqual(result["retentionValidation"], "not_applicable")

    def test_verified_presentation_requires_native_row_and_rendered_evidence(self):
        readback = {
            **self.native,
            "staticPresentationValidation": {"status": "pass", "components": [{
                "sourceId": "component-a", "sourceVisible": True, "verified": True, "rendered": True,
            }]},
        }
        result = assess(self.plan, readback, "creator")
        self.assertEqual(result["staticPresentationValidation"]["status"], "pass")
        self.assertEqual(result["nativeStaticValidation"], "pass")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["runtimeCheck"], "not_run")

    def test_source_visible_nonrendering_spine_stays_partial_even_if_retained(self):
        plan = {
            "nodes": self.plan["nodes"],
            "components": [{"sourceId": "spine-a", "node": "node-a", "type": "sp.Skeleton",
                            "convertible": False, "enabled": True}],
            "staticSpineContinuation": {"components": [{"sourceComponentId": "spine-a"}]},
        }
        readback = {
            "staticSpineContinuation": {"status": "verified", "sourceComponentIds": ["spine-a"]},
            "retainedComponents": [{"sourceId": "spine-a", "status": "verified", "verified": True,
                                    "sourceIdentityVerified": True, "persistent": True,
                                    "guid": "0123456789abcdef0123456789abcdef", "localFileId": 2,
                                    "representation": "non-rendering-static-spine"}],
        }
        result = assess(plan, readback, "unity")
        row = result["components"][0]
        self.assertEqual(row["disposition"], "retained")
        self.assertEqual(result["retentionValidation"], "pass")
        self.assertEqual(result["nativeStaticValidation"], "partial")
        self.assertEqual(result["staticPresentationValidation"]["status"], "partial")
        self.assertTrue(any(row["code"] == "SOURCE_VISIBLE_SPINE_NOT_RENDERED" for row in result["diagnostics"]))

        incomplete = assess(plan, {}, "unity")
        self.assertEqual(incomplete["retentionValidation"], "not_run")
        self.assertNotEqual(incomplete["nativeStaticValidation"], "pass")

    def test_native_presentation_gap_is_preserved_when_known_visual_rows_pass(self):
        readback = {**self.native, "staticPresentationValidation": {
            "status": "partial", "components": [{
                "sourceId": "component-a", "sourceVisible": True, "verified": True, "rendered": True,
            }, {"sourceId": "unknown-role", "verified": False, "reason": "source-static-role-unproven"}],
        }}
        result = assess(self.plan, readback, "creator")
        self.assertEqual(result["nativeStaticValidation"], "pass")
        self.assertEqual(result["staticPresentationValidation"]["status"], "partial")
        self.assertEqual(result["status"], "partial")
        self.assertIn("STATIC_PRESENTATION_NATIVE_INCOMPLETE", [row["code"] for row in result["diagnostics"]])

    def test_duplicate_or_missing_source_identity_stays_in_denominator(self):
        plan = {"components": [
            {"sourceId": "duplicate", "type": "cc.Sprite", "convertible": True},
            {"sourceId": "duplicate", "type": "cc.Sprite", "convertible": True},
            {"type": "cc.Label", "convertible": False},
        ]}
        result = assess(plan, {"components": []}, "creator")
        self.assertEqual(result["sourceComponentCount"], 3)
        self.assertEqual(len(result["components"]), 3)
        self.assertEqual(sum(result["dispositionCounts"].values()), 3)
        self.assertTrue(any(row["code"] == "SOURCE_COMPONENT_ID_DUPLICATE" for row in result["diagnostics"]))
        self.assertTrue(any(row["code"] == "SOURCE_COMPONENT_ID_MISSING" for row in result["diagnostics"]))

    def test_no_editor_readback_is_not_run_and_never_passes(self):
        result = assess(self.plan, {}, "creator")
        self.assertEqual(result["nativeStaticValidation"], "not_run")
        self.assertEqual(result["staticPresentationValidation"]["status"], "not_run")
        self.assertEqual(result["components"][0]["nativeStatus"], "not_run")
        self.assertEqual(result["playerValidation"], "not_run")

    def test_source_and_raw_native_diagnostics_are_preserved(self):
        plan = {**self.plan, "diagnostics": [{"code": "SOURCE_GAP", "sourceId": "component-a", "message": "original"}]}
        readback = {**self.native, "diagnostics": ["NATIVE_GAP: component-a"]}
        result = assess(plan, readback, "creator")
        self.assertTrue(any(row.get("code") == "SOURCE_GAP" for row in result["sourceDiagnostics"]))
        raw = next(row for row in result["diagnostics"] if row.get("rawDiagnostic"))
        self.assertEqual(raw["rawDiagnostic"], "NATIVE_GAP: component-a")

    def test_creator_full_source_observations_only_accept_actual_uuid_rows(self):
        readback = {"sourceComponentCoverage": [{
            "sourceIndex": 0, "sourceId": "component-a", "sourceType": "cc.Sprite",
            "nativeComponentReadback": [{"sourceId": "component-a", "type": "cc.Sprite",
                                          "nativeType": "cc.Sprite", "componentUuid": "actual-uuid"}],
        }]}
        result = assess(self.plan, readback, "creator")
        self.assertEqual(result["sourceComponentCount"], 1)
        self.assertEqual(result["components"][0]["nativeComponentReadback"]["componentUuid"], "actual-uuid")
        self.assertEqual(result["nativeStaticValidation"], "pass")

        readback["components"] = [{"sourceId": "component-a", "type": "cc.Sprite",
                                   "nativeType": "cc.Sprite", "componentUuid": "actual-uuid"}]
        result = assess(self.plan, readback, "creator")
        self.assertEqual(result["components"][0]["disposition"], "native")

        fabricated = {"sourceComponentCoverage": [{
            "sourceIndex": 0, "sourceId": "component-a", "sourceType": "cc.Sprite",
            "nativeComponentReadback": [{"sourceId": "component-a", "type": "cc.Sprite"}],
        }]}
        result = assess(self.plan, fabricated, "creator")
        self.assertEqual(result["components"][0]["disposition"], "missing")
        self.assertEqual(result["nativeStaticValidation"], "fail")

    def test_creator_prefab_component_rows_fill_full_prefab_coverage(self):
        readback = {"components": [], "sourcePrefabs": [{"components": [{
            "sourceId": "component-a", "type": "cc.Sprite", "nativeType": "cc.Sprite",
            "componentUuid": "prefab-native-uuid",
        }]}]}
        result = assess(self.plan, readback, "creator")
        self.assertEqual(result["components"][0]["disposition"], "native")

    def test_explicit_source_empty_sprite_is_business_disabled_not_missing(self):
        plan={"nodes":self.plan["nodes"],"components":[{
            "sourceId":"sprite-empty","node":"node-a","type":"cc.Sprite","enabled":True,
            "spriteFrame":None,"nativeType":"cc.Sprite","convertible":True,
        }]}
        row={"sourceId":"sprite-empty","status":"disabled","representation":"native-component",
             "nativeType":"UnityEngine.UI.Image","sourceEnabled":True,"nativeEnabled":False,
             "disabledReason":"source-empty-sprite","nativeStaticFieldsVerified":True,
             "sourceIdentityVerified":True,"persistent":True,
             "guid":"0123456789abcdef0123456789abcdef","localFileId":7}
        result=assess(plan,{"components":[row]},"unity")
        self.assertEqual(result["components"][0]["disposition"],"disabled")
        self.assertEqual(result["components"][0]["nativeStatus"],"pass")
        self.assertFalse(result["components"][0]["sourceVisible"])
        self.assertNotEqual(result["nativeStaticValidation"],"fail")

    def test_empty_sprite_requires_explicit_source_field_and_native_null_proof(self):
        from monkey.prefab_component_coverage import _valid_native_disabled
        component={"sourceId":"s","type":"cc.Sprite","enabled":True,"spriteFrame":None}
        row={"sourceId":"s","status":"disabled","representation":"native-component",
             "nativeType":"UnityEngine.UI.Image","sourceEnabled":True,"nativeEnabled":False,
             "disabledReason":"source-empty-sprite","nativeStaticFieldsVerified":True,
             "sourceIdentityVerified":True,"persistent":True,
             "guid":"0123456789abcdef0123456789abcdef","localFileId":7}
        self.assertTrue(_valid_native_disabled(component,row,"unity")[0])
        unknown_source={"sourceId":"s","type":"cc.Sprite","enabled":True}
        self.assertTrue(_valid_native_disabled(unknown_source,row,"unity")[0])
        self.assertIsNone(_valid_native_disabled(unknown_source,row,"unity")[1])
        row["nativeStaticFieldsVerified"]=False
        self.assertTrue(_valid_native_disabled(component,row,"unity")[0])
        result=assess({"nodes":self.plan["nodes"],"components":[{
            "sourceId":"s","node":"node-a","type":"cc.Sprite","enabled":True,
            "spriteFrame":None}]},{"components":[row]},"unity")
        self.assertEqual(result["components"][0]["disposition"],"disabled")
        self.assertEqual(result["components"][0]["nativeStatus"],"partial")

    def test_native_disabled_button_requires_exact_business_safe_profile(self):
        plan={"nodes":self.plan["nodes"],"components":[{
            "sourceId":"button","node":"node-a","type":"cc.Button","enabled":True,
            "staticButtonBinding":{"behavior":"disabled","renderReady":True,"sourceEnabled":True},
        }]}
        row={"sourceId":"button","status":"disabled","representation":"native-component",
             "nativeType":"UnityEngine.UI.Button","sourceEnabled":True,"nativeEnabled":False,
             "disabledReason":"static-button-business-safety","nativeStaticFieldsVerified":True,
             "sourceIdentityVerified":True,"persistent":True,
             "guid":"0123456789abcdef0123456789abcdef","localFileId":8}
        result=assess(plan,{"components":[row]},"unity")
        self.assertEqual(result["components"][0]["disposition"],"disabled")
        self.assertEqual(result["components"][0]["nativeStatus"],"pass")
        self.assertEqual(result["components"][0]["sourceBehaviorStatus"],"disabled_for_business_safety_behavior_not_restored")
        row["disabledReason"]="unproven-native-disabled"
        result=assess(plan,{"components":[row]},"unity")
        self.assertEqual(result["components"][0]["disposition"],"disabled")
        self.assertEqual(result["components"][0]["nativeStatus"],"partial")
        self.assertTrue(any(item["code"]=="NATIVE_DISABLED_REASON_UNPROVEN" for item in result["diagnostics"]))

    def test_unity_identity_accepts_signed64_edges_and_rejects_invalid_pairs(self):
        from monkey.prefab_component_coverage import _unity_persistent_identity
        guid="0123456789abcdef0123456789abcdef"
        for local in (-(1<<63),(1<<63)-1):
            self.assertIsNotNone(_unity_persistent_identity({"guid":guid,"localFileId":local}))
        for local in (0,1<<63,-(1<<63)-1,True,"01"):
            self.assertIsNone(_unity_persistent_identity({"guid":guid,"localFileId":local}))
        self.assertIsNone(_unity_persistent_identity({"guid":"bad","localFileId":1}))
        self.assertIsNone(_unity_persistent_identity({"guid":guid,"localFileId":1,"componentUuid":guid+":2"}))

    def test_static_progress_retention_joins_source_id_values_and_bar_sprite(self):
        from monkey.unity_verification_contract import coverage_readback
        binding={"sourceComponentId":"progress","sourceEnabled":True,"mode":0,"progress":0.5,
                 "reverse":False,"barSpriteSourceId":"bar-sprite"}
        plan={"components":[{"sourceId":"progress","type":"cc.ProgressBar","enabled":True,
                             "staticProgressBinding":binding}]}
        row={"sourceComponentId":"progress","verified":True,"carrierDisabled":True,
             "carrierGuid":"0123456789abcdef0123456789abcdef","carrierLocalFileId":12,
             "sourceEnabled":True,"mode":0,"progress":0.5,"reverse":False,
             "barSpriteSourceId":"bar-sprite","barSpritePersistent":True,
             "barSpriteGuid":"fedcba9876543210fedcba9876543210","barSpriteLocalFileId":13}
        normalized=coverage_readback({"staticProgressFields":[row],"components":[{
            "sourceId":"bar-sprite","status":"native","representation":"native-component",
            "nativeType":"UnityEngine.UI.Image","sourceIdentityVerified":True,"persistent":True,
            "guid":"fedcba9876543210fedcba9876543210","localFileId":13,
        }]})
        result=assess(plan,normalized,"unity")
        self.assertEqual(result["components"][0]["disposition"],"retained")
        self.assertEqual(result["retentionValidation"],"pass")
        row["barSpriteSourceId"]="other-sprite"
        result=assess(plan,coverage_readback({"staticProgressFields":[row]}),"unity")
        self.assertEqual(result["components"][0]["disposition"],"missing")
        self.assertEqual(result["retentionValidation"],"partial")

    def test_progress_single_precision_is_exact_and_creator_numbers_remain_strict(self):
        import struct
        from monkey.prefab_component_coverage import _progress_number_matches
        value=struct.unpack('!f',struct.pack('!f',.9))[0]
        self.assertTrue(_progress_number_matches(value,.9,'unity'))
        self.assertFalse(_progress_number_matches(.9000001,.9,'unity'))
        self.assertFalse(_progress_number_matches(float('nan'),.9,'unity'))
        self.assertFalse(_progress_number_matches(True,1,'unity'))
        self.assertFalse(_progress_number_matches(value,.9,'creator'))

    def test_native_slider_profile_needs_native_fields_not_a_fabricated_extra_carrier(self):
        sid='progress';guid='a'*32
        plan={'nodes':[{'sourceId':'node','active':True}], 'components':[dict(sourceId=sid,
            node='node',type='cc.ProgressBar',enabled=True,convertible=True,
            staticProgressBinding=dict(policy='native-static-progress-v1',sourceEnabled=True,
                mode=0,progress=.6,reverse=False,barSpriteSourceId='bar'))]}
        native=dict(sourceId=sid,status='native',representation='native-component',
            nativeType='UnityEngine.UI.Slider',guid=guid,localFileId=1,persistent=True,
            sourceIdentityVerified=True,nativeStaticFieldsVerified=True,nativeEnabled=True,sourceEnabled=True)
        result=assess(plan,{'components':[native]},'unity')
        self.assertEqual(result['sourceComponentCount'],1)
        self.assertEqual(result['components'][0]['disposition'],'native')
        self.assertFalse(any(d['code']=='STATIC_RETENTION_READBACK_INCOMPLETE' for d in result['diagnostics']))
        native['nativeStaticFieldsVerified']=False
        self.assertNotEqual(assess(plan,{'components':[native]},'unity')['nativeStaticValidation'],'pass')
        native['nativeStaticFieldsVerified']=True
        plan['staticComponentRetentions']=[{'sourceComponentId':sid}]
        declared=assess(plan,{'components':[native]},'unity')
        self.assertTrue(any(d['code']=='STATIC_RETENTION_READBACK_INCOMPLETE' for d in declared['diagnostics']))

    def test_spine_renderer_does_not_skip_retained_carrier_verification(self):
        sid="spine-source"
        guid="0123456789abcdef0123456789abcdef"
        plan={"nodes":self.plan["nodes"],"components":[{
            "sourceId":sid,"node":"node-a","type":"sp.Skeleton","enabled":True}],
            "staticSpineContinuation":{"components":[{"sourceComponentId":sid}]}}
        readback={"staticSpineContinuation":{"status":"verified","sourceComponentIds":[sid]},
            "staticSpineRendering":{"status":"verified","sourceComponentIds":[sid]},
            "components":[{"sourceId":sid,"status":"native","representation":"native-component",
                "coverageRole":"native-renderer",
                "nativeType":"Spine.Unity.SkeletonGraphic","nativeStaticFieldsVerified":True,
                "nativeEnabled":True,
                "sourceIdentityVerified":True,"persistent":True,"guid":guid,"localFileId":20}],
            "retainedComponents":[{"sourceId":sid,"status":"verified","verified":True,
                "coverageRole":"retained-carrier","sourceIdentityVerified":True,"persistent":True,
                "guid":"fedcba9876543210fedcba9876543210","localFileId":21,
                "nativeType":"NativeStaticSpineReference","representation":"disabled-source-data-carrier"}]}
        result=assess(plan,readback,"unity")
        self.assertEqual(result["components"][0]["disposition"],"native")
        self.assertEqual(result["retentionValidation"],"pass")
        self.assertEqual(result["staticPresentationValidation"]["status"],"pass")
        self.assertEqual(result["components"][0]["nativeComponentReadback"]["localFileId"],20)
        self.assertEqual(result["components"][0]["retainedComponentReadback"]["localFileId"],21)
        readback["retainedComponents"][0]["guid"]="bad"
        result=assess(plan,readback,"unity")
        self.assertEqual(result["retentionValidation"],"partial")

    def test_spine_carrier_and_renderer_roles_join_across_top_and_prefab_scopes(self):
        sid="spine-role-source"
        carrier={"sourceId":sid,"node":"node-a","type":"sp.Skeleton","nativeType":"NativeStaticSpineReference",
                 "status":"retained","representation":"disabled-source-data-carrier","coverageRole":"retained-carrier",
                 "guid":"0123456789abcdef0123456789abcdef","localFileId":30,"componentUuid":"0123456789abcdef0123456789abcdef:30",
                 "sourceIdentityVerified":True,"persistent":True,"verified":True,"fieldsVerified":True,
                 "sourceEnabled":True,"nativeEnabled":False}
        renderer={"sourceId":sid,"node":"node-a","type":"sp.Skeleton","nativeType":"Spine.Unity.SkeletonGraphic",
                  "status":"native","representation":"native-component","coverageRole":"native-renderer",
                  "guid":"fedcba9876543210fedcba9876543210","localFileId":31,
                  "componentUuid":"fedcba9876543210fedcba9876543210:31","sourceIdentityVerified":True,
                  "persistent":True,"nativeStaticFieldsVerified":True,"sourceEnabled":True,"nativeEnabled":True}
        plan={"nodes":self.plan["nodes"],"components":[{"sourceId":sid,"node":"node-a","type":"sp.Skeleton","enabled":True}],
              "staticSpineContinuation":{"components":[{"sourceComponentId":sid}]}}
        raw_copy={key:value for key,value in carrier.items() if key!="coverageRole"}
        readback={"components":[dict(carrier),dict(renderer)],"sourcePrefabs":[{"components":[raw_copy]}],
                  "staticSpineContinuation":{"status":"verified","sourceComponentIds":[sid]},
                  "staticSpineRendering":{"status":"verified","sourceComponentIds":[sid]}}
        result=assess(plan,readback,"unity")
        self.assertEqual(result["components"][0]["disposition"],"native")
        self.assertEqual(result["retentionValidation"],"pass")
        self.assertEqual(result["staticPresentationValidation"]["status"],"pass")
        self.assertFalse(any(row["code"] in ("NATIVE_COMPONENT_READBACK_AMBIGUOUS","NATIVE_COMPONENT_IDENTITY_MISMATCH",
                                             "STATIC_RETENTION_READBACK_AMBIGUOUS") for row in result["diagnostics"]))

    def test_same_role_renderer_duplicates_are_still_ambiguous(self):
        sid="spine-role-duplicate"
        renderer={"sourceId":sid,"status":"native","representation":"native-component","coverageRole":"native-renderer",
                  "nativeType":"Spine.Unity.SkeletonGraphic","sourceIdentityVerified":True,"persistent":True,
                  "nativeStaticFieldsVerified":True,"nativeEnabled":True,"sourceEnabled":True,
                  "guid":"0123456789abcdef0123456789abcdef","localFileId":40}
        duplicate=dict(renderer, guid="fedcba9876543210fedcba9876543210", localFileId=41)
        plan={"nodes":self.plan["nodes"],"components":[{"sourceId":sid,"node":"node-a","type":"sp.Skeleton","enabled":True}],
              "staticSpineContinuation":{"components":[{"sourceComponentId":sid}]}}
        readback={"components":[renderer,duplicate],"staticSpineRendering":{"status":"verified","sourceComponentIds":[sid]}}
        result=assess(plan,readback,"unity")
        self.assertEqual(result["components"][0]["disposition"],"missing")
        self.assertTrue(any(row["code"]=="NATIVE_COMPONENT_READBACK_AMBIGUOUS" for row in result["diagnostics"]))

    def test_same_role_retained_duplicates_still_fail_retention(self):
        sid="spine-retained-duplicate"
        carrier={"sourceId":sid,"status":"retained","coverageRole":"retained-carrier",
                 "nativeType":"NativeStaticSpineReference","representation":"disabled-source-data-carrier",
                 "sourceIdentityVerified":True,"persistent":True,"verified":True,"fieldsVerified":True,
                 "guid":"0123456789abcdef0123456789abcdef","localFileId":50}
        plan={"nodes":self.plan["nodes"],"components":[{"sourceId":sid,"node":"node-a","type":"sp.Skeleton","enabled":True}],
              "staticSpineContinuation":{"components":[{"sourceComponentId":sid}]}}
        readback={"retainedComponents":[dict(carrier),dict(carrier)],
                  "staticSpineContinuation":{"status":"verified","sourceComponentIds":[sid]}}
        result=assess(plan,readback,"unity")
        self.assertEqual(result["retentionValidation"],"partial")
        self.assertTrue(any(row["code"]=="STATIC_RETENTION_READBACK_AMBIGUOUS" for row in result["diagnostics"]))

    def test_normalized_peer_duplicate_survives_pipeline_and_fails_native_role(self):
        from monkey.unity_verification_contract import coverage_readback
        sid="spine-normalized-peer-duplicate"
        renderer={"sourceId":sid,"status":"native","representation":"native-component",
                  "coverageRole":"native-renderer","nativeType":"Spine.Unity.SkeletonGraphic",
                  "sourceIdentityVerified":True,"persistent":True,"nativeStaticFieldsVerified":True,
                  "nativeEnabled":True,"sourceEnabled":True,
                  "guid":"0123456789abcdef0123456789abcdef","localFileId":60}
        plan={"nodes":self.plan["nodes"],"components":[{"sourceId":sid,"node":"node-a","type":"sp.Skeleton","enabled":True}],
              "staticSpineContinuation":{"components":[{"sourceComponentId":sid}]}}
        normalized=coverage_readback({"components":[dict(renderer),dict(renderer)]},
                                     {"status":"verified","sourceComponentIds":[sid]})
        self.assertTrue(any(item.get("sourceId")==sid and item.get("coverageRole")=="native-renderer"
                            for item in normalized.get("componentPeerDuplicates",[])))
        normalized["staticSpineRendering"]={"status":"verified","sourceComponentIds":[sid]}
        result=assess(plan,normalized,"unity")
        self.assertEqual(result["components"][0]["disposition"],"missing")
        self.assertTrue(any(row["code"]=="NATIVE_COMPONENT_READBACK_AMBIGUOUS" and row.get("sourceId")==sid
                            for row in result["diagnostics"]))

    def test_unsupported_readback_status_is_not_misreported_as_native_identity_mismatch(self):
        row={"sourceId":"component-a","status":"unsupported","representation":"unsupported",
             "coverageRole":"unsupported-component","nativeType":None}
        result=assess(self.plan,{"components":[row]},"unity")
        self.assertEqual(result["components"][0]["disposition"],"unsupported")
        self.assertFalse(any(item["code"]=="NATIVE_COMPONENT_IDENTITY_MISMATCH" for item in result["diagnostics"]))

    def test_role_tag_cannot_promote_a_physical_carrier_to_native_renderer(self):
        sid="spine-role-spoof"
        carrier={"sourceId":sid,"status":"retained","representation":"disabled-source-data-carrier",
                 "coverageRole":"native-renderer","nativeType":"NativeStaticSpineReference",
                 "sourceIdentityVerified":True,"persistent":True,"verified":True,"fieldsVerified":True,
                 "guid":"0123456789abcdef0123456789abcdef","localFileId":70}
        plan={"components":[{"sourceId":sid,"type":"sp.Skeleton","enabled":True}],
              "staticSpineContinuation":{"components":[{"sourceComponentId":sid}]}}
        result=assess(plan,{"components":[carrier]},"unity")
        self.assertTrue(any(item["code"]=="COMPONENT_ROLE_MISMATCH" for item in result["diagnostics"]))
        self.assertNotEqual(result["components"][0]["disposition"],"native")

    def test_source_disabled_spine_renderer_keeps_renderer_role_and_disabled_state(self):
        sid="spine-disabled-renderer"
        plan={"nodes":self.plan["nodes"],"components":[{"sourceId":sid,"node":"node-a",
            "type":"sp.Skeleton","enabled":False}],
            "staticSpineContinuation":{"components":[{"sourceComponentId":sid}]}}
        row={"sourceId":sid,"status":"disabled","representation":"native-component",
             "coverageRole":"native-renderer","nativeType":"Spine.Unity.SkeletonGraphic",
             "sourceIdentityVerified":True,"persistent":True,"nativeStaticFieldsVerified":True,
             "sourceEnabled":False,"nativeEnabled":False,"disabledReason":"source-disabled",
             "sourceVisible":False,"guid":"0123456789abcdef0123456789abcdef","localFileId":71}
        result=assess(plan,{"disabledComponents":[row]},"unity")
        self.assertEqual(result["components"][0]["disposition"],"disabled")
        self.assertEqual(result["components"][0]["nativeStatus"],"pass")
        self.assertFalse(any(item["code"]=="COMPONENT_ROLE_MISMATCH" for item in result["diagnostics"]))

    def test_spine_self_report_unknown_ids_cannot_verify_static_render(self):
        sid="spine-source";guid="0123456789abcdef0123456789abcdef"
        plan={"nodes":self.plan["nodes"],"components":[{
            "sourceId":sid,"node":"node-a","type":"sp.Skeleton","enabled":True}],
            "staticSpineContinuation":{"components":[{"sourceComponentId":sid}]}}
        readback={"staticSpineRendering":{"status":"verified","sourceComponentIds":["invented"]},
            "components":[{"sourceId":sid,"status":"native","representation":"native-component",
                "nativeType":"Spine.Unity.SkeletonGraphic","nativeStaticFieldsVerified":True,
                "nativeEnabled":True,
                "sourceIdentityVerified":True,"persistent":True,"guid":guid,"localFileId":20}]}
        result=assess(plan,readback,"unity")
        self.assertEqual(result["staticPresentationValidation"]["status"],"partial")
        self.assertTrue(any(row["code"]=="STATIC_SPINE_RENDERING_ID_UNKNOWN" for row in result["diagnostics"]))


    def test_layout_slot_requires_source_binding_exact_slot_and_static_field_proof(self):
        source = "layout:asset#0/components/0"
        binding = {"contract": "monkey-static-layout-continuation/1",
                   "sourceComponentId": source, "sourceNodeId": "layout:asset#0",
                   "physicalNativeType": "NativeStaticLayoutCompletion"}
        plan = {"nodes": [{"sourceId": "layout:asset#0", "parent": None, "active": True}],
                "components": [{"sourceId": source, "node": "layout:asset#0", "type": "cc.Layout",
                    "nativeType": "NativeStaticLayoutCompletion", "convertible": False,
                    "enabled": True, "staticLayoutContinuationBinding": binding}],
                "diagnostics": [{"code": "COMPONENT_NOT_IMPORTED", "sourceId": source,
                                 "message": "early native creation diagnostic"}]}
        slot = {"sourceId": source, "type": "cc.Layout", "nativeType": "NativeStaticLayoutCompletion",
                "status": "native", "sourceEnabled": True, "representation": "native-component-slot", "nativeSlotId": source,
                "guid": "0123456789abcdef0123456789abcdef", "localFileId": 81,
                "persistent": True, "sourceIdentityVerified": True, "nativeStaticFieldsVerified": True}
        result = assess(plan, {"components": [slot]}, "unity")
        covered = result["components"][0]
        self.assertEqual(covered["nativeStatus"], "pass")
        self.assertEqual(covered["nativeComponentReadback"]["representation"], "native-component-slot")
        self.assertEqual(covered["nativeComponentReadback"]["nativeSlotId"], source)
        self.assertEqual(covered["nativeSlotId"], source)
        self.assertTrue(next(d for d in result["diagnostics"] if d["code"] == "COMPONENT_NOT_IMPORTED")["resolved"])

        bad_slot = dict(slot, nativeSlotId="layout:other#0/components/0")
        result = assess(plan, {"components": [bad_slot]}, "unity")
        self.assertNotEqual(result["components"][0]["nativeStatus"], "pass")
        self.assertFalse(next(d for d in result["diagnostics"] if d["code"] == "COMPONENT_NOT_IMPORTED")["resolved"])

        unverified = dict(slot, nativeStaticFieldsVerified=False)
        result = assess(plan, {"components": [unverified]}, "unity")
        self.assertNotEqual(result["components"][0]["nativeStatus"], "pass")

    def test_disabled_sort_driver_requires_binding_and_whole_queue_driver_evidence(self):
        source = "sort:asset#0/components/0"
        marker = "Monkey.StaticSortQueueProxy.NativeStaticSortOrderIdentity"
        binding = {"contract": "monkey-static-sort-continuation/1", "sourceComponentId": source,
                   "expectedMarkerType": marker}
        plan = {"nodes": [{"sourceId": "sort:asset#0", "parent": None, "active": True}],
                "components": [{"sourceId": source, "node": "sort:asset#0", "type": "cc.SortOrder",
                    "nativeType": marker, "convertible": False, "enabled": True,
                    "staticSortContinuationBinding": binding}], "diagnostics": []}
        row = {"sourceId": source, "nativeType": marker, "status": "disabled",
               "representation": "native-component", "guid": "0123456789abcdef0123456789abcdef",
               "localFileId": 91, "persistent": True, "sourceIdentityVerified": True,
               "sourceEnabled": True, "nativeEnabled": False,
               "disabledReason": "native-static-sort-driver", "nativeStaticFieldsVerified": True,
               "queueDriverGuid": "abcdef0123456789abcdef0123456789", "queueDriverLocalFileId": 92,
               "queueDriverPersistent": True, "queueProofVerified": True}
        result = assess(plan, {"disabledComponents": [row]}, "unity")
        self.assertEqual(result["components"][0]["disposition"], "disabled")
        self.assertEqual(result["components"][0]["nativeStatus"], "pass")
        self.assertEqual(result["components"][0]["disabledReason"], "native-static-sort-driver")

        for mutant in ({"queueProofVerified": False}, {"queueDriverPersistent": False},
                       {"queueDriverLocalFileId": 0}, {"queueDriverGuid": "not-a-guid"}, {"sourceEnabled": False}):
            bad = dict(row, **mutant)
            result = assess(plan, {"disabledComponents": [bad]}, "unity")
            self.assertNotEqual(result["components"][0]["nativeStatus"], "pass")


if __name__ == "__main__":
    unittest.main()
