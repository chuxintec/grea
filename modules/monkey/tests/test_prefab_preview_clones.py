import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import shutil
import subprocess

from monkey.io import encoded, write_json
from monkey.prefab_preview_clones import PreviewCloneError, prepare_clones, validate_clone_batch


def _append_expected(rule, index):
    column, row = index % rule["columns"], index // rule["columns"]
    width, height = rule["expectedParentSize"]
    left, _bottom, _right, top = rule["padding"]
    cell_width, cell_height = rule["cellSize"]
    gap_x, gap_y = rule["spacing"]
    return [-width / 2 + left + cell_width / 2 + column * (cell_width + gap_x),
            height / 2 - top - cell_height / 2 - row * (cell_height + gap_y), 0]


def fixture(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = "bundle:prefab-neutral"
    template = source + "#3"
    parent = source + "#2"
    sprite_node = source + "#4"
    hidden = source + "#5"
    label = source + "#3/components/0"
    sprite = source + "#4/components/0"
    layout = parent + "/components/0"
    manifest = "a" * 64
    proof = root / "source-evidence.json"
    proof.write_text('{"source":"neutral-fixture"}\n')
    proof_sha = hashlib.sha256(proof.read_bytes()).hexdigest()
    plan = {
        "sourceManifestSha256": manifest,
        "sourcePrefabs": [{"sourceId": source}],
        "nodes": [
            {"sourceId": source + "#1", "name": "Root", "parent": None, "children": [parent],
             "components": [], "active": True, "scale": [1, 1, 1], "position": [0, 0, 0], "size": [500, 700]},
            {"sourceId": parent, "name": "Grid", "parent": source + "#1", "children": [template],
             "components": [layout], "active": True, "scale": [1, 1, 1], "position": [0, 0, 0], "size": [300, 300]},
            {"sourceId": template, "name": "Entry", "parent": parent, "children": [sprite_node, hidden],
             "components": [label], "active": True, "scale": [1, 1, 1], "position": [-50, -50, 0], "size": [100, 100]},
            {"sourceId": sprite_node, "name": "Icon", "parent": template, "children": [], "components": [sprite],
             "active": True, "scale": [1, 1, 1], "position": [0, 0, 0], "size": [32, 32], "opacity": 255,
             "color": [255, 255, 255, 255]},
            {"sourceId": hidden, "name": "Hidden", "parent": template, "children": [], "components": [],
             "active": True, "scale": [1, 1, 1], "position": [0, -30, 0], "size": [50, 20], "opacity": 255,
             "color": [255, 255, 255, 255]},
        ],
        "components": [
            {"sourceId": layout, "node": parent, "type": "cc.Layout", "enabled": True, "layoutType": 3},
            {"sourceId": label, "node": template, "type": "cc.Label", "enabled": True, "text": "Template"},
            {"sourceId": sprite, "node": sprite_node, "type": "cc.Sprite", "enabled": True, "spriteFrame": None},
        ],
        "assets": [{"sourceId": "bundle:sprite-a"}, {"sourceId": "bundle:sprite-b"}],
    }
    stage = root / "stage"
    stage.mkdir()
    plan_path = stage / "plan.json"
    plan_raw = encoded(plan)
    plan_path.write_bytes(plan_raw)
    write_json(stage / "manifest.json", {"sourceManifestSha256": manifest, "files": [
        {"path": "plan.json", "sha256": hashlib.sha256(plan_raw).hexdigest(), "bytes": len(plan_raw)}
    ]})
    clone_spec = {
        "schema": "monkey-prefab-preview-clones/1",
        "id": "neutral-fixture",
        "sourcePrefabId": source,
        "sourceManifestSha256": manifest,
        "sourceVersion": "source-1",
        "referenceVersion": "fixture-1",
        "sourceEvidenceFiles": [{"path": proof.name, "sha256": proof_sha}],
        "template": {
            "rootSourceId": template,
            "parentSourceId": parent,
            "layoutComponentSourceId": layout,
            "layoutMode": "native-layout",
            "initialSiblingIndex": 0,
            "initialChildSourceIds": [template],
        },
        "instances": [],
    }
    for i, asset in enumerate(("bundle:sprite-a", "bundle:sprite-b")):
        clone_spec["instances"].append({
            "instanceId": f"entry-{i}", "sourceRowId": f"row-{i}", "configOrderIndex": i,
            "siblingIndex": i, "mode": "reuse-template" if i == 0 else "clone-template",
            "sourceNodeId": template, "parentSourceId": parent,
            "operations": [
                {"kind": "node.active", "sourceId": hidden, "expectedValue": True, "value": False},
                {"kind": "label.text", "sourceId": label, "expectedValue": "Template", "value": "???"},
                {"kind": "sprite.asset", "sourceId": sprite, "expectedValue": None, "value": asset},
                {"kind": "node.opacity", "sourceId": sprite_node, "expectedValue": 255, "value": 110},
            ],
            "extraOperations": [{"kind": "sprite.color", "sourceId": sprite,
                "expectedValue": [255, 255, 255, 255], "value": [0, 0, 0, 255]}],
        })
    spec_path = root / "clone-spec.json"
    spec_raw = encoded(clone_spec)
    spec_path.write_bytes(spec_raw)
    return root, spec_path, hashlib.sha256(spec_raw).hexdigest(), plan_path, hashlib.sha256(plan_raw).hexdigest(), clone_spec, plan


class PrefabPreviewClonesTests(unittest.TestCase):
    def test_prepares_repeated_states_and_native_layout_contract_without_coordinates(self):
        with tempfile.TemporaryDirectory() as temp:
            root, spec_path, spec_sha, plan_path, plan_sha, clone_spec, plan = fixture(temp)
            output = root / "prepared"
            result = prepare_clones(spec_path, spec_sha, plan_path, plan_sha, root, output)
            batch = json.loads((output / "clone-batch.json").read_text())
            self.assertEqual(result["schema"], "monkey-prefab-preview-clone-batch/1")
            self.assertEqual(len(batch["instances"]), 2)
            self.assertEqual(batch["instances"][0]["previewState"]["operations"][1]["stringValue"], "???")
            self.assertEqual(batch["instances"][1]["previewState"]["operations"][2]["assetId"], "bundle:sprite-b")
            self.assertEqual(batch["instances"][0]["extraOperations"][0]["kind"], "sprite.color")
            self.assertEqual(batch["template"]["layoutMode"], "native-layout")
            self.assertTrue(batch["template"]["positionsAreTargetReadbackOnly"])
            self.assertNotIn("position", batch["instances"][1])
            self.assertTrue(validate_clone_batch(batch, plan))

    def test_fails_closed_on_hash_manifest_tree_asset_layout_and_projected_position(self):
        with tempfile.TemporaryDirectory() as temp:
            root, spec_path, spec_sha, plan_path, plan_sha, spec, plan = fixture(temp)
            with self.assertRaises(PreviewCloneError):
                prepare_clones(spec_path, "0" * 64, plan_path, plan_sha, root, root / "wrong-spec-hash")
            self.assertFalse((root / "wrong-spec-hash").exists())

            spec["template"]["layoutMode"] = "projected-coordinates"
            raw = encoded(spec); spec_path.write_bytes(raw)
            with self.assertRaises(PreviewCloneError):
                prepare_clones(spec_path, hashlib.sha256(raw).hexdigest(), plan_path, plan_sha, root, root / "projected")
            self.assertFalse((root / "projected").exists())

            spec["template"]["layoutMode"] = "native-layout"
            spec["instances"][1]["operations"][2]["value"] = "bundle:unknown"
            raw = encoded(spec); spec_path.write_bytes(raw)
            with self.assertRaises(PreviewCloneError):
                prepare_clones(spec_path, hashlib.sha256(raw).hexdigest(), plan_path, plan_sha, root, root / "unknown-asset")
            self.assertFalse((root / "unknown-asset").exists())

    def test_wrong_manifest_or_non_layout_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, spec_path, spec_sha, plan_path, plan_sha, spec, plan = fixture(temp)
            spec["sourceManifestSha256"] = "b" * 64
            raw = encoded(spec); spec_path.write_bytes(raw)
            with self.assertRaises(PreviewCloneError):
                prepare_clones(spec_path, hashlib.sha256(raw).hexdigest(), plan_path, plan_sha, root, root / "wrong-manifest")

            spec["sourceManifestSha256"] = plan["sourceManifestSha256"]
            raw = encoded(spec); spec_path.write_bytes(raw)
            plan["components"][0]["enabled"] = False
            plan_raw = encoded(plan); plan_path.write_bytes(plan_raw)
            write_json(plan_path.parent / "manifest.json", {"sourceManifestSha256": plan["sourceManifestSha256"], "files": [
                {"path": "plan.json", "sha256": hashlib.sha256(plan_raw).hexdigest(), "bytes": len(plan_raw)}
            ]})
            with self.assertRaises(PreviewCloneError):
                prepare_clones(spec_path, hashlib.sha256(raw).hexdigest(), plan_path,
                    hashlib.sha256(plan_raw).hexdigest(), root, root / "disabled-layout")

    def test_cross_prefab_template_replaces_only_declared_container_placeholder(self):
        with tempfile.TemporaryDirectory() as temp:
            root, spec_path, _, plan_path, _, spec, plan = fixture(temp)
            owner, template = "bundle:owner", "bundle:template"
            old = spec["sourcePrefabId"]
            # Keep only the owner root/layout parent in the container prefab;
            # move the original source subtree to a second, explicitly declared prefab.
            mapping = {old + suffix: template + suffix for suffix in ("#3", "#4", "#5")}
            mapping.update({old + suffix: template + suffix for suffix in ("#3/components/0", "#4/components/0")})
            nodes = plan["nodes"]
            by_id = {n["sourceId"]: n for n in nodes}
            owner_root, owner_parent = by_id[old + "#1"], by_id[old + "#2"]
            template_nodes = [by_id[old + suffix] for suffix in ("#3", "#4", "#5")]
            owner_placeholder = owner + "#3"
            owner_root["children"] = [owner + "#2"]
            owner_root["sourceId"] = owner + "#1"
            owner_parent["sourceId"] = owner + "#2"
            owner_parent["parent"] = owner + "#1"
            owner_parent["children"] = [owner_placeholder]
            owner_parent["components"] = [owner + "#2/components/0"]
            layout = plan["components"][0]
            layout.update(sourceId=owner + "#2/components/0", node=owner + "#2")
            placeholder = {"sourceId": owner_placeholder, "name": "ExternalTemplatePlaceholder", "parent": owner + "#2",
                "children": [], "components": [], "active": True, "scale": [1, 1, 1],
                "position": [0, 0, 0], "size": [100, 100], "opacity": 255, "color": [255,255,255,255]}
            for node in template_nodes:
                node["sourceId"] = mapping[node["sourceId"]]
                node["parent"] = mapping.get(node.get("parent"))
                node["children"] = [mapping[x] for x in node.get("children", [])]
                node["components"] = [mapping.get(x, x) for x in node.get("components", [])]
            plan["nodes"] = [owner_root, owner_parent, placeholder] + template_nodes
            for component in plan["components"][1:]:
                component["sourceId"] = mapping[component["sourceId"]]
                component["node"] = mapping[component["node"]]
            plan["sourcePrefabs"] = [{"sourceId": owner}, {"sourceId": template}]
            spec["sourcePrefabId"] = owner
            spec["templatePrefabId"] = template
            spec["template"].update(rootSourceId=template + "#3", parentSourceId=owner + "#2",
                sourceRootParentSourceId=None, replacePlaceholderSourceId=owner_placeholder,
                layoutComponentSourceId=owner + "#2/components/0", initialChildSourceIds=[owner_placeholder])
            spec["instances"][0]["sourceNodeId"] = template + "#3"
            spec["instances"][1]["sourceNodeId"] = template + "#3"
            for row in spec["instances"]:
                for op in row["operations"]:
                    op["sourceId"] = mapping.get(op["sourceId"], op["sourceId"])
                for op in row["extraOperations"]:
                    op["sourceId"] = mapping.get(op["sourceId"], op["sourceId"])

            plan_raw = encoded(plan); plan_path.write_bytes(plan_raw)
            write_json(plan_path.parent / "manifest.json", {"sourceManifestSha256": plan["sourceManifestSha256"], "files": [
                {"path": "plan.json", "sha256": hashlib.sha256(plan_raw).hexdigest(), "bytes": len(plan_raw)}
            ]})
            spec_raw = encoded(spec); spec_path.write_bytes(spec_raw)
            batch_dir = root / "external-prepared"
            prepare_clones(spec_path, hashlib.sha256(spec_raw).hexdigest(), plan_path,
                hashlib.sha256(plan_raw).hexdigest(), root, batch_dir)
            batch = json.loads((batch_dir / "clone-batch.json").read_text())
            self.assertEqual(batch["sourcePrefabId"], owner)
            self.assertEqual(batch["templatePrefabId"], template)
            self.assertEqual(batch["template"]["replacePlaceholderSourceId"], owner_placeholder)
            self.assertEqual(batch["instances"][0]["previewState"]["sourcePrefabId"], template)
            self.assertTrue(validate_clone_batch(batch, plan))

    def test_append_external_preserves_every_owner_atom_and_uses_source_grid_formula(self):
        with tempfile.TemporaryDirectory() as temp:
            root, spec_path, _, plan_path, _, spec, plan = fixture(temp)
            owner, template = "bundle:append-owner", "bundle:append-template"
            old = spec["sourcePrefabId"]
            mapping = {old + suffix: template + suffix for suffix in ("#3", "#4", "#5")}
            mapping.update({old + suffix: template + suffix for suffix in ("#3/components/0", "#4/components/0")})
            by_id = {node["sourceId"]: node for node in plan["nodes"]}
            owner_root, owner_parent = by_id[old + "#1"], by_id[old + "#2"]
            template_nodes = [by_id[old + suffix] for suffix in ("#3", "#4", "#5")]
            atom_ids = [owner + "#3", owner + "#4"]
            owner_root.update(sourceId=owner + "#1", children=[owner + "#2"])
            owner_parent.update(sourceId=owner + "#2", parent=owner + "#1", children=atom_ids,
                components=[owner + "#2/components/0"], size=[300, 200])
            atoms = [{"sourceId": atom, "name": f"OwnerAtom{i}", "parent": owner + "#2", "children": [],
                "components": [], "active": False, "scale": [1, 1, 1], "position": [0, 0, 0], "size": [10, 10]}
                for i, atom in enumerate(atom_ids)]
            layout = plan["components"][0]
            layout.update(sourceId=owner + "#2/components/0", node=owner + "#2", layoutType=3, resize=1,
                startAxis=0, horizontalDirection=0, verticalDirection=1, constraintCount=2,
                cellSize=[100, 100], spacingXY=[5, 10], padding=[8, 0, 8, 0])
            for node in template_nodes:
                node["sourceId"] = mapping[node["sourceId"]]
                node["parent"] = mapping.get(node.get("parent"))
                node["children"] = [mapping[x] for x in node.get("children", [])]
                node["components"] = [mapping.get(x, x) for x in node.get("components", [])]
            plan["nodes"] = [owner_root, owner_parent, *atoms, *template_nodes]
            for component in plan["components"][1:]:
                component["sourceId"] = mapping[component["sourceId"]]
                component["node"] = mapping[component["node"]]
            plan["sourcePrefabs"] = [{"sourceId": owner}, {"sourceId": template}]
            spec["sourcePrefabId"], spec["templatePrefabId"] = owner, template
            spec["template"].update(rootSourceId=template + "#3", parentSourceId=owner + "#2",
                sourceRootParentSourceId=None, replacePlaceholderSourceId=None,
                layoutComponentSourceId=owner + "#2/components/0", placementMode="append-external",
                appendStartSiblingIndex=2, initialChildSourceIds=atom_ids)
            for i, row in enumerate(spec["instances"]):
                row["sourceNodeId"] = template + "#3"
                row["siblingIndex"] = 2 + i
                row["mode"] = "append-clone"
                row["extraOperations"] = row.get("extraOperations") or []
                for operation in row["operations"]:
                    operation["sourceId"] = mapping.get(operation["sourceId"], operation["sourceId"])
                for operation in row["extraOperations"]:
                    operation["sourceId"] = mapping.get(operation["sourceId"], operation["sourceId"])

            plan_raw = encoded(plan); plan_path.write_bytes(plan_raw)
            write_json(plan_path.parent / "manifest.json", {"sourceManifestSha256": plan["sourceManifestSha256"], "files": [
                {"path": "plan.json", "sha256": hashlib.sha256(plan_raw).hexdigest(), "bytes": len(plan_raw)}
            ]})
            spec_raw = encoded(spec); spec_path.write_bytes(spec_raw)
            output = root / "append-prepared"
            prepare_clones(spec_path, hashlib.sha256(spec_raw).hexdigest(), plan_path,
                hashlib.sha256(plan_raw).hexdigest(), root, output)
            batch = json.loads((output / "clone-batch.json").read_text())
            self.assertEqual(batch["template"]["placementMode"], "append-external")
            self.assertEqual(batch["template"]["initialChildSourceIds"], atom_ids)
            self.assertEqual(batch["template"]["appendStartSiblingIndex"], 2)
            self.assertEqual(batch["template"]["expectedChildCount"], 4)
            self.assertEqual([row["siblingIndex"] for row in batch["instances"]], [2, 3])
            self.assertEqual([row["mode"] for row in batch["instances"]], ["append-clone", "append-clone"])
            self.assertEqual(batch["template"]["firstSourcePosition"], [-50, -50, 0])
            rule = batch["template"]["appendLayoutRule"]
            self.assertEqual(rule["expectedParentSize"], [300.0, 100.0])
            self.assertEqual([round(x, 3) for x in _append_expected(rule, 0)], [-92.0, 0.0, 0.0])
            self.assertNotEqual(_append_expected(rule, 0), batch["template"]["firstSourcePosition"])
            self.assertTrue(validate_clone_batch(batch, plan))

            batch["template"]["initialChildSourceIds"] = list(reversed(atom_ids))
            with self.assertRaises(PreviewCloneError):
                validate_clone_batch(batch, plan)
            batch["template"]["initialChildSourceIds"] = atom_ids
            owner_atom = next(node for node in plan["nodes"] if node["sourceId"] == atom_ids[0])
            owner_atom["active"] = True
            with self.assertRaises(PreviewCloneError):
                validate_clone_batch(batch, plan)

    def test_source_manual_layout_requires_pinned_span_and_exact_formula_positions(self):
        with tempfile.TemporaryDirectory() as temp:
            root, spec_path, _, plan_path, _, spec, plan = fixture(temp)
            source_code = root / "manual-layout.js"
            source_code.write_bytes(b"templateWidth=100; gap=10; count=2; centered-horizontal-linear")
            raw_source = source_code.read_bytes()
            source_sha = hashlib.sha256(raw_source).hexdigest()
            spec["sourceEvidenceFiles"].append({"path": source_code.name, "sha256": source_sha})
            spec["template"].update(layoutMode="source-manual", layoutComponentSourceId=None,
                sourceManualLayout={"formulaId": "centered-horizontal-linear/1", "sourceEvidenceId": "manual-span",
                    "sourceCodePath": source_code.name, "sourceCodeSha256": source_sha,
                    "sourceBytes": {"start": 0, "end": len(raw_source)}, "sourceSpanSha256": source_sha,
                    "templateWidth": 100, "gap": 10, "count": 2, "sourceTemplateY": -50})
            plan["nodes"][1]["components"] = []
            plan["components"] = plan["components"][1:]
            for i, row in enumerate(spec["instances"]):
                row["mode"] = "clone-template"
                row["siblingIndex"] = i + 1
                row["position"] = [-45 + i * 90, -50, 0]
                row["positionEvidenceId"] = "manual-span"

            plan_raw = encoded(plan); plan_path.write_bytes(plan_raw)
            write_json(plan_path.parent / "manifest.json", {"sourceManifestSha256": plan["sourceManifestSha256"], "files": [
                {"path": "plan.json", "sha256": hashlib.sha256(plan_raw).hexdigest(), "bytes": len(plan_raw)}
            ]})
            spec_raw = encoded(spec); spec_path.write_bytes(spec_raw)
            output = root / "manual-prepared"
            spec["template"]["sourceManualLayout"]["sourceSpanSha256"] = "0" * 64
            bad_proof = encoded(spec); spec_path.write_bytes(bad_proof)
            with self.assertRaises(PreviewCloneError):
                prepare_clones(spec_path, hashlib.sha256(bad_proof).hexdigest(), plan_path,
                    hashlib.sha256(plan_raw).hexdigest(), root, output)
            self.assertFalse(output.exists())

            # Use two source-backed rows and matching positions; a malformed
            # or missing proof is never treated as a layout pass.
            spec["instances"] = spec["instances"][:2]
            spec["instances"][1]["operations"] = spec["instances"][0]["operations"]
            spec["instances"][1]["extraOperations"] = spec["instances"][0]["extraOperations"]
            spec["template"]["sourceManualLayout"]["count"] = 2
            spec["template"]["sourceManualLayout"]["sourceSpanSha256"] = source_sha
            spec["instances"][0]["position"] = [-45, -50, 0]
            spec["instances"][1]["position"] = [45, -50, 0]
            raw = encoded(spec); spec_path.write_bytes(raw)
            output = root / "manual-prepared-ok"
            prepare_clones(spec_path, hashlib.sha256(raw).hexdigest(), plan_path,
                hashlib.sha256(plan_raw).hexdigest(), root, output)
            batch = json.loads((output / "clone-batch.json").read_text())
            self.assertEqual(batch["template"]["layoutMode"], "source-manual")
            self.assertEqual([r["position"] for r in batch["instances"]], [[-45, -50, 0], [45, -50, 0]])
            self.assertTrue(validate_clone_batch(batch, plan))

            manual_layout = spec["template"]["sourceManualLayout"]
            manual_layout.clear()
            manual_layout.update({"formulaId": "progress-threshold-centers/1", "sourceEvidenceId": "manual-span",
                "sourceCodePath": source_code.name, "sourceCodeSha256": source_sha,
                "sourceBytes": {"start": 0, "end": len(raw_source)}, "sourceSpanSha256": source_sha,
                "count": 2, "sourceTemplateY": -50, "progressBarTotalLength": 460, "totalThresholdCount": 5})
            spec["instances"][0]["position"] = [-138, -50, 0]
            spec["instances"][1]["position"] = [-46, -50, 0]
            raw = encoded(spec); spec_path.write_bytes(raw)
            output = root / "manual-progress-prepared"
            prepare_clones(spec_path, hashlib.sha256(raw).hexdigest(), plan_path,
                hashlib.sha256(plan_raw).hexdigest(), root, output)
            batch = json.loads((output / "clone-batch.json").read_text())
            self.assertEqual([r["position"] for r in batch["instances"]], [[-138, -50, 0], [-46, -50, 0]])
            self.assertTrue(validate_clone_batch(batch, plan))

            spec["instances"][1]["position"][0] = 46
            raw = encoded(spec); spec_path.write_bytes(raw)
            with self.assertRaises(PreviewCloneError):
                prepare_clones(spec_path, hashlib.sha256(raw).hexdigest(), plan_path,
                    hashlib.sha256(plan_raw).hexdigest(), root, root / "manual-bad-position")

            manual_layout.clear()
            manual_layout.update({"formulaId": "pass-task-linear-y/1", "sourceEvidenceId": "manual-span",
                "sourceCodePath": source_code.name, "sourceCodeSha256": source_sha,
                "sourceBytes": {"start": 0, "end": len(raw_source)}, "sourceSpanSha256": source_sha,
                "count": 2, "sourceTemplateY": -100, "passItemHeight": 200, "spacingY": 10})
            spec["instances"][0].update(position=[0, -100, 0], positionEvidenceId="manual-span", layoutIndex=0)
            spec["instances"][1].update(position=[0, -310, 0], positionEvidenceId="manual-span", layoutIndex=1)
            raw = encoded(spec); spec_path.write_bytes(raw)
            output = root / "pass-manual-prepared"
            prepare_clones(spec_path, hashlib.sha256(raw).hexdigest(), plan_path,
                hashlib.sha256(plan_raw).hexdigest(), root, output)
            batch = json.loads((output / "clone-batch.json").read_text())
            self.assertEqual([row["position"] for row in batch["instances"]], [[0, -100, 0], [0, -310, 0]])
            self.assertEqual([row["layoutIndex"] for row in batch["instances"]], [0, 1])
            self.assertTrue(validate_clone_batch(batch, plan))

    def test_sprite_color_accepts_source_node_with_one_sprite_and_resolves_component(self):
        with tempfile.TemporaryDirectory() as temp:
            root, spec_path, _, plan_path, _, spec, plan = fixture(temp)
            sprite_component = spec["instances"][0]["extraOperations"][0]["sourceId"]
            sprite_node = sprite_component.rsplit("/components/", 1)[0]
            for row in spec["instances"]:
                row["extraOperations"][0]["sourceId"] = sprite_node
            raw = encoded(spec); spec_path.write_bytes(raw)
            output = root / "node-color-prepared"
            prepare_clones(spec_path, hashlib.sha256(raw).hexdigest(), plan_path,
                hashlib.sha256(plan_path.read_bytes()).hexdigest(), root, output)
            batch = json.loads((output / "clone-batch.json").read_text())
            color = batch["instances"][0]["extraOperations"][0]
            self.assertEqual(color["sourceId"], sprite_node)
            self.assertEqual(color["targetKind"], "node")
            self.assertEqual(color["targetComponentSourceId"], sprite_component)
            self.assertTrue(validate_clone_batch(batch, plan))

    def test_unity_saved_read_uses_post_apply_child_boundary(self):
        source = Path("src/monkey/targets/UnityPreviewClones.cs").read_text()
        read_start = source.index("public static Readback Read(")
        read_body = source[read_start:]
        self.assertIn("Validate(batch,sourceNodes,true)", read_body)
        validate_start = source.index("static void Validate(")
        validate_end = source.index("static void StaticOnly(", validate_start)
        validate_body = source[validate_start:validate_end]
        self.assertIn("if(readingSavedBatch)", validate_body)
        self.assertIn("parent.transform.childCount == batch.template.expectedChildCount", validate_body)
        self.assertIn("parent.transform.childCount == batch.template.initialChildSourceIds.Length", validate_body)
        self.assertIn("} else {", validate_body)

    def test_unity_instantiated_clone_roots_restore_source_name_before_mapping(self):
        source = Path("src/monkey/targets/UnityPreviewClones.cs").read_text()
        self.assertEqual(source.count("clone.name=template.name"), 3)
        self.assertIn("clone.name=template.name;clone.SetActive(false);StaticOnly(clone);", source)

    def test_creator_clone_module_uses_layout_and_reads_every_instance(self):
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js unavailable")
        helper = Path("src/monkey/targets/CreatorPreviewClones.js").resolve()
        source = r'''const Module=require('module'),original=Module._load;
class Component{constructor(node){this.node=node;this.enabled=true}}
class Color{constructor(r=255,g=255,b=255,a=255){this.r=r;this.g=g;this.b=b;this.a=a}}
class UITransform extends Component{constructor(n,w=0,h=0){super(n);this.width=w;this.height=h}}
class Layout extends Component{updateLayout(){if(this.rule){const u=this.node.getComponent(UITransform);u.height=this.rule.expectedParentSize[1];const items=this.node.children.filter(n=>n.active&&n.getComponent(UITransform));items.forEach((n,i)=>{const col=i%this.rule.columns,row=Math.floor(i/this.rule.columns),cw=this.rule.cellSize[0],ch=this.rule.cellSize[1],left=this.rule.padding[0],top=this.rule.padding[3],sx=this.rule.spacing[0],sy=this.rule.spacing[1];n.position={x:-u.width/2+left+cw/2+col*(cw+sx),y:u.height/2-top-ch/2-row*(ch+sy),z:0}});return}this.node.children.forEach((n,i)=>{if(i===0)return;n.position={x:i*100,y:-20,z:0}})}}
class Node{constructor(name){this.name=name;this.parent=null;this.children=[];this.components=[];this.position={x:0,y:0,z:0};this.scale={x:1,y:1,z:1};this.color=new Color();this.active=true;this.isValid=true}
setPosition(x,y,z){if(typeof x==='object')this.position={x:x.x,y:x.y,z:x.z};else this.position={x,y,z}}
get activeInHierarchy(){return this.active&&(!this.parent||this.parent.activeInHierarchy)}set parent(p){if(this._parent===p)return;if(this._parent){const a=this._parent.children.indexOf(this);if(a>=0)this._parent.children.splice(a,1)}this._parent=p;if(p){p.children.push(this)}}get parent(){return this._parent}
setSiblingIndex(i){if(!this.parent)throw Error('no parent');const a=this.parent.children;const old=a.indexOf(this);if(old<0)throw Error('not child');a.splice(old,1);a.splice(i,0,this)}getSiblingIndex(){return this.parent?this.parent.children.indexOf(this):-1}
addComponent(T){const c=new T(this);this.components.push(c);return c}getComponent(T){return this.components.find(x=>x instanceof T)||null}getComponents(T){return this.components.filter(x=>x instanceof T)}
clone(){const n=new Node(this.name);n.position={...this.position};n.scale={...this.scale};n.color=new Color(this.color.r,this.color.g,this.color.b,this.color.a);n.active=this.active;for(const c of this.components){let x;if(c instanceof Label){x=new Label(n);x.string=c.string}else if(c instanceof Sprite){x=new Sprite(n);x.spriteFrame=c.spriteFrame;x.color=new Color(c.color.r,c.color.g,c.color.b,c.color.a)}else if(c instanceof UIOpacity){x=new UIOpacity(n);x.opacity=c.opacity}else if(c instanceof UITransform)x=new UITransform(n,c.width,c.height);else if(c instanceof Layout)x=new Layout(n);else throw Error('unexpected component');n.components.push(x)}for(const ch of this.children)n.children.push(ch.clone());for(const ch of n.children)ch._parent=n;return n}
destroy(){if(this.parent)this.parent=null;this.isValid=false;for(const c of this.children)c.destroy()}}
class Scene extends Node{} class Label extends Component{constructor(n){super(n);this.string='Template'}}class RichText extends Component{} class Sprite extends Component{constructor(n){super(n);this.color=new Color();this.spriteFrame=null}}
class SpriteFrame{} class UIOpacity extends Component{constructor(n){super(n);this.opacity=255}}
const names=new Map([[Node,'cc.Node'],[Label,'cc.Label'],[Sprite,'cc.Sprite'],[UIOpacity,'cc.UIOpacity'],[Layout,'cc.Layout'],[UITransform,'cc.UITransform'],[SpriteFrame,'cc.SpriteFrame']]);
Module._load=function(req){if(req==='cc')return{Node,Scene,Component,Label,RichText,Sprite,UIOpacity,Layout,UITransform,SpriteFrame,Color,instantiate:n=>n.clone(),js:{getClassName:C=>names.get(C)||C.name}};if(req==='./preview-state.js')return require(process.argv[2]);if(req==='./static-richtext.js')return require(require('path').join(require('path').dirname(process.argv[1]),'CreatorStaticRichText.js'));return original.apply(this,arguments)};
const api=require(process.argv[1]),hash='a'.repeat(64),source='bundle:prefab',rootId=source+'#1',parentId=source+'#2',templateId=source+'#3',iconNodeId=source+'#4',hiddenId=source+'#5',labelId=templateId+'/components/0',spriteId=iconNodeId+'/components/0',layoutId=parentId+'/components/0';
const richSourceChildren=require(require('path').join(require('path').dirname(process.argv[1]),'CreatorStaticRichText.js')).sourceChildren;
const richNode=new Node('Rich');richNode.addComponent(RichText);const generatedRich=new Node('RICHTEXT_CHILD');generatedRich.hideFlags=1;generatedRich.parent=richNode;const authoredRich=new Node('Authored');authoredRich.parent=richNode;
if(richSourceChildren(richNode).length!==1||richSourceChildren(richNode)[0]!==authoredRich)throw Error('Creator RichText generated child was not filtered precisely');
const scene=new Scene('Scene'),root=new Node('Root');root.parent=scene;const parent=new Node('Grid');parent.parent=root;const template=new Node('Entry');template.position={x:-50,y:-50,z:0};template.parent=parent;const icon=new Node('Icon');icon.parent=template;icon.addComponent(UITransform).width=32;icon.getComponent(UITransform).height=32;const sprite=icon.addComponent(Sprite);const hidden=new Node('Hidden');hidden.parent=template;const label=template.addComponent(Label);template.addComponent(UITransform).width=100;template.getComponent(UITransform).height=100;parent.addComponent(Layout);const frame=new SpriteFrame();
const nodes=new Map([[rootId,root],[parentId,parent],[templateId,template],[iconNodeId,icon],[hiddenId,hidden]]);
const tree=[{sourceId:templateId,name:'Entry',childrenSourceIds:[iconNodeId,hiddenId],componentSourceIds:[labelId]},{sourceId:iconNodeId,name:'Icon',childrenSourceIds:[],componentSourceIds:[spriteId]},{sourceId:hiddenId,name:'Hidden',childrenSourceIds:[],componentSourceIds:[]}];
const makeState=(id,asset)=>({schemaVersion:1,stateId:id,sourcePrefabId:source,sourceManifestSha256:hash,stateSha256:hash,sourceVersion:'source-v',referenceVersion:'fixture-v',evidence:[{id:'e',path:'proof',sha256:hash}],operations:[
{kind:'node.active',sourceId:hiddenId,expectedBoolValue:true,boolValue:false,evidenceId:'e'},
{kind:'label.text',sourceId:labelId,expectedStringValue:'Template',stringValue:'???',evidenceId:'e'},
{kind:'sprite.asset',sourceId:spriteId,expectedAssetId:null,assetId:asset,sourceEnabled:true,evidenceId:'e'},
{kind:'node.opacity',sourceId:iconNodeId,expectedNumberValue:255,numberValue:110,evidenceId:'e'}]});
const batch={schema:'monkey-prefab-preview-clone-batch/1',cloneSpecSha256:hash,sourcePlanSha256:hash,sourceManifestSha256:hash,sourcePrefabId:source,
template:{rootSourceId:templateId,parentSourceId:parentId,layoutComponentSourceId:layoutId,layoutMode:'native-layout',firstSourcePosition:[-50,-50,0],positionsAreTargetReadbackOnly:true,initialChildSourceIds:[templateId],expectedChildCount:2,sourceTree:tree},
instances:[0,1].map(i=>({instanceId:'row-'+i,siblingIndex:i,mode:i?'clone-template':'reuse-template',sourceNodeId:templateId,parentSourceId:parentId,previewState:makeState('row-'+i,'asset-'+i),extraOperations:[{kind:'sprite.color',sourceId:spriteId,expectedValue:[255,255,255,255],value:[0,0,0,255]}]}))};
const resolverFactory=map=>id=>id===labelId?map.get(templateId).getComponent(Label):id===spriteId?map.get(iconNodeId).getComponent(Sprite):id===iconNodeId?map.get(iconNodeId):id===hiddenId?map.get(hiddenId):id==='asset-0'||id==='asset-1'?frame:null;
const settle=container=>container.getComponent(Layout).updateLayout();
const applied=api.Apply(batch,nodes,resolverFactory,settle);if(applied.cloneCount!==2||!applied.verified||!applied.layout.verified||label.string!=='???'||sprite.spriteFrame!==frame)throw Error('clone apply failed');
const reopened=api.Read(batch,nodes,resolverFactory,settle);if(!reopened.verified||reopened.cloneCount!==2||reopened.instances.some(x=>!x.verified))throw Error('clone readback failed');
const owner='bundle:owner',ownerParentId=owner+'#2',placeholderId=owner+'#3';
const ownerRoot=new Node('OwnerRoot');ownerRoot.parent=scene;const ownerParent=new Node('OwnerContent');ownerParent.parent=ownerRoot;ownerParent.addComponent(Layout);
const placeholder=new Node('NestedPrefabPlaceholder');placeholder.parent=ownerParent;
const externalRoot=new Node('Entry');const extIcon=new Node('Icon');extIcon.parent=externalRoot;extIcon.addComponent(UITransform).width=32;extIcon.getComponent(UITransform).height=32;extIcon.addComponent(Sprite);
const extHidden=new Node('Hidden');extHidden.parent=externalRoot;externalRoot.addComponent(Label);externalRoot.addComponent(UITransform).width=100;externalRoot.getComponent(UITransform).height=100;
const externalNodes=new Map([[ownerParentId,ownerParent],[placeholderId,placeholder]]);
const externalBatch={...batch,sourcePrefabId:owner,templatePrefabId:source,template:{...batch.template,templatePrefabId:source,parentSourceId:ownerParentId,
sourceRootParentSourceId:null,replacePlaceholderSourceId:placeholderId,initialChildSourceIds:[placeholderId],firstSourcePosition:[0,0,0]},
instances:batch.instances.map(row=>({...row,sourceNodeId:templateId,parentSourceId:ownerParentId,previewState:{...row.previewState,sourcePrefabId:source}}))};
const externalProvider=(prefabId,id)=>{if(prefabId!==source||id!==templateId)throw Error('wrong template provider request');return externalRoot};
const externalApplied=api.Apply(externalBatch,externalNodes,resolverFactory,settle,externalProvider);
if(!externalApplied.verified||placeholder.parent!==null||externalRoot.parent!==ownerParent)throw Error('cross-prefab clone apply failed');
const externalRead=api.Read(externalBatch,externalNodes,resolverFactory,settle);if(!externalRead.verified||externalRead.cloneCount!==2)throw Error('cross-prefab clone read failed');
const appendParent=new Node('AppendOwnerContent');appendParent.parent=ownerRoot;appendParent.addComponent(Layout);
const atomA=new Node('SourceAtomA');atomA.active=false;atomA.parent=appendParent;const atomB=new Node('SourceAtomB');atomB.active=false;atomB.parent=appendParent;
const appendA=owner+'#4',appendB=owner+'#5',appendNodes=new Map([[ownerParentId,appendParent],[appendA,atomA],[appendB,atomB]]);
const appendRoot=new Node('Entry');appendRoot.position={x:0,y:0,z:0};const appendIcon=new Node('Icon');appendIcon.parent=appendRoot;appendIcon.addComponent(UITransform).width=32;appendIcon.getComponent(UITransform).height=32;appendIcon.addComponent(Sprite);
const appendHidden=new Node('Hidden');appendHidden.parent=appendRoot;appendRoot.addComponent(Label);appendRoot.addComponent(UITransform).width=100;appendRoot.getComponent(UITransform).height=100;
const appendProof={formulaId:'pass-task-linear-y/1',sourceEvidenceId:'append-manual-proof',sourceCodePath:'manual.js',sourceCodeSha256:hash,
sourceBytes:{start:0,end:1},sourceSpanSha256:hash,count:2,sourceTemplateY:-50,passItemHeight:100,spacingY:10};
const appendRows=externalBatch.instances.map((row,i)=>({...row,instanceId:'append-'+i,siblingIndex:2+i,mode:'append-clone',parentSourceId:ownerParentId,
 position:[0,-50-i*110,0],layoutIndex:i,positionEvidenceId:'append-manual-proof',previewState:{...row.previewState,stateId:'append-'+i,sourcePrefabId:source}}));
const appendBatch={...externalBatch,template:{...externalBatch.template,placementMode:'append-external',appendStartSiblingIndex:2,
replacePlaceholderSourceId:null,sourceRootParentSourceId:null,parentSourceId:ownerParentId,layoutMode:'source-manual',
layoutComponentSourceId:ownerParentId+'/components/0',initialChildSourceIds:[appendA,appendB],initialSiblingIndex:2,expectedChildCount:4,
retainedTemplateDisposition:'preserve-owner-children',firstSourcePosition:[0,0,0],sourceManualLayout:appendProof},
instances:appendRows};
const appendProvider=(prefabId,id)=>{if(prefabId!==source||id!==templateId)throw Error('wrong append template provider request');return appendRoot};
const appendApplied=api.Apply(appendBatch,appendNodes,resolverFactory,null,appendProvider);
if(!appendApplied.verified||appendParent.children.length!==4||appendParent.children[0]!==atomA||appendParent.children[1]!==atomB||
appendParent.children[2].position.y!==-50||appendParent.children[3].position.y!==-160||appendParent.getComponent(Layout).enabled)
throw Error('append source-manual apply did not preserve owner children/order');
const appendRead=api.Read(appendBatch,appendNodes,resolverFactory,null);
if(!appendRead.verified||appendRead.layout.items[0].siblingIndex!==2||appendRead.layout.items[1].siblingIndex!==3)
throw Error('append source-manual readback lost sibling boundary');
const gridParent=new Node('AppendGrid');gridParent.parent=ownerRoot;gridParent.addComponent(UITransform).width=300;gridParent.getComponent(UITransform).height=200;
const gridLayout=gridParent.addComponent(Layout),gridPlaceholder=new Node('InactiveSourceTemplate');gridPlaceholder.active=false;gridPlaceholder.addComponent(UITransform).width=100;gridPlaceholder.getComponent(UITransform).height=100;gridPlaceholder.parent=gridParent;
const gridParentId=owner+'#8',gridPlaceholderId=owner+'#9',gridNodes=new Map([[gridParentId,gridParent],[gridPlaceholderId,gridPlaceholder]]);
const gridRoot=new Node('Entry');gridRoot.position={x:-222,y:0,z:0};const gridIcon=new Node('Icon');gridIcon.parent=gridRoot;gridIcon.addComponent(UITransform).width=32;gridIcon.getComponent(UITransform).height=32;gridIcon.addComponent(Sprite);
const gridHidden=new Node('Hidden');gridHidden.parent=gridRoot;gridRoot.addComponent(Label);gridRoot.addComponent(UITransform).width=100;gridRoot.getComponent(UITransform).height=100;
const gridRule={formulaId:'cocos-grid-auto-columns-top-left/1',sourceLayoutType:3,sourceResizeMode:1,sourceStartAxis:0,sourceHorizontalDirection:0,
sourceVerticalDirection:1,sourceConstraint:0,sourceConstraintCount:2,columns:2,rows:1,cellSize:[100,100],spacing:[5,10],padding:[8,0,8,0],sourceParentSize:[300,200],expectedParentSize:[300,100],count:2};gridLayout.rule=gridRule;
gridRule.inactiveOwnerChildSourceIds=[gridPlaceholderId];
const gridBatch={...externalBatch,template:{...externalBatch.template,placementMode:'append-external',appendStartSiblingIndex:1,
replacePlaceholderSourceId:null,sourceRootParentSourceId:null,parentSourceId:gridParentId,layoutMode:'native-layout',layoutComponentSourceId:gridParentId+'/components/0',
initialChildSourceIds:[gridPlaceholderId],initialSiblingIndex:1,expectedChildCount:3,retainedTemplateDisposition:'preserve-owner-children',
firstSourcePosition:[-222,0,0],appendLayoutRule:gridRule},instances:externalBatch.instances.map((row,i)=>({...row,siblingIndex:1+i,mode:'append-clone',parentSourceId:gridParentId}))};
const gridProvider=(prefabId,id)=>{if(prefabId!==source||id!==templateId)throw Error('wrong grid template provider request');return gridRoot};
const gridApplied=api.Apply(gridBatch,gridNodes,resolverFactory,container=>container.getComponent(Layout).updateLayout(),gridProvider);
if(!gridApplied.verified||gridParent.children.length!==3||gridParent.children[0]!==gridPlaceholder||gridPlaceholder.parent!==gridParent||
gridRoot.parent!==null||gridParent.children[1].position.x!==-92||gridParent.children[2].position.x!==13||gridParent.getComponent(UITransform).height!==100)
throw Error('append grid placement failed to preserve source child or verify source formula');
const gridRead=api.Read(gridBatch,gridNodes,resolverFactory,container=>container.getComponent(Layout).updateLayout());
if(!gridRead.verified||gridRead.layout.status!=='append_grid_source_rule_pass'||gridRead.layout.items[0].siblingIndex!==1)
throw Error('append grid source rule readback failed');
const manual='bundle:manual',manualRootId=manual+'#3',manualParentId=manual+'#2',manualLabelId=manualRootId+'/components/0';
const manualRoot=new Node('DayTab');manualRoot.position={x:0,y:-50,z:0};manualRoot.addComponent(Label);manualRoot.addComponent(Sprite);manualRoot.addComponent(UITransform).width=100;manualRoot.getComponent(UITransform).height=40;
const manualParent=new Node('Tabs');manualParent.parent=scene;manualRoot.parent=manualParent;const manualNodes=new Map([[manualRootId,manualRoot],[manualParentId,manualParent]]);
const manualSpriteId=manualRootId+'/components/1';
const manualRows=[-45,45].map((x,i)=>({instanceId:'day-'+i,siblingIndex:i+1,mode:'clone-template',sourceNodeId:manualRootId,parentSourceId:manualParentId,
position:[x,-50,0],positionEvidenceId:'manual-proof',previewState:{schemaVersion:1,stateId:'day-'+i,sourcePrefabId:manual,sourceManifestSha256:hash,stateSha256:hash,
sourceVersion:'source-v',referenceVersion:'fixture-v',evidence:[{id:'e',path:'proof',sha256:hash}],operations:[{kind:'label.text',sourceId:manualLabelId,
expectedStringValue:'Template',stringValue:'Day '+i,evidenceId:'e'}]},extraOperations:[{kind:'sprite.color',sourceId:manualRootId,targetKind:'node',targetNodeSourceId:manualRootId,
targetComponentSourceId:manualSpriteId,expectedValue:[255,255,255,255],value:[20,30,40,255]}]}));
const manualBatch={schema:'monkey-prefab-preview-clone-batch/1',cloneSpecSha256:hash,sourcePlanSha256:hash,sourceManifestSha256:hash,sourcePrefabId:manual,templatePrefabId:manual,
template:{rootSourceId:manualRootId,templatePrefabId:manual,parentSourceId:manualParentId,sourceRootParentSourceId:manualParentId,replacePlaceholderSourceId:null,
layoutComponentSourceId:null,layoutMode:'source-manual',firstSourcePosition:[0,-50,0],initialSiblingIndex:0,initialChildSourceIds:[manualRootId],expectedChildCount:3,
retainedTemplateDisposition:'inactive',positionsAreTargetReadbackOnly:true,sourceManualLayout:{formulaId:'centered-horizontal-linear/1',sourceEvidenceId:'manual-proof',
sourceCodePath:'manual.js',sourceCodeSha256:hash,sourceBytes:{start:0,end:1},sourceSpanSha256:hash,templateWidth:100,gap:10,count:2,sourceTemplateY:-50},
sourceTree:[{sourceId:manualRootId,name:'DayTab',childrenSourceIds:[],componentSourceIds:[manualLabelId,manualSpriteId]}]},instances:manualRows};
const manualResolverFactory=map=>id=>id===manualLabelId?map.get(manualRootId).getComponent(Label):id===manualSpriteId?map.get(manualRootId).getComponent(Sprite):id===manualRootId?map.get(manualRootId):null;
const manualApplied=api.Apply(manualBatch,manualNodes,manualResolverFactory,null);
if(!manualApplied.verified||manualParent.children.length!==3||manualRoot.active||manualParent.children[1].position.x!==-45||manualParent.children[2].position.x!==45)
throw Error('source-manual clone apply failed');
const manualRead=api.Read(manualBatch,manualNodes,manualResolverFactory,null);if(!manualRead.verified||manualRead.layout.status!=='source_manual_position_pass')throw Error('source-manual clone read failed');
const progressRoot=new Node('DayTab');progressRoot.position={x:0,y:-50,z:0};progressRoot.addComponent(Label);progressRoot.addComponent(Sprite);progressRoot.addComponent(UITransform).width=100;progressRoot.getComponent(UITransform).height=40;
const progressParent=new Node('ProgressPoints');progressParent.parent=scene;progressRoot.parent=progressParent;const progressNodes=new Map([[manualRootId,progressRoot],[manualParentId,progressParent]]);
const progressProof={formulaId:'progress-threshold-centers/1',sourceEvidenceId:'progress-proof',sourceCodePath:'manual.js',sourceCodeSha256:hash,
sourceBytes:{start:0,end:1},sourceSpanSha256:hash,count:2,sourceTemplateY:-50,progressBarTotalLength:460,totalThresholdCount:5};
const progressBatch={...manualBatch,template:{...manualBatch.template,sourceManualLayout:progressProof},instances:manualRows.map((row,i)=>({...row,position:i===0?[-138,-50,0]:[-46,-50,0],
positionEvidenceId:'progress-proof',previewState:{...row.previewState,stateId:'progress-day-'+i}}))};
const progressApplied=api.Apply(progressBatch,progressNodes,manualResolverFactory,null);
if(!progressApplied.verified||progressParent.children[1].position.x!==-138||progressParent.children[2].position.x!==-46)throw Error('progress-threshold source-manual apply failed');
const progressRead=api.Read(progressBatch,progressNodes,manualResolverFactory,null);if(!progressRead.verified||progressRead.layout.status!=='source_manual_position_pass')throw Error('progress-threshold source-manual read failed');
process.stdout.write('ok');'''
        preview_state = Path("src/monkey/targets/CreatorPreviewState.js").resolve()
        result = subprocess.run([node_bin, "-e", source, str(helper), str(preview_state)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok")


if __name__ == "__main__":
    unittest.main()
