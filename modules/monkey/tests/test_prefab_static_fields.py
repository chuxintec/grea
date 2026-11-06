import unittest
import math

from monkey.prefab_static_fields import StaticFieldError, extract_static_fields


class PrefabStaticFieldsTests(unittest.TestCase):
    def sample(self, renamed=False):
        asset_id = "bundle:renamed-prefab" if renamed else "bundle:prefab-a"
        resource_id = "bundle:renamed-texture" if renamed else "bundle:texture-a"
        custom_type = "renamed.Script" if renamed else "example.Panel"
        manifest = {"assets": [
            {"sourceId": asset_id, "kind": "cc.Prefab", "bundle": "bundle", "document": {"instances": [
                {"__type__": "cc.Prefab", "data": {"__id__": 1}},
                {"__type__": "cc.Node", "_name": "Source Name", "_components": [{"__id__": 2},
                    {"__type__": custom_type, "node": {"__id__": 1}, "renamedInline": True}], "_children": []},
                {"__type__": "Engine.Helper", "node": {"__id__": 1}, "link": {"__id__": 1}},
                {"__type__": "cc.PrefabInfo", "target": {"__id__": 1}},
            ]}},
            {"sourceId": resource_id, "kind": "cc.Texture2D", "bundle": "bundle"},
        ]}
        inline_id = f"{asset_id}#1/components/1"
        direct_id = f"{asset_id}#2"
        ir = {"nodes": [{"sourceId": f"{asset_id}#1"}], "components": [
            {"sourceId": direct_id, "type": "Engine.Helper", "node": f"{asset_id}#1"},
            {"sourceId": inline_id, "type": custom_type, "node": f"{asset_id}#1"},
        ]}
        return manifest, ir, asset_id, resource_id, direct_id, inline_id

    def test_preserves_inline_fields_and_exact_reference_kinds(self):
        manifest, ir, asset_id, resource_id, direct_id, inline_id = self.sample()
        instances = manifest["assets"][0]["document"]["instances"]
        instances[2].update({
            "enabledFlag": True, "ratio": 1.25, "caption": "hello", "nothing": None,
            "mixed": [None, False, 2, {"nested": "ok"}],
            "nodeLink": {"__id__": 1}, "componentLink": {"__id__": 2},
            "prefabLink": {"__id__": 0}, "unmappedEngineObject": {"__id__": 3},
            "texture": {"__uuid__": "texture-a"},
        })
        report = extract_static_fields(manifest, ir)
        self.assertEqual(report["schemaVersion"], 1)
        self.assertEqual([row["sourceId"] for row in report["components"]], sorted([direct_id, inline_id]))
        direct = next(row for row in report["components"] if row["sourceId"] == direct_id)
        values = {field["name"]: (field["kind"], field["value"]) for field in direct["fields"]}
        self.assertEqual(values["enabledFlag"], ("bool", True))
        self.assertEqual(values["ratio"], ("float", 1.25))
        self.assertEqual(values["caption"], ("string", "hello"))
        self.assertEqual(values["nothing"], ("null", None))
        self.assertEqual(values["nodeLink"], ("node_ref", f"{asset_id}#1"))
        self.assertEqual(values["componentLink"], ("component_ref", f"{asset_id}#2"))
        self.assertEqual(values["prefabLink"], ("asset_ref", asset_id))
        self.assertEqual(values["unmappedEngineObject"][0], "unresolved_ref")
        self.assertEqual(values["texture"], ("asset_ref", resource_id))
        self.assertEqual(values["mixed"][0], "array")
        self.assertEqual(direct["behavior"], "disabled")
        self.assertEqual(direct["gaps"], ["source_declaration_defaults_not_verified"])
        self.assertNotIn("node", {field["name"] for field in direct["fields"]})

    def test_renamed_component_and_uuid_use_source_identity_not_name(self):
        manifest, ir, _asset, _resource, _direct, _inline = self.sample(renamed=True)
        report = extract_static_fields(manifest, ir)
        self.assertEqual(len(report["components"]), 2)
        self.assertEqual(next(row for row in report["components"] if row["sourceId"].endswith("/components/1"))["sourceType"], "renamed.Script")
        instances = manifest["assets"][0]["document"]["instances"]
        instances[2]["resource"] = {"__uuid__": "renamed-texture"}
        updated = extract_static_fields(manifest, ir)
        direct = next(row for row in updated["components"] if row["sourceId"].endswith("#2"))
        self.assertIn({"name": "resource", "kind": "asset_ref", "value": "bundle:renamed-texture"}, direct["fields"])
        self.assertEqual(report["diagnostics"], [])

    def test_invalid_object_and_ambiguous_uuid_are_unresolved(self):
        manifest, ir, _asset, _resource, _direct, _inline = self.sample()
        instances = manifest["assets"][0]["document"]["instances"]
        instances[2].update({"badObject": {"__id__": 99}, "badUuid": {"__uuid__": "missing"}})
        manifest["assets"].append({"sourceId": "other:prefab-a", "kind": "Texture", "bundle": "other"})
        report = extract_static_fields(manifest, ir)
        direct = next(row for row in report["components"] if row["sourceId"].endswith("#2"))
        fields = {field["name"]: field for field in direct["fields"]}
        self.assertEqual(fields["badObject"]["kind"], "unresolved_ref")
        self.assertEqual(fields["badObject"]["value"], {"__id__": 99})
        self.assertEqual(fields["badUuid"]["kind"], "unresolved_ref")
        self.assertEqual(len(report["diagnostics"]), 2)

    def test_cyclic_values_and_duplicate_source_component_id_are_rejected(self):
        manifest, ir, _asset, _resource, _direct, _inline = self.sample()
        cyclic = []
        cyclic.append(cyclic)
        manifest["assets"][0]["document"]["instances"][2]["loop"] = cyclic
        with self.assertRaises(StaticFieldError):
            extract_static_fields(manifest, ir)

    def test_non_finite_numbers_are_rejected(self):
        manifest, ir, *_ = self.sample()
        manifest["assets"][0]["document"]["instances"][2]["notFinite"] = math.nan
        with self.assertRaises(StaticFieldError):
            extract_static_fields(manifest, ir)
        manifest, ir, *_ = self.sample()
        ir["components"].append(dict(ir["components"][0]))
        with self.assertRaises(StaticFieldError):
            extract_static_fields(manifest, ir)

    def test_reference_with_extra_payload_is_rejected(self):
        manifest, ir, *_ = self.sample()
        manifest["assets"][0]["document"]["instances"][2]["ref"] = {"__id__": 1, "name": "lost?"}
        with self.assertRaises(StaticFieldError):
            extract_static_fields(manifest, ir)

    def test_missing_ir_component_is_diagnostic_and_never_empty_match(self):
        manifest, ir, _asset, _resource, _direct, inline_id = self.sample()
        ir["components"] = [row for row in ir["components"] if row["sourceId"] != inline_id]
        report = extract_static_fields(manifest, ir)
        self.assertEqual([row["sourceId"] for row in report["components"]], [_direct])
        self.assertFalse(any(row["sourceId"] == inline_id for row in report["components"]))
        self.assertEqual(report["diagnostics"], [{"code": "IR_COMPONENT_MISSING", "sourceId": inline_id,
                                                   "message": "serialized custom component in selected asset has no matching IR identity"}])

    def test_invalid_ir_node_and_component_source_type_are_rejected(self):
        manifest, ir, *_ = self.sample()
        ir["nodes"][0]["sourceId"] = "bad-owner"
        with self.assertRaises(StaticFieldError):
            extract_static_fields(manifest, ir)
        manifest, ir, *_ = self.sample()
        ir["components"][0]["type"] = None
        with self.assertRaises(StaticFieldError):
            extract_static_fields(manifest, ir)


class RedirectStaticFieldsTests(unittest.TestCase):
    sample=PrefabStaticFieldsTests.sample
    def test_explicit_redirect_chain_resolves_actual_native_asset_identity(self):
        manifest,ir,*_=self.sample()
        manifest['assets'][0]['document']['instances'][2]['icon']={'__uuid__':'texture-a'}
        manifest['assets'][1].update(kind='redirect',redirectTarget='shared:texture-a')
        manifest['assets'].append({'sourceId':'shared:texture-a','bundle':'shared','kind':'cc.SpriteFrame'})
        result=extract_static_fields(manifest,ir)
        field=next(f for c in result['components']for f in c['fields']if f['name']=='icon')
        self.assertEqual(field['value'],'shared:texture-a')
        self.assertEqual(result['assetRedirects'],[{'sourceId':'bundle:texture-a','target':'shared:texture-a'}])

    def test_broken_or_cyclic_owner_redirect_does_not_guess_another_bundle(self):
        for target in ['missing:texture-a','bundle:texture-a']:
            manifest,ir,*_=self.sample()
            manifest['assets'][0]['document']['instances'][2]['icon']={'__uuid__':'texture-a'}
            manifest['assets'][1].update(kind='redirect',redirectTarget=target)
            manifest['assets'].append({'sourceId':'other:texture-a','bundle':'other','kind':'cc.SpriteFrame'})
            result=extract_static_fields(manifest,ir)
            field=next(f for c in result['components']for f in c['fields']if f['name']=='icon')
            self.assertEqual(field['kind'],'unresolved_ref')

if __name__ == "__main__":
    unittest.main()
