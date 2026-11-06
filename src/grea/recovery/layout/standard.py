"""monkey-project/2.0.0 fixed locations (docs/PROJECT-SPEC.md). The only module that spells target roots.

Each fixed file is (current, legacy). Candidates whose manifest carries projectLayout=VERSION use the
current path; older frozen candidates resolve the legacy path through their own pathMap.
"""
VERSION='monkey-project/2.0.0'
PARTITION_VERSION='monkey-project/1.1.0'
PREVIOUS_VERSION='monkey-project/1.0.0'

UNITY_TYPES={'sprite':'Textures','texture':'Textures','atlas':'Atlases','prefab':'Prefabs','scene':'Scenes','effect':'Effects',
    'animation':'Animations','spine':'Spine','font':'Fonts','music':'Audio/Music','sfx':'Audio/Sfx','voice':'Audio/Voice',
    'material':'Materials','shader':'Shaders','model':'Models','config':'Config','data':'Data','strings':'Strings','video':'Video'}
CREATOR_TYPES=dict(UNITY_TYPES)

ROOTS={
    'unity':dict(content='Assets/Game/Content',scenes='Assets/Game/Content/Scenes',game='Assets/Game',conversion='Assets/Game/Editor/Conversion',
        localization='Localization',minigames='MiniGames',unsorted='Unsorted',scripts='Assets/Game/Scripts'),
    'creator':dict(content='assets/resources',scenes='assets/resources/Scenes',game='assets/Game',conversion='extensions/monkey-import',
        localization='Localization',minigames='MiniGames',unsorted='Unsorted',scripts='assets/Game/Scripts'),
}
SOURCE_RECOVERY='SourceRecovery'
RECOVERY=dict(original='SourceRecovery/Original',unconverted='SourceRecovery/Unconverted',config='SourceRecovery/Config',
    modules='SourceRecovery/Code/Modules',drafts='SourceRecovery/Code/Drafts',source='SourceRecovery/Code/Source',
    thirdParty='SourceRecovery/Code/ThirdParty',excluded='SourceRecovery/Excluded')

_C='Assets/Game/Editor/Conversion/'
UNITY_FILES={
    'importPlan':(_C+'import-plan.json','Assets/Monkey/Editor/import-plan.json'),
    'outputPaths':(_C+'output-paths.json','Analysis/output-paths.json'),
    'importer':(_C+'MonkeyImporter.cs','Assets/Monkey/Editor/MonkeyImporter.cs'),
    'numericCode':(_C+'MonkeyNumericCode.cs','Assets/Monkey/Editor/MonkeyNumericCode.cs'),
    'prefabInstances':(_C+'MonkeyPrefabInstances.cs','Assets/Monkey/Editor/MonkeyPrefabInstances.cs'),
    'dynamicUi':(_C+'MonkeyDynamicUi.cs','Assets/Monkey/Editor/UnityDynamicUi.cs'),
    'previewView':('Assets/Game/Presentation/Preview/ContentPreviewView.cs','Assets/Generated/Views/MonkeyCandidateView.cs'),
    'previewPrefab':('Assets/Game/Content/Prefabs/Preview/ContentPreview.prefab','Assets/Generated/Views/Candidate.prefab'),
    'previewScene':('Assets/Game/Content/Scenes/Preview/ContentPreview.unity','Assets/Generated/Scenes/Candidate.unity'),
    'bootScene':('Assets/Game/Content/Scenes/Boot/Boot.unity','Assets/Generated/Scenes/ImportBootstrap.unity'),
    'editableProbe':('Assets/Game/Content/Prefabs/Preview/EditableProbe.prefab','Assets/Generated/Views/EditableProbe.prefab'),
}
LAYOUT_COMPONENTS=('NativeLinearLayoutGroup.cs','NativeRectConstraints.cs','NativeTextLineBox.cs','IntrinsicGridLayoutGroup.cs')
UNITY_LAYOUT_DIR='Assets/Game/Presentation/Common/Layout'
UNITY_NATIVE_ROOTS=['Assets/Game/Content','Assets/Game/Scenes','Assets/Game/Presentation','Assets/Game/Domain','Assets/TextMesh Pro']
UNITY_META_ROOTS=['Assets/Game/Editor/Conversion']

_E='extensions/monkey-import/'
CREATOR_FILES={
    'importPlan':(_E+'import-plan.json',_E+'import-plan.json'),
    'previewScene':('assets/resources/Scenes/Preview/ContentPreview.scene','assets/generated/views/Candidate.scene'),
}


def unity(key):return UNITY_FILES[key][0]
def creator(key):return CREATOR_FILES[key][0]


def current(manifest):
    return manifest.get('projectLayout') in (VERSION,PREVIOUS_VERSION,PARTITION_VERSION)


def locate(manifest,key,engine='unity'):
    """Fixed file path inside a candidate of either layout generation."""
    table=UNITY_FILES if engine=='unity' else CREATOR_FILES
    if engine=='creator' and key=='previewScene' and manifest.get('projectLayout')==PREVIOUS_VERSION:
        return 'assets/scenes/preview/ContentPreview.scene'
    if manifest.get('projectLayout') in (PREVIOUS_VERSION,PARTITION_VERSION):
        if engine=='creator' and key=='previewScene':return 'assets/Game/Scenes/Preview/ContentPreview.scene'
        old={'previewPrefab':'Assets/Game/Scenes/Preview/ContentPreview.prefab','editableProbe':'Assets/Game/Scenes/Preview/EditableProbe.prefab','previewScene':'Assets/Game/Scenes/Preview/ContentPreview.unity','bootScene':'Assets/Game/Scenes/Boot.unity'}
        if engine=='unity' and key in old:return old[key]
    if current(manifest):return table[key][0]
    from ..targets.layout import lookup
    return lookup(table[key][1],manifest)


def unity_output_paths():
    """Typed Editor host locations (UnityImporter.OutputPaths)."""
    return dict(plan=unity('importPlan'),prefab=unity('previewPrefab'),scene=unity('previewScene'),bootstrap=unity('bootScene'),
        artRoot=ROOTS['unity']['content'],controllersRoot=ROOTS['unity']['content']+'/Animations',materialsRoot=ROOTS['unity']['content']+'/Materials',
        animationsRoot=ROOTS['unity']['content'],sourcePrefabsRoot=ROOTS['unity']['content'],editableProbe=unity('editableProbe'),
        nativeRoots=UNITY_NATIVE_ROOTS,metaRoots=UNITY_META_ROOTS)


def creator_output_paths():
    return dict(scene=creator('previewScene'),prefabs='assets/resources',animations='assets/resources',nativeRoots=['assets/Game','assets/resources'])


# Analysis/ is grouped by purpose (PROJECT-SPEC 6.2). Writers use analysis(); readers use find_analysis() so frozen
# candidates with the older flat Analysis/ remain readable. Unlisted names stay at the Analysis root.
ANALYSIS_GROUPS={
    'Mappings':('source-map.json','name-map.json','package-name-map.json','module-name-map.json','decoded-name-map.json','cocos-assets.json',
                'dynamic-keys.json','font-bindings.json','unity-relocation.json','layout-migration.json','modules.json','config.json','resource-catalog.json','resource-groups.json','resource-paths.json'),
    'Ledger':('resource-ledger.json','all-inputs.json','all-texture-inputs.json','full-input-disposition.json','source-manifest.json','acquisition.json',
              'package-migration.json','provider-packages.json','dependency-closure.json'),
    'Code':('code-index.json','component-code-bindings.json','named-code-handoff.json','code-evidence-handoff.json','unity-code-model.json',
            'unity-code-quarantine.json','code-contract.json','package-code.json','numeric-code-declaration.json'),
    'Readback':('layout-check.json','editor-readback.json','native-progress.json','native-engine-error.json','native-error.json','native-page.png','native-api-timing.json',
                'tmp-resources.json','initial-editor-verification.json','bulk-finish-readback.json','native-identity-contract.json','unity-source-readback.json',
                'layout-patch-readback.json','layout-patch-summary.json','numeric-code-readback.json','texture-hydration.json','unity-texture-normalization.json','layout-patch-history'),
    'Tasks':('agent-work.json','agent-work-details.json','handoff.json','initial-handoff.json','full-resource-handoff.json','animation-module.json'),
    'Plans':('bulk-finish-plan.json','layout-patch-plan.json','native-check-spec.json','numeric-code-spec.json'),
    'Evidence':('structured-objects.json','spine-closures.json','unity-typed-objects.json','all-typed-objects.json','provider-export.json','Decoded','Egret'),
}
_ANALYSIS={name:group for group,names in ANALYSIS_GROUPS.items() for name in names}


def analysis(name):
    """Current Analysis/ location of a receipt, e.g. analysis('editor-readback.json') -> 'Analysis/Readback/editor-readback.json'."""
    head,_,rest=name.partition('/')
    group=_ANALYSIS.get(head) or ('Evidence' if head.startswith(('dependency-typed-','invalid-texture-quarantine-')) else None)
    return 'Analysis/'+(group+'/' if group else '')+name


def find_analysis(root,name):
    """Readable location in a candidate of either generation: grouped first, then the legacy flat Analysis/."""
    from pathlib import Path
    current=Path(root)/analysis(name);legacy=Path(root)/'Analysis'/name
    return legacy if not current.exists() and legacy.exists() else current


def analysis_rel(root,name):
    """find_analysis() as a candidate-relative POSIX path."""
    return find_analysis(root,name).relative_to(root).as_posix()


def find_output_paths(root):
    """Typed Editor host locations: beside the importer (current) or in the older formatted Analysis/."""
    from pathlib import Path
    current=Path(root)/unity('outputPaths');legacy=Path(root)/'Analysis/output-paths.json'
    return legacy if not current.exists() and legacy.exists() else current


def analysis_out(root,name):
    """find_analysis() for writers that copy or move files (write_json already creates parents)."""
    path=find_analysis(root,name);path.parent.mkdir(parents=True,exist_ok=True)
    return path
