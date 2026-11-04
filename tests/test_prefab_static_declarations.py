import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_static_declarations import extract_declarations


def rf_module(rf_id="neutral-rf-01", class_name="RenamedWidget", constructor_body=""):
    return f'''cc._RF.push({{exports:{{}}}}, "{rf_id}", "{class_name}");
(function (Base) {{
  function {class_name}() {{ {constructor_body} }}
  inherit({class_name}, Base);
  decorate([property(cc.Number)], {class_name}.prototype, "count", void 0);
  decorate([property()], {class_name}.prototype, "caption", void 0);
  decorate([property()], {class_name}.prototype, "values", void 0);
  decorate([property()], {class_name}.prototype, "enabled", void 0);
  decorate([property()], {class_name}.prototype, "visible", void 0);
  decorate([property()], {class_name}.prototype, "safe", void 0);
  decorate([property()], {class_name}.prototype, "dynamicValue", void 0);
  decorate([property()], {class_name}.prototype, "flag", void 0);
  decorate([property()], {class_name}.prototype, "inherited", void 0);
  decorate([property()], {class_name}.prototype, "shared", void 0);
  decorate([property()], {class_name}.prototype, "own", void 0);
  decorate([property()], {class_name}.prototype, "mode", void 0);
  decorate([property()], {class_name}.prototype, "unknown", void 0);
  {class_name}.prototype.setCount = function (value) {{ this.count = value; }};
}})(BaseClass);
cc._RF.pop();
'''


class PrefabStaticDeclarationsTests(unittest.TestCase):
    def run_source(self, source, rf_ids):
        raw = source.encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game.js"
            path.write_bytes(raw)
            return extract_declarations(path, hashlib.sha256(raw).hexdigest(), rf_ids)

    def test_renamed_module_extracts_changed_constant_and_typed_decorator(self):
        source = rf_module(
            constructor_body='''var self = Base.apply(this, arguments) || this;
            return self.count = -23, self.caption = "changed default", self.values = [true, null, { depth: 4 }], self;'''
        )
        result = self.run_source(source, ["neutral-rf-01"])
        component = result["components"]["neutral-rf-01"]
        self.assertEqual([field["name"] for field in component["fields"]], ["count", "caption", "values"])
        self.assertEqual(component["fields"][0]["value"], -23)
        self.assertEqual(component["fields"][1]["value"], "changed default")
        self.assertEqual(component["fields"][2]["value"], [True, None, {"depth": 4}])
        self.assertTrue(all(field["owner"] == "RenamedWidget" for field in component["fields"]))
        self.assertEqual(component["propertyTypes"], [{"name": "count", "types": ["cc.Number"]}])
        self.assertTrue(any(gap["kind"] == "base_class_unresolved" for gap in component["gaps"]))
        self.assertEqual(result["diagnostics"][0]["code"], "PARTIAL_DECLARATIONS")

    def test_setter_and_closure_assignments_are_not_constructor_defaults(self):
        body = '''var self = Base.apply(this, arguments) || this;
        return self.count = 3, self;
        (function () { self.count = 999; })();'''
        result = self.run_source(rf_module(constructor_body=body), ["neutral-rf-01"])
        fields = result["components"]["neutral-rf-01"]["fields"]
        self.assertEqual([(field["name"], field["value"]) for field in fields], [("count", 3)])
        self.assertFalse(any(field["value"] == 999 for field in fields))

    def test_conditional_constructor_assignment_becomes_gap_and_cannot_pass_as_default(self):
        body = '''var self = Base.apply(this, arguments) || this;
        self.safe = 1;
        if (enabled) self.dynamicValue = 8;
        return self;'''
        result = self.run_source(rf_module(constructor_body=body), ["neutral-rf-01"])
        component = result["components"]["neutral-rf-01"]
        self.assertEqual([field["name"] for field in component["fields"]], ["safe"])
        self.assertTrue(any(gap.get("kind") == "non_direct_constructor_assignment" and gap.get("name") == "dynamicValue" for gap in component["gaps"]))

    def test_compiler_boolean_literal_form_is_recovered_as_boolean(self):
        result = self.run_source(rf_module(constructor_body="var self = Base.apply(this, arguments) || this; return self.enabled = !1, self;"), ["neutral-rf-01"])
        field = result["components"]["neutral-rf-01"]["fields"][0]
        self.assertEqual((field["kind"], field["value"]), ("boolean", False))

    def test_direct_constructor_this_assignment_is_supported(self):
        result = self.run_source(rf_module(constructor_body="this.visible = true;"), ["neutral-rf-01"])
        field = result["components"]["neutral-rf-01"]["fields"][0]
        self.assertEqual((field["name"], field["kind"], field["value"]), ("visible", "boolean", True))

    def test_source_hash_mismatch_is_rejected_and_duplicate_rf_is_not_selected(self):
        text = rf_module(constructor_body="var self = Base.apply(this, arguments) || this; return self.flag = false, self;")
        raw = text.encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game.js"
            path.write_bytes(raw)
            mismatch = extract_declarations(path, "0" * 64, ["neutral-rf-01"])
            self.assertEqual(mismatch["diagnostics"][0]["code"], "SOURCE_SHA256_MISMATCH")
            duplicate = text + text
            path.write_text(duplicate)
            result = extract_declarations(path, hashlib.sha256(duplicate.encode()).hexdigest(), ["neutral-rf-01"])
            self.assertEqual(result["components"]["neutral-rf-01"]["fields"], [])
            self.assertEqual(result["components"]["neutral-rf-01"]["gaps"][0]["kind"], "ambiguous_rf_module")

    def test_unique_lexical_rf_base_inherits_defaults_and_child_overrides_with_provenance(self):
        source = '''cc._RF.push({exports:{}}, "neutral-base-rf", "RenamedBase");
var BaseAlias=(function(Parent){function RenamedBase(){var self=Parent.apply(this,arguments)||this;return self.inherited=11,self.shared=1,self;} inherit(RenamedBase,Parent); decorate([property()],RenamedBase.prototype,"inherited"); decorate([property()],RenamedBase.prototype,"shared");})(cc.Component);
cc._RF.pop();
cc._RF.push({exports:{}}, "neutral-child-rf", "RenamedChild");
(function(Base){function RenamedChild(){var self=Base.apply(this,arguments)||this;return self.shared=99,self.own=true,self;} inherit(RenamedChild,Base); decorate([property()],RenamedChild.prototype,"shared"); decorate([property()],RenamedChild.prototype,"own");})(BaseAlias);
cc._RF.pop();'''
        result = self.run_source(source, ["neutral-child-rf"])
        component = result["components"]["neutral-child-rf"]
        fields = {field["name"]: field for field in component["fields"]}
        self.assertEqual(fields["inherited"]["value"], 11)
        self.assertEqual(fields["inherited"]["sourceType"], "neutral-base-rf")
        self.assertEqual(fields["shared"]["value"], 99)
        self.assertEqual(fields["shared"]["sourceType"], "neutral-child-rf")
        self.assertEqual(component["baseResolution"]["kind"], "resolved_source_rf")
        self.assertEqual(component["baseChain"][-1], {"kind": "engine_managed", "expression": "cc.Component"})
        self.assertEqual(component["gaps"], [])

    def test_constant_enum_members_are_resolved_only_from_transpiled_enum_tables(self):
        source = '''var config;
!function(e){e[e.FIRST=4]="FIRST",e[e.SECOND=9]="SECOND";}(config.Mode||(config.Mode={}));
cc._RF.push({exports:{}}, "enum-rf", "EnumWidget");
(function(Base){function EnumWidget(){var self=Base.apply(this,arguments)||this;return self.mode=config.Mode.SECOND,self.unknown=config.Mode.MISSING,self;} inherit(EnumWidget,Base); decorate([property()],EnumWidget.prototype,"mode"); decorate([property()],EnumWidget.prototype,"unknown"); decorate([ccclass],EnumWidget);})(cc.Component);
cc._RF.pop();'''
        result = self.run_source(source, ["enum-rf"])
        component = result["components"]["enum-rf"]
        self.assertEqual([(field["name"], field["value"]) for field in component["fields"]], [("mode", 9)])
        self.assertTrue(any(gap.get("name") == "unknown" and gap.get("kind") == "non_constant_constructor_assignment"
                            for gap in component["gaps"]))

    def test_custom_component_type_alias_is_proven_through_exact_rf_component_base(self):
        source = '''cc._RF.push({exports:{}}, "custom-rf", "CustomPanel");
var C=(function(Base){function Entry(){var self=Base.apply(this,arguments)||this;return self.enabledField=true,self;} inherit(Entry,Base); decorate([ccclass],Entry); return Entry;})(cc.Component);
cc._RF.pop();
cc._RF.push({exports:{}}, "holder-rf", "Holder");
(function(Base){function Holder(){var self=Base.apply(this,arguments)||this;return self.child=null,self;} inherit(Holder,Base); decorate([property(C)],Holder.prototype,"child",void 0); decorate([ccclass],Holder);})(cc.Component);
cc._RF.pop();'''
        result = self.run_source(source, ["holder-rf"])
        component = result["components"]["holder-rf"]
        row = next(item for item in component["propertyTypes"] if item["name"] == "child")
        self.assertEqual(row["types"], ["cc.Component"])

    def test_declared_array_of_inline_serializable_record_carries_defaults_and_enum_provenance(self):
        source = '''cc._RF.push({exports:{}}, "record-rf", "RecordPanel");
var State;(function(e){e[e.ZERO=0]="ZERO",e[e.ONE=1]="ONE";})(State||(State={}));
var Entry=(function(){function Entry(){this.mode=State.ONE,this.texture=null;} decorate([property({type:cc.Enum(State)})],Entry.prototype,"mode",void 0); decorate([property(cc.SpriteFrame)],Entry.prototype,"texture",void 0); decorate([ccclass("ModeTextureEntry")],Entry); return Entry;}());
(function(Base){function RecordPanel(){var self=Base.apply(this,arguments)||this;return self.entries=[],self;} inherit(RecordPanel,Base); decorate([property({type:[Entry]})],RecordPanel.prototype,"entries",void 0); decorate([ccclass],RecordPanel);})(cc.Component);
cc._RF.pop();'''
        result = self.run_source(source, ["record-rf"])
        component = result["components"]["record-rf"]
        declaration = next(item for item in component["propertyTypes"] if item["name"] == "entries")
        self.assertEqual(len(declaration["types"]), 1)
        marker = "__monkey_static_type_v1__:"
        encoded = declaration["types"][0]
        self.assertTrue(encoded.startswith(marker))
        descriptor = json.loads(encoded[len(marker):])
        self.assertEqual(descriptor["element"]["kind"], "record")
        fields = {field["name"]: field for field in descriptor["element"]["fields"]}
        self.assertEqual((fields["mode"]["kind"], fields["mode"]["value"]), ("float", 1))
        self.assertEqual(fields["mode"]["enumValues"], [{"name": "ZERO", "value": 0}, {"name": "ONE", "value": 1}])
        self.assertEqual((fields["texture"]["kind"], fields["texture"]["sourceDeclaredType"]), ("null", "cc.SpriteFrame"))

    def test_conditional_reassignment_of_base_alias_stays_unresolved(self):
        source = '''cc._RF.push({exports:{}}, "neutral-base-rf", "RenamedBase");
var BaseAlias=(function(Parent){function RenamedBase(){var self=Parent.apply(this,arguments)||this;return self.inherited=11,self;} inherit(RenamedBase,Parent);})(cc.Component);
cc._RF.pop();
if (flag) BaseAlias = DynamicBase;
cc._RF.push({exports:{}}, "neutral-child-rf", "RenamedChild");
(function(Base){function RenamedChild(){var self=Base.apply(this,arguments)||this;return self.own=true,self;} inherit(RenamedChild,Base); decorate([property()],RenamedChild.prototype,"own");})(BaseAlias);
cc._RF.pop();'''
        result = self.run_source(source, ["neutral-child-rf"])
        component = result["components"]["neutral-child-rf"]
        self.assertEqual([field["name"] for field in component["fields"]], ["own"])
        self.assertEqual(component["baseResolution"]["kind"], "unresolved")
        self.assertTrue(any(gap["kind"] == "base_class_unresolved" and gap.get("reason") == "dynamic_or_conditional_write" for gap in component["gaps"]))

    def test_runtime_render_cache_is_evidence_only_and_decorated_preset_survives(self):
        source = '''cc._RF.push({exports:{}}, "ui-color-rf", "UIColor");
(function(Base){function UIColor(){var self=Base.apply(this,arguments)||this;return self.renders=[],self.rendersPreset=[],self._materialVariants=new Map(),self._silhouette=cc.Color.WHITE,self;} inherit(UIColor,Base);
decorate([property([cc.RenderComponent])],UIColor.prototype,"rendersPreset",void 0);
decorate([property({type:cc.Color})],UIColor.prototype,"silhouette",void 0);
decorate([property()],UIColor.prototype,"_silhouette",void 0);
decorate([property(cc.Boolean)],UIColor.prototype,"refreshPreset",null);
Object.defineProperty(UIColor.prototype,"silhouette",{get:function(){return this._silhouette;},set:function(value){this._silhouette=value,this.refresh();}});
Object.defineProperty(UIColor.prototype,"refreshPreset",{get:function(){return!1;},set:function(value){}});
})(cc.Component); cc._RF.pop();'''
        result = self.run_source(source, ["ui-color-rf"])
        component = result["components"]["ui-color-rf"]
        fields = {field["name"]: field for field in component["fields"]}
        self.assertNotIn("renders", fields)
        self.assertEqual((fields["rendersPreset"]["kind"], fields["rendersPreset"]["value"]), ("array", []))
        self.assertEqual(fields["silhouette"]["value"], {"r": 255, "g": 255, "b": 255, "a": 255})
        self.assertEqual(fields["silhouette"]["accessorBacking"]["backingFieldName"], "_silhouette")
        self.assertEqual(fields["silhouette"]["constantResolution"], "cocos_creator_2_4_documented_color_white")
        self.assertEqual(fields["silhouette"]["sourceConstant"], "cc.Color.WHITE")
        self.assertEqual((fields["refreshPreset"]["kind"], fields["refreshPreset"]["value"]), ("boolean", False))
        self.assertEqual(fields["refreshPreset"]["accessorDefault"], "pure_constant_getter_and_noop_setter")
        self.assertEqual(next(row for row in component["propertyTypes"] if row["name"] == "rendersPreset")["types"], ["[cc.RenderComponent]"])
        self.assertEqual(next(row for row in component["propertyTypes"] if row["name"] == "silhouette")["types"], ["cc.Color"])
        runtime = {row["name"] for row in component["runtimeFields"]}
        self.assertEqual(runtime, {"renders", "_materialVariants"})
        self.assertFalse(component["gaps"])

    def test_undecorated_runtime_constructor_expression_does_not_block_but_decorated_one_does(self):
        source = rf_module(constructor_body='''var self=Base.apply(this,arguments)||this;
        return self.cache=new Map(), self.required=new Map(), self;''').replace(
            '  decorate([property()], RenamedWidget.prototype, "unknown", void 0);',
            '  decorate([property()], RenamedWidget.prototype, "unknown", void 0);\n  decorate([property()], RenamedWidget.prototype, "required", void 0);')
        result = self.run_source(source, ["neutral-rf-01"])
        component = result["components"]["neutral-rf-01"]
        self.assertEqual(component["fields"], [])
        self.assertTrue(any(gap.get("name") == "required" and gap["kind"] == "non_constant_constructor_assignment" for gap in component["gaps"]))
        self.assertEqual([row["name"] for row in component["runtimeFields"]], ["cache"])

    def test_accessor_backing_requires_exact_matching_getter_and_setter(self):
        source = '''cc._RF.push({exports:{}}, "unsafe-accessor-rf", "UnsafeAccessor");
(function(Base){function UnsafeAccessor(){var self=Base.apply(this,arguments)||this;return self._value=1,self;} inherit(UnsafeAccessor,Base);
decorate([property(cc.Number)],UnsafeAccessor.prototype,"value",void 0);
Object.defineProperty(UnsafeAccessor.prototype,"value",{get:function(){return this._other;},set:function(value){this._value=value;}});
})(cc.Component); cc._RF.pop();'''
        result = self.run_source(source, ["unsafe-accessor-rf"])
        component = result["components"]["unsafe-accessor-rf"]
        self.assertEqual(component["fields"], [])
        self.assertEqual({row["name"] for row in component["runtimeFields"]}, {"_value"})


if __name__ == "__main__":
    unittest.main()
