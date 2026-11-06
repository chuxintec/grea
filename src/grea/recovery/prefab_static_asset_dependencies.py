"""Deterministic source-Prefab dependency ordering for first-pass native generation.

This module reads only normalized sourcePrefab, prefabInstances, and typed static
field-binding records. It does not infer references from arbitrary JSON values.
"""
from __future__ import annotations

from collections import defaultdict
import heapq


class PrefabDependencyError(ValueError):
    def __init__(self, code: str, details: dict):
        self.code = code
        self.details = details
        super().__init__(f'{code}: {details}')


def _prefab_references(field: dict, path: str):
    """Yield exact, typed cc.Prefab references from one field and nested records."""
    declared = field.get('sourceDeclaredType')
    storage = field.get('storageType')

    if declared == 'cc.Prefab':
        if field.get('nullExpected') is True:
            return
        if storage != 'UnityEngine.Object':
            yield {'problem': 'prefab_reference_storage_mismatch', 'fieldPath': path,
                   'sourceDeclaredType': declared, 'storageType': storage}
            return
        target = field.get('refValue')
        if isinstance(target, str) and target:
            yield {'target': target, 'fieldPath': path, 'sourceDeclaredType': declared}
        else:
            yield {'problem': 'prefab_reference_id_missing', 'fieldPath': path,
                   'sourceDeclaredType': declared}
        return

    if declared == '[cc.Prefab]':
        if storage != 'UnityEngine.Object[]':
            yield {'problem': 'prefab_reference_array_storage_mismatch', 'fieldPath': path,
                   'sourceDeclaredType': declared, 'storageType': storage}
            return
        if field.get('nullExpected') is True:
            return
        refs = field.get('refValues')
        if not isinstance(refs, list):
            yield {'problem': 'prefab_reference_array_missing', 'fieldPath': path,
                   'sourceDeclaredType': declared}
            return
        for index, target in enumerate(refs):
            element_path = f'{path}[{index}]'
            if isinstance(target, str) and target:
                yield {'target': target, 'fieldPath': element_path, 'sourceDeclaredType': declared}
            else:
                yield {'problem': 'prefab_reference_id_missing', 'fieldPath': element_path,
                       'sourceDeclaredType': declared}
        return

    if field.get('elementKind') == 'record':
        rows = field.get('recordValues')
        if not isinstance(rows, list):
            return
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict) or not isinstance(row.get('fields'), list):
                continue
            for leaf in row['fields']:
                if not isinstance(leaf, dict):
                    continue
                name = leaf.get('sourceFieldName')
                if not isinstance(name, str) or not name:
                    continue
                yield from _prefab_references(leaf, f'{path}[{row_index}].{name}')


def _cycle_path(remaining: set[str], adjacency: dict[str, set[str]], indices: dict[str, int]):
    state = {}
    path = []

    def visit(node):
        state[node] = 1
        path.append(node)
        for target in sorted(adjacency[node], key=lambda value: (indices[value], value)):
            if target not in remaining:
                continue
            if state.get(target) == 1:
                start = path.index(target)
                return path[start:] + [target]
            if state.get(target, 0) == 0:
                found = visit(target)
                if found:
                    return found
        path.pop()
        state[node] = 2
        return None

    for node in sorted(remaining, key=lambda value: (indices[value], value)):
        if state.get(node, 0) == 0:
            found = visit(node)
            if found:
                return found
    return []


def plan_source_prefab_dependencies(plan: dict) -> dict:
    """Return a deterministic target-before-owner order plus pinned edge evidence.

    Missing owner/target identities are returned as explicit gaps and are never
    inferred from an asset path, UUID, component name, or field value. A cycle
    makes ordering impossible and raises ``PrefabDependencyError``.
    """
    if not isinstance(plan, dict):
        raise PrefabDependencyError('PREFAB_DEPENDENCY_PLAN_INVALID', {})
    source_prefabs = plan.get('sourcePrefabs')
    if not isinstance(source_prefabs, list):
        raise PrefabDependencyError('PREFAB_DEPENDENCY_SOURCE_LIST_INVALID', {})

    order_ids = []
    indices = {}
    for index, spec in enumerate(source_prefabs):
        source_id = spec.get('sourceId') if isinstance(spec, dict) else None
        if not isinstance(source_id, str) or not source_id:
            raise PrefabDependencyError('PREFAB_DEPENDENCY_SOURCE_ID_INVALID', {'index': index})
        if source_id in indices:
            raise PrefabDependencyError('PREFAB_DEPENDENCY_SOURCE_ID_DUPLICATE', {'sourceId': source_id})
        indices[source_id] = index
        order_ids.append(source_id)

    prefab_ids = set(order_ids)
    specs_by_id = {spec['sourceId']: spec for spec in source_prefabs}
    edge_evidence = defaultdict(list)
    gaps = []

    def add_dependency(owner, target, evidence):
        if not isinstance(owner, str) or owner not in prefab_ids:
            gaps.append({'code': 'PREFAB_DEPENDENCY_OWNER_MISSING', 'owner': owner,
                         'target': target, **evidence})
            return
        if not isinstance(target, str) or target not in prefab_ids:
            gaps.append({'code': 'PREFAB_DEPENDENCY_TARGET_MISSING', 'owner': owner,
                         'target': target, **evidence})
            return
        edge_evidence[(owner, target)].append(evidence)

    for index, relation in enumerate(plan.get('prefabInstances') or []):
        if not isinstance(relation, dict):
            gaps.append({'code': 'PREFAB_INSTANCE_RELATION_INVALID', 'index': index})
            continue
        add_dependency(relation.get('owner'), relation.get('template'),
                       {'kind': 'prefab-instance', 'root': relation.get('root')})

    node_owners = defaultdict(list)
    for source_id in order_ids:
        nodes = specs_by_id[source_id].get('nodes')
        if not isinstance(nodes, list):
            gaps.append({'code': 'PREFAB_DEPENDENCY_NODE_LIST_INVALID', 'owner': source_id})
            continue
        seen_nodes = set()
        for node_id in nodes:
            if isinstance(node_id, str) and node_id:
                if node_id in seen_nodes:
                    gaps.append({'code': 'PREFAB_DEPENDENCY_NODE_ID_DUPLICATE',
                                 'owner': source_id, 'nodeSourceId': node_id})
                    continue
                seen_nodes.add(node_id)
                node_owners[node_id].append(source_id)
            else:
                gaps.append({'code': 'PREFAB_DEPENDENCY_NODE_ID_INVALID', 'owner': source_id})

    for component in plan.get('components') or []:
        if not isinstance(component, dict):
            continue
        binding = component.get('staticFieldBinding')
        if not isinstance(binding, dict):
            continue
        fields = binding.get('fields')
        if not isinstance(fields, list):
            continue
        component_id = component.get('sourceId')
        node_id = component.get('node')
        owners = node_owners.get(node_id, [])
        for field in fields:
            if not isinstance(field, dict):
                continue
            field_name = field.get('sourceFieldName')
            if not isinstance(field_name, str) or not field_name:
                continue
            if field.get('sourceDeclaredType') not in ('cc.Prefab', '[cc.Prefab]') and field.get('elementKind') != 'record':
                continue
            found = list(_prefab_references(field, field_name))
            for reference in found:
                field_path = reference.get('fieldPath', field_name)
                base_evidence = {'kind': 'typed-static-field', 'sourceComponentId': component_id,
                                 'fieldPath': field_path,
                                 'sourceDeclaredType': reference.get('sourceDeclaredType', field.get('sourceDeclaredType'))}
                if reference.get('problem'):
                    gaps.append({'code': 'PREFAB_DEPENDENCY_REFERENCE_INVALID',
                                 'owner': owners[0] if len(owners) == 1 else None,
                                 'target': None, 'problem': reference['problem'],
                                 'sourceComponentId': component_id, **base_evidence})
                    continue
                if len(owners) != 1:
                    gaps.append({'code': 'PREFAB_DEPENDENCY_OWNER_AMBIGUOUS' if owners else 'PREFAB_DEPENDENCY_OWNER_MISSING',
                                 'owner': None, 'target': reference['target'],
                                 'sourceComponentId': component_id, 'nodeSourceId': node_id,
                                 'candidateOwners': sorted(owners), **base_evidence})
                    continue
                add_dependency(owners[0], reference['target'], base_evidence)

    adjacency = {source_id: set() for source_id in order_ids}
    dependents = {source_id: set() for source_id in order_ids}
    indegree = {source_id: 0 for source_id in order_ids}
    for owner, target in edge_evidence:
        # Dependencies point owner -> target; target must be emitted first.
        adjacency[owner].add(target)
        dependents[target].add(owner)
        indegree[owner] += 1

    available = [(indices[source_id], source_id) for source_id in order_ids if indegree[source_id] == 0]
    heapq.heapify(available)
    sorted_ids = []
    while available:
        _, target = heapq.heappop(available)
        sorted_ids.append(target)
        for owner in sorted(dependents[target], key=lambda value: (indices[value], value)):
            indegree[owner] -= 1
            if indegree[owner] == 0:
                heapq.heappush(available, (indices[owner], owner))

    if len(sorted_ids) != len(order_ids):
        remaining = {source_id for source_id in order_ids if indegree[source_id] > 0}
        cycle = _cycle_path(remaining, adjacency, indices)
        raise PrefabDependencyError('PREFAB_DEPENDENCY_CYCLE', {'cycle': cycle})

    dependencies = []
    for (owner, target), evidence in edge_evidence.items():
        evidence = sorted(evidence, key=lambda item: (
            item.get('kind', ''), item.get('sourceComponentId', ''), item.get('fieldPath', ''), item.get('root', '')))
        dependencies.append({'owner': owner, 'target': target, 'evidence': evidence})
    dependencies.sort(key=lambda edge: (
        indices[edge['owner']], indices[edge['target']], edge['owner'], edge['target']))
    gaps.sort(key=lambda item: (
        indices.get(item.get('owner'), len(indices)), str(item.get('owner') or ''), str(item.get('target') or ''),
        str(item.get('kind') or ''), str(item.get('sourceComponentId') or ''),
        str(item.get('fieldPath') or ''), str(item.get('code', ''))))

    return {'schemaVersion': 1, 'order': sorted_ids, 'dependencies': dependencies, 'gaps': gaps}
