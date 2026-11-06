import { _decorator, Component, Node, UIRenderer, Sorting2D, Mask } from 'cc';

const { ccclass, property } = _decorator;

/** Retains the exact source field alongside Creator's compressed native rank. */
@ccclass('MonkeyStaticSortOrderField')
export class MonkeyStaticSortOrderField extends Component {
    @property public sourceId = '';
    @property public nativeId = '';
    @property public sourceSortOrder = 0;
    @property public effectiveSourceSortOrder = 0;
    @property public enabledInSource = true;
    @property public renderedOnNode = false;
}

export interface StaticSortQueueRank {
    node: string;
    sourceComponentId?: string;
    sourceType: string;
    sourceSortOrder: number;
    nativeSortingOrder: number;
    kind: 'renderer' | 'maskEnter';
}

export interface StaticSortOrderField {
    sourceId: string;
    nativeId: string;
    node: string;
    sortOrder: number;
    enabled: boolean;
}

export interface StaticSortQueueContract {
    schemaVersion: number;
    sourceManifestSha256: string;
    rootScope: string;
  creatorMode: 'sorting2d' | 'source-fixed-tree' | 'unsupported';
    creatorQueueMapped: boolean;
  nativeDfsMatchesSource: boolean;
  sourceDrawEvents: Array<[string, string, string | null]>;
  nativeDfsDrawEvents: Array<[string, string, string | null]>;
  maskBarrier: { diagnostic: string | null; expectedOrder: unknown[]; nativeMaskBarrierOrder: unknown[] };
    nativeRanks: StaticSortQueueRank[];
    sortOrderFields: StaticSortOrderField[];
    sortRootOccurrences: Array<{sourceId: string; nativeId: string; node: string; enabled: boolean}>;
    sourceChildOrder: Record<string, string[]>;
  sourceNodeActive: Record<string, boolean>;
}

export interface StaticSortQueueReadback {
    sourceId: string;
    node: string;
    rendererUuid: string | null;
    sorting2DUuid: string | null;
    nativeSortingOrder: number | null;
    sourceSortOrder: number | null;
  sourceQueueMode: string;
    verified: boolean;
    diagnostic: string | null;
}

function exactNode(nodes: Map<string, Node>, sourceId: string): Node {
    const node = nodes.get(sourceId);
    if (!node || !node.isValid) throw new Error(`STATIC_SORT_NODE_MISSING: ${sourceId}`);
    return node;
}

function hasSingleRenderer(node: Node, row: StaticSortQueueRank): UIRenderer {
    const renderer = node.getComponent(UIRenderer);
    if (!renderer || !renderer.isValid)
        throw new Error(`STATIC_SORT_UIRENDERER_MISSING: ${row.node} (${row.sourceType})`);
    if (row.kind === 'maskEnter') {
        const mask = node.getComponent(Mask);
        if (!mask || !mask.enabled || mask.subComp !== renderer)
            throw new Error(`STATIC_SORT_MASK_RENDERER_IDENTITY_MISMATCH: ${row.node}`);
    }
    return renderer;
}

function sourceTreeMatches(contract: StaticSortQueueContract, nodes: Map<string, Node>): boolean {
    for (const [parentId, sourceChildren] of Object.entries(contract.sourceChildOrder)) {
        const parent = nodes.get(parentId);
        if (!parent) return false;
        const observedSourceChildren: Node[] = [];
        for (const child of parent.children) {
            if (sourceChildren.some(sourceId => nodes.get(sourceId) === child)) observedSourceChildren.push(child);
            else {
                const isTmpSubmesh = child.getComponents(Component).some(component =>
                    component.constructor.name === 'TMP_SubMeshUI' ||
                    String((component.constructor as any).__classname__ || '').includes('TMP_SubMeshUI'));
                if (!isTmpSubmesh) return false;
            }
        }
        if (observedSourceChildren.length !== sourceChildren.length) return false;
        for (let index = 0; index < sourceChildren.length; index++)
            if (nodes.get(sourceChildren[index]) !== observedSourceChildren[index]) return false;
    }
    return true;
}

function nativeDfsMatchesSource(contract: StaticSortQueueContract, nodes: Map<string, Node>): boolean {
    const maskNodes = new Set(contract.maskBarrier.expectedOrder.filter((row: any) => row[0] === 'maskEnter').map((row: any) => row[1]));
    // Expected traversal labels are hash-bound by source IDs. Mask enter/exit
    // delimit the native stencil blocks; generated TMP submeshes stay grouped
    // under the source Label and do not add source leaves.
    for (const row of contract.nativeRanks) if (row.kind === 'maskEnter') maskNodes.add(row.node);
    const rendererByNode = new Map(contract.nativeRanks.filter(row => row.kind === 'renderer').map(row => [row.node, row]));
    const actual: Array<[string, string, string | null]> = [];
    const visit = (nodeId: string, parentActive: boolean): boolean => {
        const node = nodes.get(nodeId);
        if (!node || contract.sourceNodeActive[nodeId] !== node.active) return false;
        const effectiveActive = parentActive && node.active;
        if (!effectiveActive) return true;
        if (maskNodes.has(nodeId)) {
            const mask = node.getComponent(Mask);
            if (!mask || !mask.enabled) return false;
            actual.push(['maskEnter', nodeId, null]);
            for (const childId of contract.sourceChildOrder[nodeId] || []) if (!visit(childId, effectiveActive)) return false;
            actual.push(['maskExit', nodeId, null]);
            return true;
        }
        const rank = rendererByNode.get(nodeId);
        if (rank) {
            const renderer = node.getComponent(UIRenderer);
            if (!renderer || !renderer.enabled) return false;
            actual.push(['renderer', nodeId, rank.sourceComponentId || null]);
        }
        for (const childId of contract.sourceChildOrder[nodeId] || []) if (!visit(childId, effectiveActive)) return false;
        return true;
    };
    if (!visit(contract.rootScope, true)) return false;
    return JSON.stringify(actual) === JSON.stringify(contract.sourceDrawEvents);
}

export function createStaticSortQueue(
    contract: StaticSortQueueContract,
    nodes: Map<string, Node>,
): StaticSortQueueReadback[] {
    if (!contract || contract.schemaVersion !== 1) throw new Error('STATIC_SORT_QUEUE_CONTRACT_INVALID');
    // Sorting2D's renderer queue is segmented by native Mask stencil barriers.
    // Never enable partial sorting when a source block would cross one.
    if (!contract.creatorQueueMapped || contract.creatorMode === 'unsupported')
        throw new Error(`STATIC_SORT_MASK_BARRIER_UNREPRESENTABLE: ${contract.maskBarrier.diagnostic || contract.rootScope}`);
    if (!sourceTreeMatches(contract, nodes)) throw new Error('STATIC_SORT_SOURCE_TREE_IDENTITY_MISMATCH');
    if (contract.creatorMode === 'source-fixed-tree' && !nativeDfsMatchesSource(contract, nodes))
        throw new Error('STATIC_SORT_SOURCE_FIXED_DRAW_SEQUENCE_MISMATCH');
    const rankByNode = new Map<string, StaticSortQueueRank>();
    for (const rank of contract.nativeRanks) {
        if (!Number.isInteger(rank.nativeSortingOrder) || rank.nativeSortingOrder < -32768 || rank.nativeSortingOrder > 32767)
            throw new Error(`STATIC_SORT_NATIVE_ORDER_OUT_OF_INT16_RANGE: ${rank.node}`);
        if (rankByNode.has(rank.node)) throw new Error(`STATIC_SORT_DUPLICATE_RENDER_NODE: ${rank.node}`);
        rankByNode.set(rank.node, rank);
    }

    // Preflight all identities before adding components, so a missing mask
    // backing or UIRenderer cannot leave half a Prefab modified.
    const prepared = contract.creatorMode === 'sorting2d' ? [...rankByNode.values()].map(row => {
        const node = exactNode(nodes, row.node);
        const renderer = hasSingleRenderer(node, row);
        if (node.getComponent(Sorting2D)) throw new Error(`STATIC_SORTING2D_ALREADY_EXISTS: ${row.node}`);
        return {row, node, renderer};
    }) : [];
    const fields = contract.sortOrderFields.map(row => {
        const node = exactNode(nodes, row.node);
        if (node.getComponent(MonkeyStaticSortOrderField))
            throw new Error(`STATIC_SORT_FIELD_ALREADY_EXISTS: ${row.sourceId}`);
        return {row, node};
    });

    const results: StaticSortQueueReadback[] = [];
    for (const {row, node, renderer} of prepared) {
        const sorting = node.addComponent(Sorting2D);
        if (!sorting || !(sorting instanceof Sorting2D)) throw new Error(`STATIC_SORTING2D_CREATE_FAILED: ${row.node}`);
        sorting.sortingOrder = row.nativeSortingOrder;
        sorting.enabled = true;
        if (sorting.sortingOrder !== row.nativeSortingOrder)
            throw new Error(`STATIC_SORTING2D_VALUE_CLAMPED: ${row.node}`);
        results.push({sourceId: row.sourceComponentId || row.node, node: row.node,
            rendererUuid: renderer.uuid, sorting2DUuid: sorting.uuid, nativeSortingOrder: sorting.sortingOrder,
            sourceSortOrder: row.sourceSortOrder, sourceQueueMode: contract.creatorMode, verified: true, diagnostic: null});
    }
    for (const {row, node} of fields) {
        const carrier = node.addComponent(MonkeyStaticSortOrderField);
        carrier.sourceId = row.sourceId;
        carrier.nativeId = row.nativeId;
        carrier.sourceSortOrder = row.sortOrder;
        carrier.enabledInSource = row.enabled;
        carrier.effectiveSourceSortOrder = row.enabled ? row.sortOrder : 0;
        carrier.renderedOnNode = rankByNode.has(row.node) && rankByNode.get(row.node)?.kind === 'renderer';
        if (carrier.sourceId !== row.sourceId || carrier.nativeId !== row.nativeId ||
            carrier.sourceSortOrder !== row.sortOrder || carrier.enabledInSource !== row.enabled)
            throw new Error(`STATIC_SORT_SOURCE_FIELD_ASSIGNMENT_FAILED: ${row.sourceId}`);
    }
    if (!sourceTreeMatches(contract, nodes)) throw new Error('STATIC_SORT_SOURCE_TREE_CHANGED');
    const readback = readStaticSortQueue(contract, nodes);
    if (readback.some(row => !row.verified)) throw new Error('STATIC_SORT_NATIVE_READBACK_FAILED');
    return readback;
}

export function readStaticSortQueue(
    contract: StaticSortQueueContract,
    nodes: Map<string, Node>,
): StaticSortQueueReadback[] {
    const treeOK = sourceTreeMatches(contract, nodes);
    const fixedTreeMatches = contract.creatorMode === 'source-fixed-tree' && nativeDfsMatchesSource(contract, nodes);
    return contract.nativeRanks.map(row => {
        const node = nodes.get(row.node);
        const render = node && node.getComponent(UIRenderer);
        const mask = row.kind === 'maskEnter' && node ? node.getComponent(Mask) : null;
        const sort = node && node.getComponent(Sorting2D);
        const fixedMode = contract.creatorMode === 'source-fixed-tree';
        const verified = treeOK && !!render && (fixedMode ? fixedTreeMatches : !!sort && sort.enabled &&
            sort.sortingOrder === row.nativeSortingOrder) &&
            (row.kind !== 'maskEnter' || (!!mask && mask.enabled && mask.subComp === render)) &&
            (!row.sourceComponentId || typeof render.uuid === 'string');
        return {sourceId: row.sourceComponentId || row.node, node: row.node,
            rendererUuid: render ? render.uuid : null, sorting2DUuid: sort ? sort.uuid : null,
            nativeSortingOrder: sort ? sort.sortingOrder : null, sourceSortOrder: row.sourceSortOrder,
            sourceQueueMode: contract.creatorMode,
            verified, diagnostic: verified ? null : 'STATIC_SORT_NATIVE_IDENTITY_OR_RANK_MISMATCH'};
    });
}

export function readStaticSortOrderFields(
    contract: StaticSortQueueContract,
    nodes: Map<string, Node>,
): Array<{sourceId: string; node: string; nativeId: string; sourceSortOrder: number; enabled: boolean; verified: boolean}> {
    return contract.sortOrderFields.map(row => {
        const node = nodes.get(row.node);
        const carrier = node && node.getComponent(MonkeyStaticSortOrderField);
        return {sourceId: row.sourceId, node: row.node, nativeId: carrier ? carrier.nativeId : '',
            sourceSortOrder: carrier ? carrier.sourceSortOrder : NaN,
            enabled: carrier ? carrier.enabledInSource : false,
            verified: !!carrier && carrier.sourceId === row.sourceId && carrier.nativeId === row.nativeId &&
                carrier.sourceSortOrder === row.sortOrder && carrier.enabledInSource === row.enabled};
    });
}

export function readStaticSortRoots(
    contract: StaticSortQueueContract,
    nodes: Map<string, Node>,
): Array<{sourceId: string; node: string; nativeType: null; enabled: boolean; verified: boolean; diagnostic: string | null}> {
    const treeOK = sourceTreeMatches(contract, nodes);
    return contract.sortRootOccurrences.map(row => {
        const node = nodes.get(row.node);
        return {sourceId: row.sourceId, node: row.node, nativeType: null as null, enabled: row.enabled,
            verified: treeOK && !!node, diagnostic: treeOK && !!node ? null : 'STATIC_SORT_ROOT_SOURCE_NODE_MISMATCH'};
    });
}
