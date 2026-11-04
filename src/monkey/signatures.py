"""Algorithm identities for safe offline checkpoint reuse across local tool edits."""
from pathlib import Path
from .io import sha,encoded


def phase_signatures():
    root=Path(__file__).parent
    layout=[str(p.relative_to(root)) for p in sorted((root/'layout').glob('*.py'))]
    prefab_profiles=[str(p.relative_to(root))for p in sorted(root.glob('prefab_*.py'))]
    prefab_templates=[str(p.relative_to(root))for p in sorted((root/'targets').rglob('*'))if p.is_file()and p.suffix in ('.cs','.js','.ts','.shader','.effect')]
    groups={
        'package':[*layout,'package.py','package_code.py','code_model.py','code_emit.py','code_math.py','code_presentation.py','code-facts.cjs','numeric-descriptors.cjs','module-context.cjs','inputs.py','sources/code.py','sources/index-modules.cjs','sources/containers.py','sources/cache.py','handoff_package.py','replan.py','post_format.py'],
        'inspect':['io.py','inputs.py',*[str(p.relative_to(root)) for p in sorted((root/'sources').glob('*.py'))]],
        'normalize':['io.py','normalize.py','prefab_completeness.py','sources/cocos34.py','sources/cocos34_graphs.py','sources/cocos38.py','sources/cocos38_graphs.py','sources/cocos38_prefabs.py',*[str(p.relative_to(root)) for p in sorted((root/'assets').glob('*.py'))]],
        'UnityProject-plan':['io.py','targets/unity.py','targets/common.py','targets/prefabs.py','targets/progress.py','assets/animation.py',*prefab_profiles,*prefab_templates,*layout],
        'CocosProject-plan':['io.py','targets/cocos.py','targets/common.py','targets/prefabs.py','targets/progress.py','assets/animation.py',*prefab_profiles,*prefab_templates,*layout],
        'emit':[*prefab_profiles,*prefab_templates,'targets/dynamic_ui.py','targets/layout.py','project_model.py']
    }
    # Include only actual dependencies present in this distribution.
    result = {name:dict(sha256=sha(encoded(files)),files=files) for name,paths in groups.items()
            for files in [{p:sha((root/p).read_bytes()) for p in [*paths,'signatures.py','structured.py','names.py'] if (root/p).is_file()}]}

    from .stage_contracts import source_contracts
    result.update(source_contracts())
    return result
