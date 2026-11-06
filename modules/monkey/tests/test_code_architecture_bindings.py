import hashlib
import json
import unittest
from copy import deepcopy

from monkey.code_architecture_bindings import (
    _has_monobehaviour_declaration,
    _native_field_type_match,
    _script_identity,
    build_prefab_authoring_plan,
    extract_serialized_csharp_fields,
    extract_source_component_fields,
)
from monkey.sources.compiled import ParseError


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def plain_compiled_document(objects):
    classes, masks, values = [], [], []
    for index, obj in enumerate(objects):
        keys = [key for key in obj if key != '__type__']
        classes.append([obj['__type__'], keys, len(keys) + 1])
        masks.append([index, *range(len(keys)), len(keys) + 1])
        values.append([index, *[obj[key] for key in keys]])
    return [1, [], [], classes, masks, values, [], [], [], [], []]


def fixture(*, node_types=('UnityEngine.RectTransform',), preview_reference=None):
    source_asset = 'gameAsset:source-prefab'
    source_root = source_asset + '#1'
    source_component = source_asset + '#1/components/1'
    code_region = 'bundle:game.js#DemoView@0'
    unit_id = 'module:abc:0:100'
    source_component_type = '1111111111111111111111'
    source_file = (b'cc._RF.push({exports:{}},"' + source_component_type.encode() +
                   b'","DemoView");n([property(cc.Node)],i.prototype,"nodeRef",void 0);')
    class_path = 'Assets/Game/Presentation/Demo/View.cs'
    class_source = b'''using UnityEngine;
public sealed class View : MonoBehaviour
{
    [SerializeField] private UnityEngine.RectTransform nodeRef;
}
'''
    prefab = b'''%YAML 1.1
--- !u!1 &100
GameObject:
  m_Name: Root
--- !u!224 &101
RectTransform:
  m_GameObject: {fileID: 100}
  m_Father: {fileID: 0}
'''
    prefab_meta = b'fileFormatVersion: 2\nguid: ' + b'1' * 32 + b'\n'
    script_meta = b'fileFormatVersion: 2\nguid: ' + b'2' * 32 + b'\n'
    source_span = {'start': 0, 'end': len(source_file)}
    source_context = {
        'sourceUnitId': unit_id, 'sourcePath': 'Source/game.js',
        'sourceSha256': sha(source_file), 'sourceBytes': source_span,
        'spanSha256': sha(source_file),
    }
    architecture_sha = 'a' * 64
    source_manifest_sha = 'b' * 64
    class_record = {
        'id': 'Demo.View', 'name': 'View', 'kind': 'class', 'layer': 'Presentation', 'module': 'Demo',
        'baseType': 'UnityEngine.MonoBehaviour',
        'bindingEvidence': {'sourceIds': [code_region], 'literalBindingCount': 1,
                            'nativeAttachment': 'planned, not attached or runtime-verified'},
        'path': class_path, 'sourceUnitIds': [unit_id], 'fields': [
            {'name': 'nodeRef', 'type': 'UnityEngine.RectTransform', 'role': 'serialized view binding'}],
    }
    architecture = {'schemaVersion': 'monkey-native-code-architecture/1',
                    'sourceManifestSha256': source_manifest_sha, 'classes': [class_record]}
    module_manifest = {
        'schemaVersion': 'monkey-native-architecture-module/1', 'moduleId': 'Demo',
        'sourceManifestSha256': source_manifest_sha, 'architectureSha256': architecture_sha,
        'classes': [{'classId': 'Demo.View', 'module': 'Demo', 'path': class_path, 'bytes': len(class_source),
                     'sourceUnitIds': [unit_id]}],
        'files': [
            {'path': class_path, 'targetPath': class_path, 'sha256': sha(class_source), 'bytes': len(class_source)},
            {'path': class_path + '.meta', 'targetPath': class_path + '.meta', 'sha256': sha(script_meta), 'bytes': len(script_meta)},
        ],
        'sourceContexts': [source_context],
    }
    source_node_readback = {'sourceId': source_root, 'sourceAsset': source_asset,
                            'hierarchy': 'Root', 'componentTypes': ['UnityEngine.RectTransform']}
    context = {
        'schemaVersion': 'monkey-code-architecture-asset-context/1',
        'sourceManifestSha256': source_manifest_sha, 'architectureSha256': architecture_sha,
        'bindings': [{
            'codeRegion': code_region, 'evidence': 'exact_literal_script_identity',
            'sourceOwnership': {'sourceUnitIds': [unit_id], 'classesWithThisSourceUnit': ['Demo.View']},
            'sourceAsset': source_asset, 'sourceComponent': source_component, 'sourceNode': source_root,
            'nativeComponentStatus': 'not_implemented',
            'sourceMapNodes': [{'sourceId': source_root, 'name': 'Root', 'target': 'Assets/Game/Prefabs/Demo.prefab'}],
            'sourceMapComponents': [{'sourceId': source_component, 'node': source_root, 'type': source_component_type}],
            'sourcePrefabReadback': [{'sourceId': source_asset, 'path': 'Assets/Game/Prefabs/Demo.prefab',
                                      'guid': '1' * 32, 'identityMatch': True}],
            'sourcePrefabNodeReadback': [source_node_readback],
            'assetIdentity': {'nativeTargets': [{
                'path': 'Assets/Game/Prefabs/Demo.prefab', 'type': 'prefab', 'guid': '1' * 32,
                'sha256': sha(prefab), 'bytes': len(prefab), 'metaSha256': sha(prefab_meta), 'metaBytes': len(prefab_meta),
            }]},
            'previewReadbackReference': preview_reference,
        }],
    }
    graph = {
        'sourceAssetId': source_asset, 'rootSourceNodeId': source_root,
        'nodes': [
            {'sourceNodeId': source_root, 'name': 'Root', 'parentSourceNodeId': None, 'childIndex': None},
            {'sourceNodeId': source_asset + '#2', 'name': 'Label', 'parentSourceNodeId': source_root, 'childIndex': 0},
        ],
        'componentProperties': [{
            'sourceComponentId': source_component, 'sourceProperty': 'nodeRef',
            'targetSourceNodeId': source_asset + '#2', 'evidencePath': 'Analysis/SourceModel/demo-prefab.json',
            'evidenceSha256': sha(b'exact source component field reference'),
        }],
    }
    target_nodes = [{'sourceId': source_asset + '#2', 'prefabPath': 'Assets/Game/Prefabs/Demo.prefab',
                     'prefabGuid': '1' * 32, 'componentTypes': list(node_types)}]
    kwargs = dict(
        architecture=architecture, module_manifest=module_manifest, asset_context=context,
        class_id='Demo.View', architecture_sha256=architecture_sha, code_region=code_region,
        source_unit_id=unit_id, source_file_bytes=source_file, class_source_bytes=class_source,
        prefab_bytes=prefab, prefab_meta_bytes=prefab_meta,
        field_mappings=[{'sourceProperty': 'nodeRef', 'csharpField': 'nodeRef'}],
        source_reference_graph=graph, target_node_readback=target_nodes, script_meta_bytes=script_meta,
    )
    return kwargs


def packed_source_fixture():
    kwargs = fixture()
    source_asset = 'gameAsset:00000000-0000-0000-0000-000000000003'
    source_component = source_asset + '#1/components/1'
    source_root = source_asset + '#1'
    child_id = source_asset + '#4'
    binding = kwargs['asset_context']['bindings'][0]
    binding.update(sourceAsset=source_asset, sourceComponent=source_component, sourceNode=source_root)
    binding['sourceMapComponents'][0].update(sourceId=source_component, node=source_root,
                                            type='1111111111111111111111')
    binding['sourceMapNodes'][0].update(sourceId=source_root, name='Root')
    binding['sourcePrefabReadback'][0].update(sourceId=source_asset, path='Assets/Game/Prefabs/Demo.prefab')
    binding['sourcePrefabNodeReadback'][0].update(sourceId=source_root, sourceAsset=source_asset, hierarchy='Root')
    kwargs.pop('source_reference_graph')

    objects = [
        {'__type__': 'cc.Prefab', 'data': {'__id__': 1}},
        {'__type__': 'cc.Node', '_name': 'Root', '_components': [{'__id__': 2}, {'__id__': 3}],
         '_children': [{'__id__': 4}]},
        {'__type__': 'cc.Widget', 'node': {'__id__': 1}},
        {'__type__': '1111111111111111111111', 'node': {'__id__': 1}, 'nodeRef': {'__id__': 4}},
        {'__type__': 'cc.Node', '_name': 'Label', '_components': [], '_children': []},
    ]
    encoded = plain_compiled_document(objects)
    pack_bytes = json.dumps(encoded[:5] + [[encoded[5:]]], separators=(',', ':')).encode()
    config_bytes = json.dumps({'uuids': ['00000000-0000-0000-0000-000000000003'],
                               'packs': {'111111111': [0]}}).encode()
    prefab = b'''%YAML 1.1
--- !u!1 &100
GameObject:
  m_Component:
  - component: {fileID: 101}
  m_Name: Root
--- !u!224 &101
RectTransform:
  m_GameObject: {fileID: 100}
  m_Children:
  - {fileID: 201}
  m_Father: {fileID: 0}
--- !u!1 &200
GameObject:
  m_Component:
  - component: {fileID: 201}
  m_Name: Label
--- !u!224 &201
RectTransform:
  m_GameObject: {fileID: 200}
  m_Children: []
  m_Father: {fileID: 101}
'''
    kwargs['prefab_bytes'] = prefab
    kwargs['asset_context']['bindings'][0]['assetIdentity']['nativeTargets'][0].update(
        sha256=sha(prefab), bytes=len(prefab))
    readback = {'sourcePrefabs': [{
        'sourceId': source_asset, 'path': 'Assets/Game/Prefabs/Demo.prefab', 'guid': '1' * 32,
        'nodeCount': 2, 'savedReloaded': True, 'referencesVerified': True,
        'nodes': [
            {'sourceId': source_root, 'hierarchy': 'Root', 'componentTypes': ['UnityEngine.RectTransform']},
            {'sourceId': child_id, 'hierarchy': 'Label', 'componentTypes': ['UnityEngine.RectTransform']},
        ],
    }]}
    kwargs.update(
        source_prefab_pack_bytes=pack_bytes,
        source_project_config_bytes=config_bytes,
        source_pack_id='111111111',
        source_prefab_pack_sha256=sha(pack_bytes),
        source_project_config_sha256=sha(config_bytes),
        native_readback_bytes=json.dumps(readback, separators=(',', ':')).encode(),
    )
    kwargs['native_readback_sha256'] = sha(kwargs['native_readback_bytes'])
    return kwargs


class CodeArchitectureBindingsTests(unittest.TestCase):
    def assembled_fixture(self):
        from monkey.code_architecture_candidate import script_guid
        kwargs=fixture();kwargs['architecture']['rootNamespace']='Game'
        module=kwargs['module_manifest'];module['files']=module['files'][:1]
        row=module['files'][0];path=row['path'];class_id=kwargs['class_id']
        guid=script_guid('Fixture.Native','Game',class_id)
        meta=('fileFormatVersion: 2\nguid: '+guid+'\n').encode()
        kwargs['script_meta_bytes']=meta
        candidate={'schemaVersion':1,'namespace':'Fixture.Native','targetProfile':'unity-6000.6.2f1-ugui',
            'architectureSchemaVersion':'monkey-native-architecture-candidate/1',
            'scriptIdentitySchema':'monkey-native-script-identities/1',
            'provenance':{'kind':'native-architecture-assembly','architecturePlanSha256':kwargs['architecture_sha256'],
                'sourceCandidateManifestSha256':kwargs['architecture']['sourceManifestSha256']},
            'classPaths':{class_id:path},'files':[
                dict(row,owner='generated',sourceKind='architecture-module',provenance={'classId':class_id}),
                dict(path=path+'.meta',sha256=sha(meta),bytes=len(meta),owner='generated',sourceKind='architecture-script-meta',
                    provenance={'classId':class_id,'scriptPath':path,'scriptSha256':row['sha256'],'guid':guid})],
            'scriptIdentities':{class_id:dict(path=path,sha256=row['sha256'],metaPath=path+'.meta',metaSha256=sha(meta),guid=guid)}}
        self.pin_assembled(kwargs,candidate)
        return kwargs,candidate

    @staticmethod
    def pin_assembled(kwargs,candidate):
        raw=json.dumps(candidate,sort_keys=True).encode()
        kwargs['native_candidate_manifest_bytes']=raw
        kwargs['native_candidate_manifest_sha256']=sha(raw)

    def test_assembled_owned_meta_can_supply_identity_without_rewriting_module_receipt(self):
        kwargs,candidate=self.assembled_fixture();before=json.dumps(kwargs['module_manifest'],sort_keys=True)
        plan=build_prefab_authoring_plan(**kwargs)
        self.assertEqual(plan['assembledScriptIdentity']['manifestSha256'],kwargs['native_candidate_manifest_sha256'])
        self.assertEqual(plan['assembledScriptIdentity']['unityTypeStatus'],'pending-whole-project-compile')
        self.assertEqual(plan['operations'][0]['kind'],'attach-component-to-root')
        self.assertEqual(json.dumps(kwargs['module_manifest'],sort_keys=True),before)

    def test_assembled_meta_requires_exact_source_architecture_class_and_index(self):
        mutations=[lambda c:c['provenance'].update(architecturePlanSha256='0'*64),
            lambda c:c['provenance'].update(sourceCandidateManifestSha256='0'*64),
            lambda c:c['classPaths'].update({'Demo.View':'Assets/Game/Presentation/Other/View.cs'}),
            lambda c:c['files'][0].update(sha256='0'*64),
            lambda c:c['files'][0].update(sourceKind='architecture-revision'),
            lambda c:c['files'][1]['provenance'].update(classId='another-class'),
            lambda c:c['files'][1]['provenance'].update(scriptSha256='0'*64),
            lambda c:c['scriptIdentities']['Demo.View'].update(guid='0'*32),
            lambda c:c['files'].append(dict(c['files'][1]))]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                kwargs,candidate=self.assembled_fixture();mutation(candidate);self.pin_assembled(kwargs,candidate)
                with self.assertRaises(ParseError):build_prefab_authoring_plan(**kwargs)

    def test_assembled_meta_rejects_changed_manifest_or_unowned_script_bytes(self):
        kwargs,_=self.assembled_fixture();kwargs['native_candidate_manifest_bytes']+=b' '
        with self.assertRaises(ParseError):build_prefab_authoring_plan(**kwargs)
        kwargs,_=self.assembled_fixture();kwargs['script_meta_bytes']+=b'changed'
        with self.assertRaises(ParseError):build_prefab_authoring_plan(**kwargs)
        kwargs,_=self.assembled_fixture();kwargs.pop('native_candidate_manifest_sha256')
        with self.assertRaises(ParseError):build_prefab_authoring_plan(**kwargs)

    def test_class_identity_ignores_comments_and_all_supported_string_literal_forms(self):
        fake_declarations = [
            b'// public class View : MonoBehaviour {}\n',
            b'class Holder { string text = "public class View : MonoBehaviour {}"; }\n',
            b'class Holder { string text = @"public class View : MonoBehaviour {}"; }\n',
            b'class Holder { string text = """public class View : MonoBehaviour {}"""; }\n',
        ]
        for source in fake_declarations:
            with self.subTest(source=source):
                self.assertFalse(_has_monobehaviour_declaration(source, 'View'))
        self.assertTrue(_has_monobehaviour_declaration(
            b'public sealed class View : UnityEngine.MonoBehaviour {}', 'View'))

    def test_script_identity_requires_canonical_or_supported_compact_uuid(self):
        self.assertEqual(_script_identity('11111111-1111-1111-1111-111111111111'),
                         '11111111-1111-1111-1111-111111111111')
        self.assertIsNone(_script_identity('11111111--1111-1111-1111-111111111111'))
        self.assertIsNone(_script_identity('not-a-script-id'))

    def test_exact_component_property_and_node_path_produce_editor_intent(self):
        plan = build_prefab_authoring_plan(**fixture())
        self.assertEqual(plan['status'], 'ready-for-editor-authoring-after-whole-project-compile')
        self.assertEqual(plan['sourceClassIdentityProof']['status'], 'verified-exact-source-script-to-monoBehaviour')
        self.assertEqual(plan['sourceClassIdentityProof']['sourceClassName'], 'DemoView')
        self.assertEqual(plan['sourceClassIdentityProof']['sourceByteOffset'], 0)
        self.assertEqual(plan['sourceClassIdentityProof']['literalScriptRegistration']['className'], 'DemoView')
        self.assertEqual(plan['sourceClassIdentityProof']['sourceComponentType'], '1111111111111111111111')
        self.assertEqual(plan['component']['target']['nodePath'], [{'root': True, 'expectedName': 'Root'}])
        field = plan['fieldMappings'][0]
        self.assertEqual(field['referenceStatus'], 'verified-node-reference')
        self.assertEqual(field['reference']['nodePath'][-1]['childIndex'], 0)
        self.assertEqual(plan['operations'][0]['kind'], 'attach-component-to-root')
        self.assertEqual(plan['operations'][1]['csharpField'], 'nodeRef')
        self.assertIn('not runtime lookup keys', plan['runtimeUse'])

    def test_missing_serialized_reference_stays_unresolved_and_preview_fileid_is_ignored(self):
        kwargs = fixture(preview_reference={'status': 'verified-preview-object-reference-only', 'prefabFileId': '999'})
        kwargs['source_reference_graph'] = {'sourceAssetId': 'gameAsset:source-prefab',
                                             'rootSourceNodeId': 'gameAsset:source-prefab#1',
                                             'nodes': [], 'componentProperties': []}
        plan = build_prefab_authoring_plan(**kwargs)
        self.assertEqual(plan['fieldMappings'][0]['referenceStatus'], 'unresolved')
        self.assertFalse(any(op['kind'] == 'set-serialized-reference' for op in plan['operations']))
        self.assertNotIn('prefabFileId', str(plan))

    def test_no_case_folding_for_source_to_csharp_names(self):
        kwargs = fixture()
        kwargs['field_mappings'] = []
        plan = build_prefab_authoring_plan(**kwargs)
        self.assertTrue(any(row.get('sourceProperty') == 'nodeRef' for row in plan['unresolved']))
        self.assertTrue(any(row.get('csharpField') == 'nodeRef' for row in plan['unresolved']))

    def test_rejects_wrong_candidate_prefab_bytes_and_foreign_script_meta(self):
        kwargs = fixture()
        kwargs['prefab_bytes'] += b'changed'
        with self.assertRaisesRegex(ParseError, 'Prefab bytes differ'):
            build_prefab_authoring_plan(**kwargs)
        kwargs = fixture()
        kwargs['script_meta_bytes'] = b'fileFormatVersion: 2\nguid: ' + b'3' * 32 + b'\n'
        with self.assertRaisesRegex(ParseError, 'Script .meta bytes differ'):
            build_prefab_authoring_plan(**kwargs)

    def test_incompatible_native_component_does_not_emit_reference_assignment(self):
        plan = build_prefab_authoring_plan(**fixture(node_types=('UnityEngine.UI.Image',)))
        self.assertEqual(plan['fieldMappings'][0]['referenceStatus'],
                         'source-reference-and-node-path-verified-target-component-missing')
        self.assertEqual(plan['fieldMappings'][0]['reference']['nodePath'][-1]['expectedName'], 'Label')
        self.assertIn('does not have the required', plan['fieldMappings'][0]['unresolvedReason'])
        self.assertFalse(any(op['kind'] == 'set-serialized-reference' for op in plan['operations']))

    def test_source_and_target_field_extractors_keep_exact_types_and_identity(self):
        source = b'n([property(cc.Node)],i.prototype,"nodeRef",void 0); n([property(cc.ProgressBar)],i.prototype,"bar",void 0);'
        fields = extract_source_component_fields(source, base_offset=30)
        self.assertEqual([(f['sourceProperty'], f['sourceTypeExpression']) for f in fields],
                         [('nodeRef', 'cc.Node'), ('bar', 'cc.ProgressBar')])
        csharp = b'class V { [SerializeField] private UnityEngine.RectTransform nodeRef; }'
        self.assertEqual(extract_serialized_csharp_fields(csharp)[0]['fieldType'], 'UnityEngine.RectTransform')

    def test_rejects_nonmatching_source_hash_and_unknown_field_mapping(self):
        kwargs = fixture()
        kwargs['source_file_bytes'] += b'changed'
        with self.assertRaisesRegex(ParseError, 'Original source file differs'):
            build_prefab_authoring_plan(**kwargs)
        kwargs = fixture()
        kwargs['field_mappings'] = [{'sourceProperty': 'NodeRef', 'csharpField': 'nodeRef'}]
        with self.assertRaisesRegex(ParseError, 'not found in the pinned source component'):
            build_prefab_authoring_plan(**kwargs)

    def test_decodes_exact_pack_component_reference_and_proves_candidate_hierarchy(self):
        kwargs = packed_source_fixture()
        plan = build_prefab_authoring_plan(**kwargs)
        self.assertEqual(plan['sourceReferenceEvidence']['sourcePackSectionIndex'], 0)
        self.assertEqual(plan['sourceReferenceEvidence']['sourceUuidIndex'], 0)
        self.assertEqual(plan['sourcePrefabStructure']['status'], 'verified-isomorphic-child-index-hierarchy')
        field = plan['fieldMappings'][0]
        self.assertEqual(field['referenceStatus'], 'verified-node-reference')
        self.assertEqual(field['serializedSourceValue'], {'__id__': 4})
        self.assertEqual([step.get('expectedName') for step in field['reference']['nodePath']], ['Root', 'Label'])
        self.assertEqual([step.get('candidateNodeType') for step in field['reference']['nodePath']],
                         ['UnityEngine.RectTransform', 'UnityEngine.RectTransform'])
        self.assertEqual(field['reference']['nodePath'][-1]['childIndex'], 0)
        self.assertEqual([operation['kind'] for operation in plan['operations']],
                         ['attach-component-to-root', 'set-serialized-reference'])

    def test_known_serialized_base_field_accepts_only_documented_derived_component_types(self):
        self.assertEqual(_native_field_type_match('TMPro.TMP_Text', ['TMPro.TextMeshProUGUI']), 'known-derived-type')
        self.assertEqual(_native_field_type_match('TMPro.TMP_Text', ['UnityEngine.UI.Image']), 'missing')

    def test_source_property_reference_is_not_authorized_when_candidate_tree_differs(self):
        kwargs = packed_source_fixture()
        changed = kwargs['prefab_bytes'].replace(b'm_Name: Label', b'm_Name: Other')
        kwargs['prefab_bytes'] = changed
        target = kwargs['asset_context']['bindings'][0]['assetIdentity']['nativeTargets'][0]
        target.update(sha256=sha(changed), bytes=len(changed))
        plan = build_prefab_authoring_plan(**kwargs)
        self.assertEqual(plan['sourcePrefabStructure']['status'], 'unresolved-hierarchy-mismatch')
        self.assertEqual(plan['fieldMappings'][0]['referenceStatus'], 'unresolved')
        self.assertFalse(any(row['kind'] == 'set-serialized-reference' for row in plan['operations']))

    def test_packed_source_bytes_require_exact_hash_pins(self):
        kwargs = packed_source_fixture()
        kwargs['source_prefab_pack_sha256'] = '0' * 64
        with self.assertRaisesRegex(ParseError, 'bytes differ from their supplied pins'):
            build_prefab_authoring_plan(**kwargs)

    def test_packed_section_must_be_selected_by_exact_config_uuid_membership(self):
        kwargs = packed_source_fixture()
        config = json.loads(kwargs['source_project_config_bytes'])
        config['packs']['111111111'] = [7]
        kwargs['source_project_config_bytes'] = json.dumps(config, separators=(',', ':')).encode()
        kwargs['source_project_config_sha256'] = sha(kwargs['source_project_config_bytes'])
        with self.assertRaisesRegex(ParseError, 'Source UUID must occur exactly once'):
            build_prefab_authoring_plan(**kwargs)

    def test_rejects_shared_source_unit_class_without_exact_class_source_identity(self):
        kwargs = fixture()
        architecture = kwargs['architecture']
        plan_class = architecture['classes'][0]
        other_class = deepcopy(plan_class)
        other_class.update(id='Demo.Other', name='Other', path='Assets/Game/Presentation/Demo/Other.cs')
        other_class.pop('bindingEvidence')
        architecture['classes'].append(other_class)
        kwargs['class_id'] = 'Demo.Other'
        kwargs['class_source_bytes'] = b'''using UnityEngine;
public sealed class Other : MonoBehaviour
{
    [SerializeField] private UnityEngine.RectTransform nodeRef;
}
'''
        kwargs['module_manifest']['classes'].append({'classId': 'Demo.Other', 'module': 'Demo',
            'path': other_class['path'], 'bytes': len(kwargs['class_source_bytes']),
            'sourceUnitIds': [kwargs['source_unit_id']]})
        kwargs['module_manifest']['files'].append({'path': other_class['path'],
            'targetPath': other_class['path'], 'sha256': sha(kwargs['class_source_bytes']),
            'bytes': len(kwargs['class_source_bytes'])})
        kwargs['asset_context']['bindings'][0]['sourceOwnership']['classesWithThisSourceUnit'].append('Demo.Other')
        kwargs['script_meta_bytes'] = None
        plan = build_prefab_authoring_plan(**kwargs)
        self.assertEqual(plan['status'], 'partial-unresolved-evidence')
        self.assertEqual(plan['sourceClassIdentityProof']['status'], 'unresolved')
        self.assertEqual(plan['component']['attachStatus'], 'source-class-identity-unresolved')
        self.assertEqual(plan['operations'], [])

    def test_rejects_multiple_architecture_classes_for_one_exact_source_identity(self):
        kwargs = fixture()
        other = deepcopy(kwargs['architecture']['classes'][0])
        other.update(id='Demo.Other', name='Other', path='Assets/Game/Presentation/Demo/Other.cs')
        kwargs['architecture']['classes'].append(other)
        with self.assertRaisesRegex(ParseError, 'exactly one planned architecture class'):
            build_prefab_authoring_plan(**kwargs)

    def test_rejects_source_identity_id_or_byte_offset_that_disagrees_with_pinned_unit(self):
        kwargs = fixture()
        kwargs['architecture']['classes'][0]['bindingEvidence']['sourceIds'] = ['bundle:game.js#DifferentView@0']
        with self.assertRaisesRegex(ParseError, 'does not declare the exact selected codeRegion'):
            build_prefab_authoring_plan(**kwargs)
        kwargs = fixture()
        wrong_region = 'bundle:game.js#DemoView@1'
        kwargs['architecture']['classes'][0]['bindingEvidence']['sourceIds'] = [wrong_region]
        kwargs['asset_context']['bindings'][0]['codeRegion'] = wrong_region
        kwargs['code_region'] = wrong_region
        with self.assertRaisesRegex(ParseError, 'Source unit start does not equal'):
            build_prefab_authoring_plan(**kwargs)

    def test_legacy_class_without_binding_evidence_returns_unresolved_and_zero_operations(self):
        kwargs = fixture()
        kwargs['architecture']['classes'][0].pop('bindingEvidence')
        plan = build_prefab_authoring_plan(**kwargs)
        self.assertEqual(plan['status'], 'partial-unresolved-evidence')
        self.assertEqual(plan['sourceClassIdentityProof']['status'], 'unresolved')
        self.assertEqual(plan['operations'], [])
        self.assertTrue(any('shared source-unit ownership cannot establish' in row['reason']
                            for row in plan['unresolved']))

    def test_source_rf_registration_must_match_literal_class_name_and_component_script_type(self):
        kwargs = fixture()
        wrong_name = kwargs['source_file_bytes'].replace(b'"DemoView"', b'"DifferentView"', 1)
        kwargs['source_file_bytes'] = wrong_name
        context = kwargs['module_manifest']['sourceContexts'][0]
        context['sourceSha256'] = sha(wrong_name)
        context['spanSha256'] = sha(wrong_name)
        context['sourceBytes']['end'] = len(wrong_name)
        with self.assertRaisesRegex(ParseError, 'Literal Cocos script class name differs'):
            build_prefab_authoring_plan(**kwargs)

        kwargs = fixture()
        wrong_type = kwargs['source_file_bytes'].replace(b'"1111111111111111111111"',
                                                         b'"2222222222222222222222"', 1)
        kwargs['source_file_bytes'] = wrong_type
        context = kwargs['module_manifest']['sourceContexts'][0]
        context['sourceSha256'] = sha(wrong_type)
        context['spanSha256'] = sha(wrong_type)
        context['sourceBytes']['end'] = len(wrong_type)
        with self.assertRaisesRegex(ParseError, 'Literal Cocos script identity differs'):
            build_prefab_authoring_plan(**kwargs)


if __name__ == '__main__':
    unittest.main()
