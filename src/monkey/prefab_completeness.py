"""Independent source-to-IR structural accounting for Cocos 2.4.15 Prefabs.

This module reports identity coverage only. It does not assert native, runtime,
visual, or field-semantic completeness.
"""
from copy import deepcopy


SUPPORTED = {'cocos-2.4.15-bundle', 'cocos-2.4.15-project'}
NODE_TYPES = {'cc.Node', 'cc.Scene'}
PREFAB_KINDS = {'cc.Prefab', 'cc.SceneAsset'}


class FieldError(ValueError):
    pass


def _same(left, right):
    """JSON-semantic equality (notably, bool is distinct from integer)."""
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    return left == right


def _reference(value, namespace, object_count):
    if value is None:
        return None
    if isinstance(value, dict) and isinstance(value.get('__sourceId__'), str):
        return value['__sourceId__']
    if isinstance(value, dict) and type(value.get('__id__')) is int:
        index = value['__id__']
        if not 0 <= index < object_count:
            raise FieldError(f'object reference index {index} is outside source document')
        return namespace + '#' + str(index)
    if isinstance(value, dict) and isinstance(value.get('__uuid__'), str):
        return namespace.split(':', 1)[0] + ':' + value['__uuid__']
    raise FieldError('expected null or a valid source object/resource reference')


def _vector(value, keys, default):
    if value is None:
        return list(default)
    if isinstance(value, dict) and '__value_type__' in value:
        values = value.get('values')
        if not isinstance(values, list):
            raise FieldError('typed vector has no values array')
        if len(keys) == 4 and len(values) == 1 and type(values[0]) is int:
            packed = values[0]
            return [(packed >> shift) & 255 for shift in (0, 8, 16, 24)]
        if len(values) != len(keys) or any(type(x) not in (int, float) for x in values):
            raise FieldError('typed vector has invalid numeric values')
        return values
    if isinstance(value, dict):
        return [value.get(k, d) for k, d in zip(keys, default)]
    raise FieldError('expected a serialized vector')


def _semantic_expectations(source, namespace, object_count):
    """Independent source-field projection into the current conversion IR."""
    typ = source.get('__type__')
    source_fields = {}
    unmapped_semantics = set()

    def add(prop, source_keys, value):
        for key in source_keys:
            source_fields[key] = prop
        return (prop, value, source_keys)

    checks = [
        add('node', ['node'], _reference(source.get('node'), namespace, object_count)),
        add('enabled', ['_enabled'], source.get('_enabled', True)),
        add('materials', ['_materials'], [_reference(v, namespace, object_count)
                                          for v in source.get('_materials', []) if v]),
    ]
    if typ == 'cc.Sprite':
        checks += [add('spriteFrame', ['_spriteFrame'], _reference(source.get('_spriteFrame'), namespace, object_count)),
                   add('mode', ['_type'], source.get('_type', 0)),
                   add('sizeMode', ['_sizeMode'], source.get('_sizeMode', 0)),
                   add('trim', ['_isTrimmedMode'], source.get('_isTrimmedMode', True))]
        unmapped_semantics |= {'_fillType', '_fillCenter', '_fillStart', '_fillRange', '_atlas'}
    elif typ == 'cc.Label':
        if '_overflow' in source and '_N$overflow' in source and source['_overflow'] != source['_N$overflow']:
            raise FieldError('LABEL_OVERFLOW_ALIAS_CONFLICT: _overflow and _N$overflow differ')
        flags = source.get('_styleFlags', 0)
        if type(flags) is not int:
            raise FieldError('_styleFlags must be an integer bit field')
        overflow_keys = [k for k in ('_overflow', '_N$overflow') if k in source]
        checks += [add('text', [k for k in ('_string', '_N$string') if k in source],
                       source.get('_string', source.get('_N$string', ''))),
                   add('font', ['_N$file'], _reference(source.get('_N$file'), namespace, object_count)),
                   add('fontSize', ['_fontSize'], source.get('_fontSize', 40)),
                   add('lineHeight', ['_lineHeight'], source.get('_lineHeight', 40)),
                   add('horizontalAlign', [k for k in ('_N$horizontalAlign', '_horizontalAlign') if k in source],
                       source.get('_N$horizontalAlign', source.get('_horizontalAlign', 0))),
                   add('verticalAlign', [k for k in ('_N$verticalAlign', '_verticalAlign') if k in source],
                       source.get('_N$verticalAlign', source.get('_verticalAlign', 0))),
                   add('bold', ['_styleFlags'], bool(flags & 1)), add('italic', ['_styleFlags'], bool(flags & 2)),
                   add('underline', ['_styleFlags'], bool(flags & 4)),
                   add('spacing', ['_spacingX'], source.get('_spacingX', 0)),
                   add('systemFont', ['_isSystemFontUsed'], source.get('_isSystemFontUsed', True)),
                   add('overflow', overflow_keys, source.get('_overflow', source.get('_N$overflow', 0))),
                   add('wrap', ['_enableWrapText'], source.get('_enableWrapText', True))]
        if '_string' in source and '_N$string' in source:
            source_fields['_N$string'] = None  # lower-priority alias is retained, not independently applied
        if '_N$horizontalAlign' in source and '_horizontalAlign' in source:
            source_fields['_horizontalAlign'] = None
        if '_N$verticalAlign' in source and '_verticalAlign' in source:
            source_fields['_verticalAlign'] = None
        unmapped_semantics |= {'_fontFamily', '_N$fontFamily', '_cacheMode'}
    elif typ == 'cc.Widget':
        checks += [add('flags', ['_alignFlags'], source.get('_alignFlags', 0)),
                   add('target', ['_target'], _reference(source.get('_target'), namespace, object_count)),
                   add('margins', ['_left', '_bottom', '_right', '_top'],
                       [source.get(k, 0) for k in ('_left', '_bottom', '_right', '_top')]),
                   add('absolute', ['_isAbsLeft', '_isAbsBottom', '_isAbsRight', '_isAbsTop'],
                       [source.get(k, True) for k in ('_isAbsLeft', '_isAbsBottom', '_isAbsRight', '_isAbsTop')]),
                   add('alignMode', ['alignMode'], source.get('alignMode', 1)),
                   add('center', ['_horizontalCenter', '_verticalCenter'],
                       [source.get('_horizontalCenter', 0), source.get('_verticalCenter', 0)]),
                   add('centerAbsolute', ['_isAbsHorizontalCenter', '_isAbsVerticalCenter'],
                       [source.get('_isAbsHorizontalCenter', True), source.get('_isAbsVerticalCenter', True)])]
        unmapped_semantics |= {'_originalWidth', '_originalHeight'}
    elif typ == 'cc.Button':
        events = []
        for ordinal, event in enumerate(source.get('clickEvents', []) or []):
            if not isinstance(event, dict) or '__id__' in event:
                events.append(dict(status='unresolved_source_event', sourceIndex=ordinal,
                                   eventReference=_reference(event, namespace, object_count) if isinstance(event, dict) else None))
            else:
                events.append(dict(target=_reference(event.get('target'), namespace, object_count),
                                   component=event.get('_componentId'), handler=event.get('handler'),
                                   customData=event.get('customEventData', '')))
        checks += [add('target', ['_N$target'], _reference(source.get('_N$target'), namespace, object_count)),
                   add('transition', ['_N$transition'], source.get('_N$transition', 0)),
                   add('zoomScale', ['zoomScale'], source.get('zoomScale', 1.2)),
                   add('duration', ['duration'], source.get('duration', .1)),
                   add('interactable', ['interactable'], source.get('interactable', True)),
                   add('events', ['clickEvents'], events)]
        unmapped_semantics |= {'_N$normalColor', '_N$pressedColor', '_N$hoverColor', '_N$disabledColor',
                               '_N$normalSprite', '_N$pressedSprite', '_N$hoverSprite', '_N$disabledSprite',
                               '_normalMaterial', '_pressedMaterial', '_hoverMaterial', '_disabledMaterial',
                               '_N$autoGrayEffect', '_N$enableAutoGrayEffect'}
    elif typ == 'cc.Mask':
        mask_keys = [k for k in ('_type', '_N$type') if k in source]
        inverted_keys = [k for k in ('_inverted', '_N$inverted') if k in source]
        checks += [add('maskType', mask_keys, source.get('_type', source.get('_N$type', 0))),
                   add('inverted', inverted_keys, source.get('_inverted', source.get('_N$inverted', False)))]
        unmapped_semantics |= {'_alphaThreshold', '_N$alphaThreshold', '_spriteFrame', '_segments'}
    elif typ == 'cc.ScrollView':
        checks += [add('content', ['_N$content'], _reference(source.get('_N$content'), namespace, object_count)),
                   add('horizontal', ['horizontal'], source.get('horizontal', True)),
                   add('vertical', ['vertical'], source.get('vertical', True))]
        unmapped_semantics |= {'_N$horizontalScrollBar', '_N$verticalScrollBar', 'bounceDuration', 'brake',
                               'elastic', 'inertia', 'scrollEvents', 'cancelInnerEvents'}
    elif typ == 'cc.ProgressBar':
        checks += [add('barSprite', ['_N$barSprite'], _reference(source.get('_N$barSprite'), namespace, object_count)),
                   add('progress', ['_N$progress'], source.get('_N$progress')),
                   add('totalLength', ['_N$totalLength'], source.get('_N$totalLength')),
                   add('progressMode', ['_N$mode'], source.get('_N$mode')),
                   add('progressReverse', ['_N$reverse'], source.get('_N$reverse'))]
    elif typ == 'cc.Layout':
        if '_N$cellSize' in source and '_cellSize' in source and _vector(source['_N$cellSize'], ['width','height'], [40,40]) != _vector(source['_cellSize'], ['width','height'], [40,40]):
            raise FieldError('CONFLICTING_LAYOUT_CELL_SIZE: _N$cellSize and _cellSize differ')
        cell_key = '_N$cellSize' if '_N$cellSize' in source else '_cellSize'
        checks += [add('layoutType', ['_N$layoutType'], source.get('_N$layoutType', 0)),
                   add('resize', ['_resize'], source.get('_resize', 0)),
                   add('spacingXY', ['_N$spacingX', '_N$spacingY'], [source.get('_N$spacingX', 0), source.get('_N$spacingY', 0)]),
                   add('padding', ['_N$paddingLeft', '_N$paddingBottom', '_N$paddingRight', '_N$paddingTop'],
                       [source.get(k, 0) for k in ('_N$paddingLeft', '_N$paddingBottom', '_N$paddingRight', '_N$paddingTop')]),
                   add('horizontalDirection', ['_N$horizontalDirection'], source.get('_N$horizontalDirection', 0)),
                   add('verticalDirection', ['_N$verticalDirection'], source.get('_N$verticalDirection', 1)),
                   add('startAxis', ['_N$startAxis'], source.get('_N$startAxis', 0)),
                   add('cellSizeFromSource', [k for k in ('_N$cellSize', '_cellSize') if k in source],
                       ('_N$cellSize' in source or '_cellSize' in source)),
                   add('cellSize', [cell_key] if cell_key in source else [],
                       _vector(source.get('_N$cellSize', source.get('_cellSize')), ['width','height'], [40,40])),
                   add('affectedByScale', ['_affectedByScale'], source.get('_affectedByScale', False)),
                   add('alignCross', ['_isAlign'], source.get('_isAlign', False)),
                   add('constraint', ['_constraint'], source.get('_constraint', 0)),
                   add('constraintCount', ['_constraintNum'], source.get('_constraintNum', 2))]
        if '_N$cellSize' in source and '_cellSize' in source:
            source_fields['_cellSize'] = None
        unmapped_semantics.add('_layoutSize')
    elif typ == 'cc.Animation':
        checks += [add('clips', ['_clips'], [_reference(v, namespace, object_count) for v in source.get('_clips', []) if v is not None]),
                   add('defaultClip', ['_defaultClip'], _reference(source.get('_defaultClip'), namespace, object_count)),
                   add('playOnLoad', ['playOnLoad'], source.get('playOnLoad', False))]
    elif typ == 'cc.LabelOutline':
        checks += [add('width', ['_width'], source.get('_width', 1)),
                   add('outlineColor', ['_color'], _vector(source.get('_color'), ['r','g','b','a'], [255]*4))]
    else:
        return [], source_fields, unmapped_semantics
    return checks, source_fields, unmapped_semantics


def _node_expectations(source, source_id, namespace, object_count):
    source_fields = {}
    checks = []

    def add(prop, key, expected, semantic=None):
        source_fields.setdefault(key, []).append((prop, semantic))
        checks.append((prop, expected, [key], semantic))

    if '_name' in source:
        add('name', '_name', source['_name'])
    if '_active' in source:
        add('active', '_active', source['_active'])
    if '_parent' in source:
        add('parent', '_parent', _reference(source['_parent'], namespace, object_count), 'parent_reference')
    if '_children' in source:
        children = source['_children']
        if not isinstance(children, list):
            raise FieldError('_children must be an array')
        refs = []
        for ordinal, child in enumerate(children):
            if isinstance(child, dict) and child.get('__type__') == 'cc.Node':
                suffix = source_id.split('#', 1)[1]
                refs.append(namespace + '#' + suffix + '/_children/' + str(ordinal))
            else:
                refs.append(_reference(child, namespace, object_count))
        add('children', '_children', refs, 'ordered_child_references')
    if '_trs' in source:
        raw = source['_trs']
        values = raw.get('array', raw.get('values', [])) if isinstance(raw, dict) else raw if isinstance(raw, list) else None
        if isinstance(values, list) and len(values) == 1 and isinstance(values[0], list):
            values = values[0]
        if not isinstance(values, list) or len(values) != 10 or any(type(x) not in (int, float) for x in values):
            raise FieldError('_trs does not provide ten numeric position/quaternion/scale values')
        add('position', '_trs', values[:3], 'position')
        add('rotation', '_trs', values[3:7], 'quaternion')
        add('scale', '_trs', values[7:10], 'scale')
    if '_contentSize' in source and source['_contentSize'] is not None:
        add('size', '_contentSize', _vector(source['_contentSize'], ['width', 'height'], [0, 0]), 'size')
    if '_anchorPoint' in source and source['_anchorPoint'] is not None:
        add('anchor', '_anchorPoint', _vector(source['_anchorPoint'], ['x', 'y'], [.5, .5]), 'pivot')
    if '_color' in source and source['_color'] is not None:
        add('color', '_color', _vector(source['_color'], ['r', 'g', 'b', 'a'], [255]*4), 'color')
    if '_opacity' in source:
        add('opacity', '_opacity', source['_opacity'])

    unmapped = {'_zIndex', '_eulerAngles', '_skewX', '_skewY', '_groupIndex', 'groupIndex'}
    return checks, source_fields, unmapped


def _check_node_fields(source_record, ir_record, namespace, object_count):
    source = {field['name']: field['value'] for field in source_record['fields']}
    unverified_properties = []
    if '_trs' not in source:
        unverified_properties += ['position', 'rotation', 'scale']
    if source.get('_contentSize') is None:
        unverified_properties.append('size')
    if source.get('_anchorPoint') is None:
        unverified_properties.append('anchor')
    if '_active' not in source:
        unverified_properties.append('active')
    if '_parent' not in source:
        unverified_properties.append('parent')
    if '_children' not in source:
        unverified_properties.append('children')
    try:
        expectations, source_fields, unmapped = _node_expectations(source, source_record['sourceId'], namespace, object_count)
    except (FieldError, TypeError, ValueError, KeyError, IndexError) as error:
        detail = str(error)
        fields = [dict(sourceField=name, targetProperty=None,
                       status='unmapped_semantics' if name in {'_zIndex', '_eulerAngles', '_skewX', '_skewY', '_groupIndex', 'groupIndex'} else 'error',
                       error=detail) for name in sorted(source)]
        diag = dict(code='NODE_FIELD_SOURCE_INVALID', sourceId=source_record['sourceId'], message=detail)
        return dict(status='failed', checks=[dict(targetProperty=None, sourceFields=[], expected=None, actual=None,
                     status='error', error=detail, code='NODE_FIELD_SOURCE_INVALID')], sourceFields=fields,
                    unverifiedProperties=[]), [diag]
    checks = []
    for prop, expected, keys, semantic in expectations:
        present = isinstance(ir_record, dict) and prop in ir_record
        actual = ir_record.get(prop) if present else None
        status = 'match' if present and _same(expected, actual) else 'mismatch'
        checks.append(dict(targetProperty=prop, semantic=semantic, sourceFields=keys,
                           expected=deepcopy(expected), actual=deepcopy(actual), status=status))
    check_by_source = {key: [c for c in checks if key in c['sourceFields']] for key in source_fields}
    fields = []
    for name in sorted(source):
        if name in unmapped:
            fields.append(dict(sourceField=name, targetProperty=None, status='unmapped_semantics'))
        elif name not in source_fields:
            fields.append(dict(sourceField=name, targetProperty=None, status='unverified'))
        else:
            props = source_fields[name]
            related = check_by_source.get(name, [])
            field_status = 'mismatch' if any(c['status'] != 'match' for c in related) else 'match'
            fields.append(dict(sourceField=name, targetProperties=[p for p, _ in props],
                               semantics=[s for _, s in props], status=field_status))
    if any(c['status'] != 'match' for c in checks):
        status = 'failed'
    elif not checks or unverified_properties or any(f['status'] in ('unverified', 'unmapped_semantics') for f in fields):
        status = 'partial'
    else:
        status = 'checked'
    diagnostics = [dict(code='NODE_IR_MISMATCH', sourceId=source_record['sourceId'],
                         message=f"IR node property {c['targetProperty']} differs from serialized source value")
                   for c in checks if c['status'] == 'mismatch']
    return dict(status=status, checks=checks, sourceFields=fields, unverifiedProperties=unverified_properties), diagnostics


def _check_fields(source_record, ir_record, namespace, object_count):
    source = {field['name']: field['value'] for field in source_record['fields']}
    source_fields = {}
    try:
        expectations, source_fields, unmapped_semantics = _semantic_expectations(source, namespace, object_count)
    except (FieldError, TypeError, ValueError, KeyError, IndexError) as error:
        detail = str(error)
        code = 'FIELD_SOURCE_INVALID'
        if detail.startswith('LABEL_OVERFLOW_ALIAS_CONFLICT'):
            code = 'LABEL_OVERFLOW_ALIAS_CONFLICT'
        elif detail.startswith('CONFLICTING_LAYOUT_CELL_SIZE'):
            code = 'CONFLICTING_LAYOUT_CELL_SIZE'
        return dict(status='failed', checks=[dict(targetProperty=None, sourceFields=[], expected=None,
                     actual=None, status='error', error=detail, code=code)],
                    sourceFields=[dict(sourceField=name, targetProperty=source_fields.get(name), status='error', error=detail)
                                  for name in sorted(source)]), [dict(code=code, sourceId=source_record['sourceId'], message=detail)]
    checks = []
    for prop, expected, keys in expectations:
        actual_present = isinstance(ir_record, dict) and prop in ir_record
        actual = ir_record.get(prop) if actual_present else None
        status = 'match' if actual_present and _same(expected, actual) else 'mismatch'
        checks.append(dict(targetProperty=prop, sourceFields=list(keys), expected=deepcopy(expected),
                           actual=deepcopy(actual), status=status))
    check_by_prop = {c['targetProperty']: c for c in checks}
    fields = []
    for name in sorted(source):
        if name in unmapped_semantics:
            fields.append(dict(sourceField=name, targetProperty=None, status='unmapped_semantics'))
        elif name not in source_fields:
            fields.append(dict(sourceField=name, targetProperty=None, status='unverified'))
        elif source_fields[name] is None:
            fields.append(dict(sourceField=name, targetProperty=None, status='unmapped_semantics',
                               note='lower-precedence serialized alias is retained but not independently applied'))
        else:
            check = check_by_prop.get(source_fields[name])
            fields.append(dict(sourceField=name, targetProperty=source_fields[name],
                               status=check['status'] if check else 'unverified'))
    if any(c['status'] != 'match' for c in checks):
        status = 'failed'
    elif not checks or any(f['status'] in ('unverified', 'unmapped_semantics') for f in fields):
        status = 'partial'
    else:
        status = 'checked'
    diagnostics = [dict(code='FIELD_IR_MISMATCH', sourceId=source_record['sourceId'],
                        message=f"IR property {check['targetProperty']} differs from independently projected source value")
                   for check in checks if check['status'] == 'mismatch']
    return dict(status=status, checks=checks, sourceFields=fields), diagnostics


def audit(source_manifest: dict, ir: dict, selected_source_ids: list[str]) -> dict:
    """Return a JSON-serializable structural completeness ledger.

    Source identity rules mirror normalize.expand_nodes/component_ir: object
    references use ``assetSourceId#integerIndex``; inline child Nodes use
    ``#parent/_children/ordinal`` and inline components use
    ``#node/components/ordinal``.
    """
    diagnostics = []

    def diag(code, identity, message):
        diagnostics.append(dict(code=code, sourceId=identity, message=message))

    profile = source_manifest.get('sourceProfile')
    if profile not in SUPPORTED:
        return dict(status='rejected', scope='structure_accounting_only',
                    sourceNodes=0, sourceComponents=0, mapped=0, unmapped=0,
                    unknown=0, diagnostics=[dict(code='UNSUPPORTED_SOURCE_PROFILE', sourceId=None,
                    message=f'Expected Cocos 2.4.15 bundle/project; got {profile!r}')],
                    nodes=[], components=[])

    if not isinstance(selected_source_ids, list):
        diag('INVALID_SELECTION', None, 'selected_source_ids must be a list of source IDs')
        requested = []
    else:
        requested = selected_source_ids
        if not requested:
            diag('EMPTY_SELECTION', None, 'At least one sourceId must be selected for accounting')
    selected = set()
    for sid in requested:
        if not isinstance(sid, str) or not sid:
            diag('INVALID_SELECTED_SOURCE_ID', None, 'Selection entries must be non-empty source IDs')
        elif sid in selected:
            diag('DUPLICATE_SELECTED_SOURCE_ID', sid, 'Selection contains this source ID more than once')
        else:
            selected.add(sid)

    assets = source_manifest.get('assets', [])
    by_asset = {}
    for asset in assets if isinstance(assets, list) else []:
        if not isinstance(asset, dict) or not isinstance(asset.get('sourceId'), str):
            diag('INVALID_SOURCE_ASSET', None, 'Asset lacks a string sourceId')
            continue
        sid = asset['sourceId']
        if sid in by_asset:
            diag('DUPLICATE_SOURCE_ASSET_ID', sid, 'Source manifest repeats an asset sourceId')
        else:
            by_asset[sid] = asset
    for sid in sorted(selected - by_asset.keys()):
        diag('SELECTED_SOURCE_MISSING', sid, 'Selected sourceId is absent from the manifest')

    ir_nodes = {}
    ir_components = {}
    def in_selected_scope(identity):
        return isinstance(identity, str) and any(identity == sid or identity.startswith(sid + '#') for sid in selected)

    for key, records in (('nodes', ir.get('nodes', [])), ('components', ir.get('components', []))):
        table = ir_nodes if key == 'nodes' else ir_components
        for record in records if isinstance(records, list) else []:
            if not isinstance(record, dict) or not isinstance(record.get('sourceId'), str):
                # Malformed records cannot be attributed to a selected asset.
                # Keep the audit bounded to the selected source scope.
                if selected:
                    diag('INVALID_IR_IDENTITY', None, f'IR {key} record lacks a string sourceId')
                continue
            identity = record['sourceId']
            if not in_selected_scope(identity):
                continue
            if identity in table:
                diag('DUPLICATE_IR_IDENTITY', identity, f'IR repeats {key} sourceId')
            table[identity] = record

    source_nodes, source_components = [], []
    source_component_by_id = {}
    for sid in sorted(selected):
        asset = by_asset.get(sid)
        if not asset or asset.get('kind') not in PREFAB_KINDS:
            if asset:
                diag('SELECTED_SOURCE_NOT_PREFAB', sid, 'Selected asset is not a Prefab/SceneAsset')
            continue
        document = asset.get('document')
        objects = document.get('instances') if isinstance(document, dict) else None
        if not isinstance(objects, list):
            diag('SOURCE_DOCUMENT_INVALID', sid, 'Expected document.instances object array')
            continue

        visited_nodes = {}

        def object_at(index):
            if type(index) is not int or index < 0 or index >= len(objects):
                return None
            value = objects[index]
            return value if isinstance(value, dict) else None

        def visit_node(index, node, identity):
            # The source identity can be reached through the object table scan
            # and through one or more parent child edges. Those are references
            # to the same declaration when they resolve to the same object
            # index. Only a different declaration claiming the same identity
            # is a duplicate source identity.
            declaration = ('object', index) if type(index) is int and index >= 0 else ('inline', identity)
            previous = visited_nodes.get(identity)
            if previous is not None:
                if previous == declaration:
                    return
                diag('DUPLICATE_SOURCE_NODE_IDENTITY', identity,
                     'Distinct source node declarations claim the same source identity')
                return
            visited_nodes[identity] = declaration
            refs = node.get('_components', [])
            source_nodes.append(dict(sourceId=identity, sourceAssetId=sid, sourceType=node.get('__type__'),
                                     fields=[dict(name=k, value=deepcopy(v), traceability='unverified') for k, v in sorted(node.items())],
                                     componentRefs=[]))
            node_entry = source_nodes[-1]
            seen_refs = set()
            if not isinstance(refs, list):
                diag('INVALID_COMPONENT_LIST', identity, 'Node._components is not an array')
                refs = []
            for ordinal, ref in enumerate(refs):
                edge_id = f'{identity}/_components/{ordinal}'
                if ref is None:
                    diag('EMPTY_COMPONENT_REFERENCE', edge_id, 'Null Node._components entry is not a component')
                    node_entry['componentRefs'].append(dict(edgeId=edge_id, target=None, status='invalid'))
                    continue
                inline = isinstance(ref, dict) and isinstance(ref.get('__type__'), str)
                if inline:
                    comp = ref
                    comp_id = f'{identity.split("#",1)[1]}/components/{ordinal}'
                    comp_id = sid + '#' + comp_id
                elif isinstance(ref, dict) and type(ref.get('__id__')) is int:
                    comp_index = ref['__id__']
                    comp = object_at(comp_index)
                    comp_id = sid + '#' + str(comp_index)
                    if comp is None:
                        diag('DANGLING_COMPONENT_REFERENCE', edge_id, f'__id__ {comp_index} is not a source object')
                        node_entry['componentRefs'].append(dict(edgeId=edge_id, target=comp_id, status='invalid'))
                        continue
                else:
                    diag('INVALID_COMPONENT_REFERENCE', edge_id, 'Expected exact integer __id__ or typed inline component')
                    node_entry['componentRefs'].append(dict(edgeId=edge_id, target=None, status='invalid'))
                    continue
                if comp_id in seen_refs:
                    diag('DUPLICATE_COMPONENT_REFERENCE', edge_id, f'Component {comp_id} is referenced more than once by this Node')
                seen_refs.add(comp_id)
                ctype = comp.get('__type__')
                if comp_id not in source_component_by_id:
                    source_component_by_id[comp_id] = dict(sourceId=comp_id, sourceAssetId=sid, sourceType=ctype,
                                              known=ctype in {'cc.Sprite','cc.Label','cc.Button','cc.Widget','cc.Layout',
                                                              'cc.Mask','cc.ScrollView','cc.ProgressBar','cc.Animation','cc.LabelOutline'},
                                                           inline=inline,
                                                           fields=[dict(name=k, value=deepcopy(v), traceability='unverified') for k, v in sorted(comp.items())],
                                                           referenceEdges=[])
                    source_components.append(source_component_by_id[comp_id])
                source_component_by_id[comp_id]['referenceEdges'].append(dict(fromNode=identity, edgeId=edge_id))
                node_entry['componentRefs'].append(dict(edgeId=edge_id, target=comp_id, status='enumerated'))
            children = node.get('_children', [])
            if not isinstance(children, list):
                diag('INVALID_CHILD_LIST', identity, 'Node._children is not an array')
                return
            for ordinal, child_ref in enumerate(children):
                if isinstance(child_ref, dict) and isinstance(child_ref.get('__type__'), str) and child_ref.get('__type__') == 'cc.Node':
                    child, child_id = child_ref, f'{identity.split("#",1)[1]}/_children/{ordinal}'
                    child_id = sid + '#' + child_id
                elif isinstance(child_ref, dict) and type(child_ref.get('__id__')) is int:
                    child = object_at(child_ref['__id__']); child_id = sid + '#' + str(child_ref['__id__'])
                else:
                    continue
                if isinstance(child, dict) and child.get('__type__') in NODE_TYPES:
                    visit_node(child_ref.get('__id__') if isinstance(child_ref, dict) and type(child_ref.get('__id__')) is int else -1,
                               child, child_id)

        root = document.get('root')
        if type(root) is int:
            root_obj = object_at(root)
        elif isinstance(root, dict) and type(root.get('__id__')) is int:
            root = root['__id__']; root_obj = object_at(root)
        else:
            root_obj = None
        # Enumerate all serialized Nodes, including detached records, so no source
        # Node disappears from the denominator merely because hierarchy is broken.
        for i, obj in enumerate(objects):
            if isinstance(obj, dict) and obj.get('__type__') in NODE_TYPES:
                visit_node(i, obj, sid + '#' + str(i))

    nodes_out, components_out = [], []
    source_node_ids = {record['sourceId'] for record in source_nodes}
    source_component_ids = {record['sourceId'] for record in source_components}
    for identity in sorted(set(ir_nodes) - source_node_ids):
        diag('IR_NODE_WITHOUT_SOURCE', identity, 'IR node identity is outside the selected source denominator')
    for identity in sorted(set(ir_components) - source_component_ids):
        diag('IR_COMPONENT_WITHOUT_SOURCE', identity, 'IR component identity is outside the selected source denominator')
    mapped = unmapped = unknown = 0
    node_semantic_counts = dict(checked=0, match=0, mismatch=0, error=0,
                                unmapped_semantics=0, unverified=0)
    semantic_counts = dict(checked=0, match=0, mismatch=0, error=0,
                           unmapped_semantics=0, unverified=0)
    for record in source_nodes:
        hit = ir_nodes.get(record['sourceId'])
        record['irMapping'] = 'mapped' if hit else 'unmapped'
        record['irFields'] = [] if not hit else sorted(hit.keys())
        source_asset = by_asset.get(record['sourceAssetId'], {})
        document = source_asset.get('document', {}) if isinstance(source_asset, dict) else {}
        instances = document.get('instances', []) if isinstance(document, dict) else []
        node_check, node_diagnostics = _check_node_fields(record, hit, record['sourceAssetId'],
                                                           len(instances) if isinstance(instances, list) else 0)
        record['fieldCheck'] = node_check
        record['fieldTraceability'] = node_check['sourceFields']
        diagnostics.extend(node_diagnostics)
        for check in node_check['checks']:
            node_semantic_counts['checked'] += 1
            node_semantic_counts[check['status']] += 1
        for field in node_check['sourceFields']:
            if field['status'] in ('unmapped_semantics', 'unverified', 'error', 'mismatch'):
                node_semantic_counts[field['status']] += 1
        node_semantic_counts['unverified'] += len(node_check.get('unverifiedProperties', []))
        mapped += bool(hit); unmapped += not bool(hit)
        nodes_out.append(record)
    for record in source_components:
        hit = ir_components.get(record['sourceId'])
        record['irMapping'] = 'mapped' if hit else 'unmapped'
        record['irFields'] = [] if not hit else sorted(hit.keys())
        source_asset = by_asset.get(record['sourceAssetId'], {})
        document = source_asset.get('document', {}) if isinstance(source_asset, dict) else {}
        instances = document.get('instances', []) if isinstance(document, dict) else []
        field_check, field_diagnostics = _check_fields(record, hit, record['sourceAssetId'],
                                                        len(instances) if isinstance(instances, list) else 0)
        record['fieldCheck'] = field_check
        record['fieldTraceability'] = field_check['sourceFields']
        diagnostics.extend(field_diagnostics)
        for check in field_check['checks']:
            semantic_counts['checked'] += 1
            semantic_counts[check['status']] += 1
        for field in field_check['sourceFields']:
            if field['status'] in ('unmapped_semantics', 'unverified'):
                semantic_counts[field['status']] += 1
        mapped += bool(hit); unmapped += not bool(hit)
        unknown += not record['known']
        components_out.append(record)
    diagnostics.sort(key=lambda d: (str(d.get('sourceId')), d['code'], d['message']))
    nodes_out.sort(key=lambda x: x['sourceId']); components_out.sort(key=lambda x: x['sourceId'])
    return dict(status='structure_accounting_only', scope='structure_accounting_only', sourceNodes=len(nodes_out),
                sourceComponents=len(components_out), mapped=mapped, unmapped=unmapped, unknown=unknown,
                semanticAccounting=semantic_counts, nodeFieldAccounting=node_semantic_counts,
                diagnostics=diagnostics, nodes=nodes_out, components=components_out)
