"""Source-bound mapping of a pinned ordered recipe-table subset.

This is a finite static-data adapter. It does not execute the original JavaScript
or mutate/copy the source JSON into an output project.
"""
from __future__ import annotations

import json
import math
import re
from importlib.resources import files
from pathlib import Path

from ...io import encoded, load, new_output, read, safe, sha, write_json
from ...sources.compiled import fail

EXTENSION_ID = 'legacy_foodstreet'
_EXTENSION_RAW = files(__package__).joinpath('extension.json').read_bytes()
_EXTENSION = load(_EXTENSION_RAW, max_nodes=20_000)
if encoded(_EXTENSION) != _EXTENSION_RAW or _EXTENSION.get('schemaVersion') != 1 or _EXTENSION.get('extensionId') != 'legacy_foodstreet':
    fail('CODE_CONFIG_EXTENSION_SCHEMA', 'legacy_foodstreet/extension.json', 'Legacy configuration extension metadata is invalid')
_CONFIG_PROFILE = _EXTENSION['configurationProfile']
SOURCE_SHA256 = _CONFIG_PROFILE['sourceSha256']
TABLE_SHA256 = _CONFIG_PROFILE['tableSha256']
REPRESENTATIVE_ROOT_DISH_ID = _CONFIG_PROFILE['representativeRootDishId']
MAX_TABLE_BYTES = _CONFIG_PROFILE['maxTableBytes']
MAX_SOURCE_BYTES = _CONFIG_PROFILE['maxSourceBytes']
MAX_ROWS = _CONFIG_PROFILE['maxRows']
MAX_INGREDIENTS_PER_ROW = _CONFIG_PROFILE['maxIngredientsPerRow']
MAX_SAFE_INTEGER = _CONFIG_PROFILE['maxSafeInteger']

_DIGITS = re.compile(r'[0-9]+\Z')
SOURCE_SPANS = _CONFIG_PROFILE['sourceSpans']


def validate_module_binding(namespace, modules, context) -> dict:
    """Validate the exact optional source module contract for this extension."""
    from ...code_semantics import NUMBER, Type

    catalog = next((module for module in modules if module.get('targetClass') == 'RecipeCatalog'), None)
    if (namespace != 'Game.Domain.Recovered' or not catalog or catalog.get('_class', {}).get('name') != 'qp'
            or catalog.get('_fields', {}).get('_dishMap') != Type('Map', (NUMBER, Type('Recipe')))
            or context.get('records', {}).get('Recipe') != {'ingredients': Type('Map', (NUMBER, NUMBER))}):
        fail('CODE_CONFIG_MODULE_BINDING', '$', 'Legacy recipe JSON profile requires its exact source class and record/field domain')
    return dict(
        catalogModuleId=catalog['id'],
        ownerId='RecipeJsonConfiguration',
        reportPath='Analysis/Code/recipe-json-configuration.json',
        publicReportKeys=['tableSha256', 'sourceSha256', 'representative'],
        extensionId='legacy_foodstreet',
        scope='legacy-project-specific',
        generatorFiles=list(_CONFIG_PROFILE['generatorFiles']),
    )


def _strict_source_evidence(source: bytes, expected_sha256: str) -> dict:
    if sha(source) != expected_sha256 or expected_sha256 != SOURCE_SHA256:
        fail('CODE_CONFIG_SOURCE_IDENTITY', 'source.js', 'Source bytes do not match the pinned input identity')
    evidence = {}
    for name, contract in SOURCE_SPANS.items():
        offset, length = contract['byteOffset'], contract['byteLength']
        if type(offset) is not int or type(length) is not int or offset < 0 or length <= 0 or offset + length > len(source):
            fail('CODE_CONFIG_SOURCE_CONTRACT', name, 'Pinned source span is outside source bounds')
        span_sha = sha(source[offset:offset + length])
        if span_sha != contract['sha256']:
            fail('CODE_CONFIG_SOURCE_CONTRACT', name, 'Pinned source byte-span hash differs')
        evidence[name] = dict(byteOffset=offset, byteLength=length, sha256=span_sha)
    return dict(sha256=expected_sha256, bytes=len(source), sourceExecuted=False,
                evidence=evidence)


def _number(value, location: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail('CODE_CONFIG_VALUE', location, 'Expected a JSON number; booleans and strings are unsupported')
    if not math.isfinite(value):
        fail('CODE_CONFIG_VALUE', location, 'Non-finite numeric value is unsupported')
    if abs(value) > MAX_SAFE_INTEGER:
        fail('CODE_CONFIG_VALUE', location, 'Number exceeds exact JavaScript integer range')
    return value


def _numeric_key(value: object, location: str, *, weight_key: bool = False) -> int:
    if not isinstance(value, str):
        fail('CODE_CONFIG_KEY', location, 'Expected a string-encoded numeric key')
    token = value.split('_', 1)[0] if weight_key else value
    if not _DIGITS.fullmatch(token):
        fail('CODE_CONFIG_KEY', location, 'Only decimal integer identifiers are supported')
    result = int(token)
    if result > MAX_SAFE_INTEGER:
        fail('CODE_CONFIG_KEY', location, 'Identifier exceeds exact JavaScript integer range')
    return result


def _js_property_keys(value: dict) -> list[str]:
    """ECMAScript for-in order for own JSON object keys (integer indices first)."""
    indices = []
    others = []
    for key in value:
        if isinstance(key, str) and re.fullmatch(r'(?:0|[1-9][0-9]*)', key):
            index = int(key)
            if index <= 4_294_967_294:
                indices.append((index, key))
                continue
        others.append(key)
    indices.sort(key=lambda item: item[0])
    return [key for _, key in indices] + others


def _js_order_row_keys(keys: list[str]) -> list[str]:
    indices = []
    others = []
    for key in keys:
        if re.fullmatch(r'(?:0|[1-9][0-9]*)', key):
            index = int(key)
            if index <= 4_294_967_294:
                indices.append((index, key))
                continue
        others.append(key)
    indices.sort(key=lambda item: item[0])
    return [key for _, key in indices] + others


def _map_rows(document: object) -> tuple[list[dict], dict[int, dict]]:
    if not isinstance(document, dict) or not document or len(document) > MAX_ROWS:
        fail('CODE_CONFIG_TABLE_SHAPE', 'ElementMultiOrderPool', 'Expected a non-empty bounded object keyed by row ID')
    rows = []
    by_dish: dict[int, dict] = {}
    seen_row_ids = set()
    for table_key in _js_order_row_keys(list(document)):
        row = document[table_key]
        row_id = _numeric_key(table_key, f'row[{table_key}]')
        if not isinstance(row, dict):
            fail('CODE_CONFIG_ROW_SHAPE', str(table_key), 'Expected a row object')
        source_id = row.get('id')
        if type(source_id) is not int or source_id != row_id:
            fail('CODE_CONFIG_ROW_ID', str(table_key), 'Object key must match the integer row id')
        if source_id in seen_row_ids:
            fail('CODE_CONFIG_DUPLICATE_ROW', str(source_id), 'Duplicate source row ID')
        seen_row_ids.add(source_id)
        cookware = row.get('elementOrderId')
        if type(cookware) is not int:
            fail('CODE_CONFIG_ROW_SHAPE', str(source_id), 'elementOrderId must be an integer')
        ingredients = row.get('needElements')
        weights = row.get('elementIdWeight')
        if not isinstance(ingredients, dict) or not ingredients or len(ingredients) > MAX_INGREDIENTS_PER_ROW:
            fail('CODE_CONFIG_INGREDIENT_SHAPE', str(source_id), 'needElements must be a non-empty bounded object')
        if not isinstance(weights, dict) or not weights:
            fail('CODE_CONFIG_DISH_SHAPE', str(source_id), 'elementIdWeight must be a non-empty object')
        dish_keys = [_numeric_key(key, f'{source_id}.elementIdWeight.{key}', weight_key=True)
                     for key in _js_property_keys(weights)]
        if len(set(dish_keys)) != len(dish_keys):
            fail('CODE_CONFIG_DUPLICATE_DISH', str(source_id),
                 'elementIdWeight keys repeat a dish prefix after Number conversion')
        dish_id = dish_keys[-1]  # Kp assigns dish on each Map iteration; the last key wins.
        mapped_ingredients = []
        seen_ingredient_ids = set()
        for key in _js_property_keys(ingredients):
            quantity = ingredients[key]
            ingredient_id = _numeric_key(key, f'{source_id}.needElements.{key}')
            if ingredient_id in seen_ingredient_ids:
                fail('CODE_CONFIG_DUPLICATE_INGREDIENT', str(source_id),
                     f'needElements keys collide after Number conversion: {ingredient_id}')
            seen_ingredient_ids.add(ingredient_id)
            mapped_ingredients.append([ingredient_id, _number(quantity, f'{source_id}.needElements.{key}')])
        if dish_id in by_dish:
            fail('CODE_CONFIG_DUPLICATE_DISH', str(dish_id),
                 'Multiple rows map to the same dish; source Map overwrite is ambiguous for this subset')
        duration = _number(row.get('duration'), f'{source_id}.duration')
        cook_type = _number(row.get('cookType'), f'{source_id}.cookType')
        recipe = dict(id=source_id, dish=dish_id, ingredients=mapped_ingredients)
        record = dict(sourceTableKey=table_key, sourceRowId=source_id, cookware= cookware,
                      duration=duration, cookType=cook_type if cook_type > 0 else 1,
                      recipe=recipe)
        rows.append(record)
        by_dish[dish_id] = record
    return rows, by_dish


def _validate_acyclic(by_dish: dict[int, dict]) -> None:
    edges = {dish: [ingredient_id for ingredient_id, _ in record['recipe']['ingredients']
                    if ingredient_id in by_dish]
             for dish, record in by_dish.items()}
    state: dict[int, int] = {}
    for start in sorted(by_dish):
        if state.get(start, 0) != 0:
            continue
        stack = [(start, 0)]
        active = [start]
        active_index = {start: 0}
        state[start] = 1
        while stack:
            dish, index = stack[-1]
            neighbours = edges[dish]
            if index >= len(neighbours):
                stack.pop()
                active.pop()
                active_index.pop(dish)
                state[dish] = 2
                continue
            child = neighbours[index]
            stack[-1] = (dish, index + 1)
            child_state = state.get(child, 0)
            if child_state == 1:
                cycle = active[active_index[child]:] + [child]
                fail('CODE_CONFIG_RECIPE_CYCLE', str(dish), 'Recipe cycle: ' + ' -> '.join(map(str, cycle)))
            if child_state == 0:
                state[child] = 1
                active_index[child] = len(active)
                active.append(child)
                stack.append((child, 0))


def _flatten(root_dish_id: int, by_dish: dict[int, dict]) -> dict:
    if type(root_dish_id) is not int or root_dish_id not in by_dish:
        fail('CODE_CONFIG_ROOT_DISH', str(root_dish_id), 'Root dish ID is not present in the mapped table')
    occurrences = []
    leaves = []
    seen = set()
    recipes = []
    frames = [(root_dish_id, 0)]
    active = {root_dish_id}
    recipes.append(root_dish_id)
    while frames:
        dish, index = frames[-1]
        ingredients = by_dish[dish]['recipe']['ingredients']
        if index >= len(ingredients):
            frames.pop()
            active.remove(dish)
            continue
        ingredient_id = ingredients[index][0]
        frames[-1] = (dish, index + 1)
        if ingredient_id in by_dish:
            if ingredient_id in active:
                fail('CODE_CONFIG_RECIPE_CYCLE', str(dish), 'Reachable recipe cycle detected')
            recipes.append(ingredient_id)
            active.add(ingredient_id)
            frames.append((ingredient_id, 0))
        else:
            occurrences.append(ingredient_id)
            if ingredient_id not in seen:
                seen.add(ingredient_id)
                leaves.append(ingredient_id)
    root_record = by_dish[root_dish_id]
    return dict(rootDishId=root_dish_id, rootSourceRowId=root_record['sourceRowId'],
                expandedRecipeDishIds=recipes, leafOccurrences=occurrences,
                flattenedLeaves=leaves)


def map_payload(table_bytes: bytes, source_bytes: bytes, *, expected_table_sha256: str,
                expected_source_sha256: str, root_dish_id: int = REPRESENTATIVE_ROOT_DISH_ID) -> dict:
    """Validate bytes against caller-supplied source identities and map the finite recipe subset.

    Production callers should use :func:`map_element_multi_order_pool`, which
    pins both SHA-256 values to the frozen source inputs.
    """
    actual_table_sha = sha(table_bytes)
    actual_source_sha = sha(source_bytes)
    if actual_table_sha != expected_table_sha256 or expected_table_sha256 != TABLE_SHA256:
        fail('CODE_CONFIG_TABLE_IDENTITY', 'ElementMultiOrderPool.json', 'Table SHA-256 does not match the pinned source table')
    if actual_source_sha != expected_source_sha256:
        fail('CODE_CONFIG_SOURCE_IDENTITY', 'game.js', 'Source SHA-256 differs from the supplied identity')
    source_evidence = _strict_source_evidence(source_bytes, expected_source_sha256)
    document = load(table_bytes, max_nodes=200_000, max_depth=24)
    rows, by_dish = _map_rows(document)
    _validate_acyclic(by_dish)
    selected = _flatten(root_dish_id, by_dish)
    return dict(status='validated-finite-source-subset', table=dict(sha256=actual_table_sha, bytes=len(table_bytes),
                rowCount=len(rows)), source=source_evidence, mapping=dict(kind='Kp-recipe-index-subset-v1',
                sourceRowOrder='ECMAScript for-in integer-index order then remaining JSON object order',
                mapKeyOrder='ECMAScript for-in order preserved by source Map converter',
                mapKeyConversion='Number(string key)',
                dishSelection='last elementIdWeight key prefix, matching Kp Map iteration assignment',
                ingredientShape='ordered [ingredientId, quantity] pairs', originalConfigIsRuntimeValueSource=True,
                omittedFromRecipeProjection=['cookware', 'duration', 'cookType', 'cookEffect',
                                             'elementIdWeight weights', 'addElementStorage', 'speedUpCost']),
                recipes=rows, representative=selected, sourceExecuted=False)


def map_element_multi_order_pool(table_path, source_path, *, root_dish_id: int = REPRESENTATIVE_ROOT_DISH_ID) -> dict:
    """Read the exact frozen table and source script without executing either."""
    table_path = safe(Path(table_path))
    source_path = safe(Path(source_path))
    table_bytes = read(table_path, max_bytes=MAX_TABLE_BYTES)
    source_bytes = read(source_path, max_bytes=MAX_SOURCE_BYTES)
    return map_payload(table_bytes, source_bytes, expected_table_sha256=TABLE_SHA256,
                       expected_source_sha256=SOURCE_SHA256, root_dish_id=root_dish_id)


def prepare_assets(table_path, source_path, output, *, root_dish_id: int = REPRESENTATIVE_ROOT_DISH_ID) -> dict:
    """Create a fresh staging directory with the original JSON bytes and a typed reader.

    The caller may merge these owned files into a larger Monkey candidate. This
    helper never rewrites the source table into a second data format.
    """
    table_path = safe(Path(table_path))
    source_path = safe(Path(source_path))
    meta_path = safe(table_path.with_name(table_path.name + '.meta'))
    result = map_element_multi_order_pool(table_path, source_path, root_dish_id=root_dish_id)
    table_bytes = read(table_path, max_bytes=MAX_TABLE_BYTES)
    source_bytes = read(source_path, max_bytes=MAX_SOURCE_BYTES)
    meta_bytes = read(meta_path, max_bytes=64 * 1024)
    if sha(table_bytes) != TABLE_SHA256 or sha(source_bytes) != SOURCE_SHA256:
        fail('CODE_CONFIG_SOURCE_CHANGED', str(table_path), 'Frozen source changed after static mapping')
    try:
        meta_text = meta_bytes.decode('utf-8')
    except UnicodeDecodeError:
        fail('CODE_CONFIG_META', str(meta_path), 'Unity meta must be UTF-8')
    match = re.search(r'^guid: ([0-9a-f]{32})\r?$', meta_text, re.MULTILINE)
    if not match or 'fileFormatVersion: 2' not in meta_text:
        fail('CODE_CONFIG_META', str(meta_path), 'Expected the exact Unity text-asset meta identity')
    reader_path = safe(Path(__file__).with_name('RecipeJsonConfiguration.cs'))
    reader_bytes = read(reader_path, max_bytes=256 * 1024)
    from ...targets.unity import guid
    reader_guid = guid('foodstreet-recipe-config-v1', 'RecipeJsonConfiguration')
    out = new_output(output, [table_path, source_path, meta_path, reader_path])
    project_files = {
        'Assets/Game/Content/Config/Base/ElementMultiOrderPool.json': table_bytes,
        'Assets/Game/Content/Config/Base/ElementMultiOrderPool.json.meta': meta_bytes,
        'Assets/Game/Domain/Recovered/RecipeJsonConfiguration.cs': reader_bytes,
        'Assets/Game/Domain/Recovered/RecipeJsonConfiguration.cs.meta':
            ('fileFormatVersion: 2\nguid: ' + reader_guid + '\n').encode('utf-8'),
    }
    for relative, raw in project_files.items():
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    evidence = dict(schemaVersion=1, status='prepared-fresh-assets-not-unity-validated',
                    sourceProfile='foodstreet-main-js-element-multi-order-pool-v1',
                    table=dict(path=table_path.name, sha256=TABLE_SHA256, bytes=len(table_bytes),
                               runtimeDataAsset='Assets/Game/Content/Config/Base/ElementMultiOrderPool.json',
                               originalBytesCopied=True, originalMetaGuid=match.group(1)),
                    source=dict(path=source_path.name, sha256=SOURCE_SHA256, bytes=len(source_bytes),
                                sourceExecuted=False, evidence=result['source']['evidence']),
                    reader=dict(path='Assets/Game/Domain/Recovered/RecipeJsonConfiguration.cs',
                                sha256=sha(reader_bytes), metaGuid=reader_guid,
                                namespace='Game.Domain.Recovered',
                                outputType='OrderedMap<double,Recipe>',
                                recoveredFullKpOrCookEffect=False),
                    mapping=result['mapping'], representative=result['representative'],
                    validation=dict(staticSourceMapping='pass', unityCompilation='not_run',
                                    unityTextAssetReadback='not_run',
                                    originalJsonIsSoleRuntimeNumberSource=True))
    report_path = out / 'Analysis/Code/recipe-json-configuration.json'
    write_json(report_path, evidence)
    inventory = [dict(path=relative, sha256=sha(raw), bytes=len(raw), owner='RecipeJsonConfiguration')
                 for relative, raw in sorted(project_files.items())]
    return dict(status=evidence['status'], output=str(out), report=str(report_path),
                tableSha256=TABLE_SHA256, sourceSha256=SOURCE_SHA256, files=inventory,
                representative=result['representative'])
