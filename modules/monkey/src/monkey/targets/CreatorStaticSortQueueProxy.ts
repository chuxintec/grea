import {
    _decorator, Camera, Canvas, Color, Component, Graphics, Label, Layout, Mask, Mat4, Node, RichText, Sorting2D, Sprite,
    SortingLayers, SpriteFrame, UITransform, UIOpacity, UIRenderer,
} from 'cc';
import { CreatorStaticSortQueueProxyMarker } from './CreatorStaticSortQueueProxyMarker';
import { CreatorStaticSortQueueProxyPresenter, syncGeneratedRichTextSegments } from './CreatorStaticSortQueueProxyPresenter';
import { MonkeyStaticSortOrderField } from './CreatorStaticSortQueue';
import { CreatorStaticSortRootField } from './CreatorStaticSortRootField';
import { MonkeyStaticMaskIdentity } from '../StaticMasks/CreatorStaticMaskIdentity';

const { ccclass, property } = _decorator;
export const CREATOR_STATIC_SORT_QUEUE_PROXY_API_UUID = 'f82a1331-6407-5dbc-9833-b421ddbbfc68';

export interface CreatorProxyRendererSpec {
    node: string; sourceComponentId: string; sourceType: string; nativeSortingOrder: number;
    sourceFields?: Record<string, unknown>; sourceFieldsJson?: string; sourceFieldsSha256?: string; initialCommandStreamEmpty?: boolean;
    sourceEnabled?: boolean; sourceText?: string; sourceTextEmpty?: boolean; sourceFontId?: string | null;
    sourceFontMissing?: boolean; nativeFontAssetId?: string; nativeFallbackAssetIds?: string[];
    targetSystemFontFamily?: string; creatorMarkup?: string; renderReady?: boolean;
}
export interface CreatorProxyNonDrawRendererSpec {
    sourceId: string; nativeId: string; node: string; sourceType: string; expectedNativeType: string;
    sourceEnabled: boolean; sourceActive: boolean; sourceFields: Record<string, unknown>;
    sourceFieldsJson: string; sourceFieldsSha256: string; sourceSpriteFrameUuid: string | null;
    sourceSpriteFrameAssetId: string | null; nativeSpriteImageUuidExpected: string | null;
    nativeSpriteFrameUuidExpected: string | null;
    sourceText: string | null; nativeTextExpectation?: string | null; sourceTextEmpty?: boolean; sourceFontId: string | null; creatorMarkup?: string;
    nativeFontAssetId?: string; nativeFallbackAssetIds?: string[]; targetSystemFontFamily?: string;
    sourceNeedsSpriteBinding: boolean;
    noDrawReason?: string; nativeEnabledExpected?: boolean; initialCommandStreamEmpty?: boolean;
    sourceDrawingCommands?: string; sourceMaterialIds?: string[];
}
export interface CreatorProxyMaskSpec {
    node: string; sourceId: string; nativeId: string; maskType: number; inverted: boolean;
    enabled: boolean; alphaThreshold: number; spriteFrameUuid?: string;
    sourceFieldsJson: string; sourceFields: Record<string, unknown>;
}
export interface CreatorProxyEvent { kind: 'renderer' | 'maskEnter' | 'maskExit'; node: string; sourceComponentId?: string | null; }
export interface CreatorProxySourceNonDrawMapping {
    sourceComponentId: string; node: string; disposition: 'source-render-event' | 'source-component-only';
    sourceEventIndex: number | null; noDrawReason: string;
}
export interface CreatorSortOrderField { sourceId: string; nativeId: string; node: string; sortOrder: number; enabled: boolean; }
export interface CreatorSortRootField { sourceId: string; nativeId: string; node: string; enabled: boolean; }
export interface CreatorSourceSortIdentityReadback {
    sourceSortOrderFields: Array<{sourceId: string; nativeId: string; node: string; sortOrder: number;
        enabled: boolean; componentUuid: string; verified: boolean}>;
    sourceSortRoots: Array<{sourceId: string; nativeId: string; node: string;
        enabled: boolean; componentUuid: string; verified: boolean}>;
    verified: boolean;
}
export interface CreatorProxySpec {
    rootScope: string; sourcePrefabId: string; prefabPath: string; sourceManifestSha256: string;
    /** Unfiltered source queue, including fixed-state no-draw renderers such as empty cc.Graphics. */
    sourceOriginalDrawEvents: CreatorProxyEvent[];
    /** Native proxy presentation queue; may omit only events with a typed, source-bound nonDrawRenderers row. */
    sourceDrawEvents: CreatorProxyEvent[]; renderers: CreatorProxyRendererSpec[]; masks: CreatorProxyMaskSpec[];
    sourceSortOrderFields: CreatorSortOrderField[]; sourceSortRoots: CreatorSortRootField[];
    nonDrawRenderers: CreatorProxyNonDrawRendererSpec[]; sourceNonDrawRenderers: CreatorProxySourceNonDrawMapping[];
    sourceChildOrder: Record<string, string[]>; sourceNodeActive: Record<string, boolean>;
    sourceNodeIds: string[]; sourceNodeLayers: Record<string, number>; sourceLayerHiddenValue: number;
}
export interface CreatorProxyGraphicReadback {
    sourceComponentId: string; sourceNode: string; nativeType: string; sourceFingerprint: string;
    proxyFingerprint: string; originalLayer: number; proxyLayer: number; opacityVerified: boolean; verified: boolean;
    sourceAuthoredOpacityWithinRoot: number | null; proxyAuthoredOpacityWithinProxy: number;
    segmentCount: number | null; sortingSegmentsVerified: boolean;
    sourceOpacityPath: Array<{nodeUuid: string; nodeName: string; sourceNodeId: string | null; componentUuid: string | null;
        enabled: boolean | null; opacity: number | null; localFactor: number}>;
    proxyOpacityPath: Array<{nodeUuid: string; nodeName: string; sourceNodeId: string | null; componentUuid: string | null;
        enabled: boolean | null; opacity: number | null; localFactor: number}>;
    sourceSegmentsHidden: boolean | null; proxySegmentsCorrectLayer: boolean | null;
    sourceFieldsJson: string | null; sourceFieldsSha256: string | null; sourceText: string | null;
    renderedString: string | null; sourceFontId: string | null; nativeFontAssetId: string | null;
    nativeFallbackAssetIds: string[] | null; targetSystemFontFamily: string | null; creatorMarkup: string | null;
    fontAssetUuid: string | null; fontFamily: string | null; imageAtlasUuid: string | null;
}
export interface CreatorProxyMaskReadback {
    sourceId: string; sourceNode: string; sourceMaskType: number; nativeMaskType: number;
    inverted: boolean; enabled: boolean; alphaThreshold: number; spriteFrameUuid: string | null;
    transformVerified: boolean; opacityVerified: boolean; verified: boolean;
    checks: Record<string, boolean>;
    sourceMaskEnabled: boolean | null; sourceMaskInverted: boolean | null; sourceAlphaThreshold: number | null;
    expectedMaskEnabled: boolean | null; expectedMaskType: number | null; expectedInverted: boolean | null;
    expectedAlphaThreshold: number | null; expectedSpriteFrameUuid: string | null;
    sourceSpriteType: string | null; sourceSpriteEnabled: boolean | null; sourceSpriteFrameUuid: string | null;
    nativeSpriteType: string | null; nativeSpriteEnabled: boolean | null; nativeSpriteFrameExpectedUuid: string | null;
    sourceSpriteFingerprint: string | null; nativeSpriteFingerprint: string | null;
    identitySourceId: string | null; identityNativeId: string | null; identityNativeMaskRefMatches: boolean;
    sourceLocalTransform: number[] | null; nativeLocalTransform: number[];
    sourceWorldMatrix: number[] | null; nativeWorldMatrix: number[];
    sourceSizeAnchor: number[] | null; nativeSizeAnchor: number[] | null;
    sourceOpacityFactor: number | null; nativeOpacityFactor: number | null;
    sourceLayer: number | null; nativeLayer: number;
}
export interface CreatorProxyReadback {
    rootScope: string; sourceTreePreserved: boolean; sourceFieldsPreserved: boolean;
    sourceSortRootsPreserved: boolean; sourceLayersPreserved: boolean; sourceSuppressed: boolean;
    sourceLayersMatchContract: boolean; failedChecks: string[]; failedSourceIds: string[];
    initializedContextVerified: boolean; cameraSafe: boolean;
    nestedProxyRootsDisabled: boolean; presentationMode: 'persistent' | 'initialized'; drawSequenceVerified: boolean;
    sourceQueueProjectionVerified: boolean; sourceOriginalDrawEvents: CreatorProxyEvent[];
    sourceNonDrawSourceMappings: Array<CreatorProxySourceNonDrawMapping & {verified: boolean}>;
    sourceSortOrderFields: Array<{sourceId: string | null; expectedSourceId: string; nativeId: string | null; expectedNativeId: string;
        node: string; sourceSortOrder: number | null; effectiveSourceSortOrder: number | null; enabledInSource: boolean | null;
        renderedOnNode: boolean | null; componentUuid: string | null; nativeClass: string | null; verified: boolean}>;
    sourceSortRoots: Array<{sourceId: string | null; expectedSourceId: string; nativeId: string | null; expectedNativeId: string;
        node: string; enabledInSource: boolean | null; componentUuid: string | null; nativeClass: string | null; verified: boolean}>;
    nestedProxyRootReadbacks: Array<{sourceNode: string; rootUuid: string; active: boolean; expectedActiveBefore: boolean | null;
        markerSourceNode: string | null; markerOwnerMatches: boolean; presenterPresent: boolean;
        presenterSourceRootMatches: boolean; presenterProxyRootMatches: boolean; presenterSourceRootId: string | null;
        verified: boolean}>;
    nestedProxyRootActiveArrayMatches: boolean;
    sourceNonDrawRenderers: Array<{sourceId: string; nativeId: string; node: string; sourceType: string; expectedNativeType: string;
        actualNativeType: string; componentUuid: string; sourceEnabled: boolean; sourceActive: boolean;
        componentEnabled: boolean; nativeEnabledExpected: boolean; nodeActive: boolean; effectiveActive: boolean;
        sourceNeedsSpriteBinding: boolean | null;
        sourceFieldsJson: string; sourceFieldsSha256: string; sourceSpriteFrameUuid: string | null;
        sourceSpriteFrameAssetId: string | null; nativeSpriteImageUuidExpected: string | null;
        nativeSpriteFrameUuidExpected: string | null; nativeSpriteFrameUuid: string | null;
        sourceText: string | null; actualText: string | null; sourceFontId: string | null; nativeFontAssetId: string | null;
        nativeFallbackAssetIds: string[] | null; targetSystemFontFamily: string | null; creatorMarkup: string | null;
        noDrawReason: string | null; sourceTextEmpty: boolean | null; nativeTextExpectation: string | null;
        initialCommandStreamEmpty: boolean | null;
        sourceDrawingCommands: string | null; sourceMaterialIds: string[] | null; graphicsPathCount: number | null;
        nativeMaterialUuid: string | null; nativeEffectUuid: string | null; nativeMaterialVerified: boolean | null; verified: boolean}>;
    sourceRendererCoverageVerified: boolean; structuralRootLayoutSafe: boolean;
    graphics: CreatorProxyGraphicReadback[]; masks: CreatorProxyMaskReadback[];
    verified: boolean; diagnostic: string | null;
}

function fail(code: string, id = ''): never { throw new Error(code + (id ? ':' + id : '')); }
const CREATOR_BUILTIN_GRAPHICS_MATERIAL_UUID = 'f0416e68-0200-4b77-a926-4f9d16e494da';
const CREATOR_BUILTIN_GRAPHICS_EFFECT_UUID = '1c02ae6f-4492-4915-b8f8-7492a3b1e4cd';
export function creatorStaticEmptyGraphicsEvidence(componentEnabled: boolean, pathCount: number,
    materialUuid: string | null, effectUuid: string | null, rendererMaterialPresent: boolean,
    rendererMaterialMatchesCustom: boolean): boolean {
    return componentEnabled === false && pathCount === 0 &&
        materialUuid === CREATOR_BUILTIN_GRAPHICS_MATERIAL_UUID && effectUuid === CREATOR_BUILTIN_GRAPHICS_EFFECT_UUID &&
        (!rendererMaterialPresent || rendererMaterialMatchesCustom);
}
function refId(value: any): string | null {
    if (!value) return null;
    return typeof value._uuid === 'string' ? value._uuid : null;
}
function creatorStaticGraphicsMaterialVerified(component: Graphics): {verified: boolean; materialUuid: string | null;
    effectUuid: string | null; rendererMaterialUuid: string | null; rendererMaterialMatchesCustom: boolean} {
    const material: any = (component as any).customMaterial, rendererMaterial: any = component.getMaterial(0);
    const effect = material && material.effectAsset;
    const materialUuid = refId(material), effectUuid = refId(effect), rendererMaterialUuid = refId(rendererMaterial);
    const rendererMaterialMatchesCustom = !!material && rendererMaterial === material;
    // A disabled, empty Graphics is a static carrier and may have no active
    // renderer material instance. If one exists, it still must be the exact
    // persistent customMaterial reference.
    const paths = (component as any).impl?.paths;
    const pathCount = Array.isArray(paths) ? paths.length : -1;
    return {verified: creatorStaticEmptyGraphicsEvidence(component.enabled, pathCount, materialUuid, effectUuid,
        !!rendererMaterial, rendererMaterialMatchesCustom), materialUuid, effectUuid, rendererMaterialUuid, rendererMaterialMatchesCustom};
}
function colorValue(color: Color): number[] { return [color.r, color.g, color.b, color.a]; }
function equalValue(a: unknown, b: unknown): boolean { return JSON.stringify(a) === JSON.stringify(b); }
function matrixValues(node: Node): number[] {
    const m = node.worldMatrix;
    return [m.m00,m.m01,m.m02,m.m03,m.m04,m.m05,m.m06,m.m07,m.m08,m.m09,m.m10,m.m11,m.m12,m.m13,m.m14,m.m15];
}
function matricesMatch(a: Node, b: Node, epsilon = 1e-5): boolean {
    const left = matrixValues(a), right = matrixValues(b);
    return left.every((v, i) => Math.abs(v - right[i]) <= epsilon);
}
function treeMatches(spec: CreatorProxySpec, nodes: Map<string, Node>): boolean {
    return Object.entries(spec.sourceChildOrder).every(([id, children]) => {
        const node = nodes.get(id);
        if (!node) return false;
        const reverse = new Map<Node, string>(); for (const [sourceId, value] of nodes) reverse.set(value, sourceId);
        const mapped = node.children.map(child => reverse.get(child) || (isGeneratedSortProxyRoot(child) || isGeneratedRichTextSegment(node, child) ? null : '__UNMAPPED__'))
            .filter(value => value !== null);
        return equalValue(mapped, children);
    });
}
function isGeneratedRichTextSegment(parent: Node, child: Node): boolean {
    return !!parent.getComponent(RichText) && !!child.hideFlags &&
        (child.name === 'RICHTEXT_CHILD' || child.name === 'RICHTEXT_Image_CHILD');
}
export function isGeneratedSortProxyRoot(child: Node): boolean {
    if (!child || !child.parent) return false;
    const marker = child.getComponent(CreatorStaticSortQueueProxyMarker);
    if (!marker || marker.kind !== 'root' || marker.sourceRootOwner !== child.parent) return false;
    const presenter = child.getComponent(CreatorStaticSortQueueProxyPresenter);
    return !!presenter && presenter.sourceRoot === child.parent && presenter.proxyRoot === child &&
        presenter.sourceRootId === marker.sourceNode;
}
function sourceRenderer(node: Node, type: string, requireHierarchy = true, requireEnabled = true): Component {
    const renderer = type === 'cc.Sprite' ? node.getComponent(Sprite) : type === 'cc.Label' ? node.getComponent(Label) :
        type === 'sp.Skeleton' ? node.getComponent('sp.Skeleton') as UIRenderer :
        type === 'cc.Graphics' ? node.getComponent(Graphics) : type === 'cc.RichText' ? node.getComponent(RichText) : null;
    if (!renderer || (requireEnabled && !renderer.enabled) || (requireHierarchy && !renderer.enabledInHierarchy))
        fail('CREATOR_PROXY_SOURCE_RENDERER_MISSING_OR_DISABLED', type);
    return renderer;
}
function ancestorCanvas(node: Node | null): Canvas | null {
    for (let current = node as Node | null; current; current = current.parent as Node | null) {
        const canvas = current.getComponent(Canvas);
        if (canvas) return canvas;
    }
    return null;
}
function nodeIsWithin(node: Node | null, ancestor: Node): boolean {
    for (let current = node as Node | null; current; current = current.parent as Node | null)
        if (current === ancestor) return true;
    return false;
}
function sourceParentByChild(spec: CreatorProxySpec): Map<string, string> {
    const parentByChild = new Map<string, string>();
    for (const [parentId, children] of Object.entries(spec.sourceChildOrder)) for (const childId of children) {
        if (parentByChild.has(childId)) fail('CREATOR_PROXY_SOURCE_NODE_HAS_MULTIPLE_PARENTS', childId);
        parentByChild.set(childId, parentId);
    }
    return parentByChild;
}
function sourceNodeActiveInContract(spec: CreatorProxySpec, nodeId: string, parentByChild = sourceParentByChild(spec)): boolean {
    const seen = new Set<string>(); let current: string | undefined = nodeId;
    while (current) {
        if (seen.has(current)) fail('CREATOR_PROXY_SOURCE_NODE_PARENT_CYCLE', current);
        seen.add(current);
        const active = spec.sourceNodeActive[current];
        if (typeof active !== 'boolean') fail('CREATOR_PROXY_SOURCE_ACTIVITY_MISSING', current);
        if (!active) return false;
        if (current === spec.rootScope) return true;
        current = parentByChild.get(current);
    }
    fail('CREATOR_PROXY_SOURCE_NODE_OUTSIDE_SCOPE', nodeId);
}
function depth(node: Node): number {
    let value = 0; for (let current: Node | null = node; current; current = current.parent) value++; return value;
}
function nestedPresenter(layerNode: Node, authoredLayer: number, nestedRoots: Node[]): CreatorStaticSortQueueProxyPresenter | null {
    for (const root of nestedRoots) {
        const presenter = root.getComponent(CreatorStaticSortQueueProxyPresenter);
        if (!presenter || presenter.proxyRoot !== root || !presenter.sourceRoot || !isGeneratedSortProxyRoot(root)) continue;
        const index = presenter.sourceNodes.indexOf(layerNode);
        if (index >= 0 && presenter.originalLayers[index] === authoredLayer && layerNode.layer === presenter.hiddenLayer)
            return presenter;
    }
    return null;
}
function maskBackingMatches(node: Node, mask: Mask, renderer: UIRenderer, requireResolvedCache: boolean): boolean {
    if (mask.subComp === renderer) return true;
    if (requireResolvedCache) return false;
    // A persistent Prefab read can observe Mask's serialized backing component
    // before its transient `_graphics`/`_sprite` cache is rebuilt by onLoad.
    // Creator's _createGraphics/_createSprite adopts the sole typed renderer
    // on the same node. Ambiguous/mixed renderer sets fail closed.
    if (!mask.subComp && node.getComponents(Mask).length === 1) {
        if ((mask.type === Mask.Type.GRAPHICS_RECT || mask.type === Mask.Type.GRAPHICS_ELLIPSE) && renderer instanceof Graphics)
            return node.getComponents(Graphics).length === 1 && node.getComponents(Sprite).length === 0 && renderer === node.getComponent(Graphics);
        if (mask.type === Mask.Type.SPRITE_STENCIL && renderer instanceof Sprite)
            return node.getComponents(Sprite).length === 1 && node.getComponents(Graphics).length === 0 && renderer === node.getComponent(Sprite);
    }
    const identity = node.getComponents(MonkeyStaticMaskIdentity).find(item => item.nativeMask === mask);
    if (!identity) return false;
    if (mask.type === Mask.Type.SPRITE_STENCIL && renderer instanceof Sprite)
        return node.getComponents(Sprite).length === 1 && renderer === node.getComponent(Sprite);
    if ((mask.type === Mask.Type.GRAPHICS_RECT || mask.type === Mask.Type.GRAPHICS_ELLIPSE) && renderer instanceof Graphics)
        return node.getComponents(Graphics).length === 1 && renderer === node.getComponent(Graphics);
    return false;
}
function isMaskBacking(node: Node, renderer: UIRenderer): boolean {
    return node.getComponents(Mask).some(mask => maskBackingMatches(node, mask, renderer, false));
}
function canonicalJson(value: any): string {
    if (Array.isArray(value)) return '[' + value.map(canonicalJson).join(',') + ']';
    if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(key =>
        JSON.stringify(key) + ':' + canonicalJson(value[key])).join(',') + '}';
    return JSON.stringify(value);
}
function sourceFieldsJsonMatches(row: CreatorProxyRendererSpec, raw: Record<string, unknown>): boolean {
    if (typeof row.sourceFieldsJson !== 'string') return false;
    try { return canonicalJson(JSON.parse(row.sourceFieldsJson)) === canonicalJson(raw); }
    catch (_) { return false; }
}
function verifyRichTextSourceProof(row: CreatorProxyRendererSpec, renderer: RichText): void {
    const raw = row.sourceFields;
    if (!raw || raw.__type__ !== 'cc.RichText' || !sourceFieldsJsonMatches(row, raw) || typeof row.sourceFieldsSha256 !== 'string' ||
        !/^[a-f0-9]{64}$/.test(row.sourceFieldsSha256) || typeof row.sourceText !== 'string' ||
        raw._N$string !== row.sourceText || row.sourceTextEmpty !== (row.sourceText === '') ||
        row.renderReady !== true || typeof row.creatorMarkup !== 'string' || renderer.string !== row.creatorMarkup ||
        row.sourceEnabled !== renderer.enabled || typeof row.sourceFontMissing !== 'boolean' ||
        row.sourceFontMissing === (typeof row.sourceFontId === 'string' && row.sourceFontId.length > 0) ||
        typeof row.nativeFontAssetId !== 'string' || !row.nativeFontAssetId ||
        !Array.isArray(row.nativeFallbackAssetIds) || typeof row.targetSystemFontFamily !== 'string' ||
        !row.targetSystemFontFamily || !renderer.useSystemFont || renderer.font !== null ||
        renderer.fontFamily !== row.targetSystemFontFamily)
        fail('CREATOR_PROXY_RICHTEXT_SOURCE_FIELDS_OR_NATIVE_FONT_PROOF_MISMATCH', row.sourceComponentId);
}
type CreatorNonDrawReadback = CreatorProxyReadback['sourceNonDrawRenderers'][number];
function assertSourceRendererCoverage(spec: CreatorProxySpec, nodes: Map<string, Node>): CreatorNonDrawReadback[] {
    const parents = sourceParentByChild(spec);
    const rowsById = new Map<string, CreatorProxyRendererSpec>(), claimed = new Set<Component>();
    for (const row of spec.renderers) {
        if (!row.sourceComponentId || rowsById.has(row.sourceComponentId)) fail('CREATOR_PROXY_RENDERER_CONTRACT_DUPLICATE', row.sourceComponentId);
        const node = nodes.get(row.node);
        if (!node) fail('CREATOR_PROXY_SOURCE_NODE_MISSING', row.node);
        if (!sourceNodeActiveInContract(spec, row.node, parents)) fail('CREATOR_PROXY_DRAW_ROW_IS_INACTIVE', row.sourceComponentId);
        const component = sourceRenderer(node, row.sourceType, false);
        if (!component.enabled || claimed.has(component)) fail('CREATOR_PROXY_RENDERER_IDENTITY_DUPLICATE_OR_DISABLED', row.sourceComponentId);
        if (row.sourceType === 'cc.RichText') verifyRichTextSourceProof(row, component as RichText);
        if (component instanceof UIRenderer && isMaskBacking(node, component))
            fail('CREATOR_PROXY_MASK_BACKING_MUST_NOT_BE_A_DRAW_ROW', row.sourceComponentId);
        claimed.add(component); rowsById.set(row.sourceComponentId, row);
    }
    const nonDrawById = new Map<string, CreatorProxyNonDrawRendererSpec>(), nonDrawComponents = new Map<Component, CreatorProxyNonDrawRendererSpec>();
    const nonDrawReadback: CreatorNonDrawReadback[] = [];
    for (const row of spec.nonDrawRenderers) {
        if (!row.sourceId || rowsById.has(row.sourceId) || nonDrawById.has(row.sourceId))
            fail('CREATOR_PROXY_NONDRAW_COMPONENT_ID_DUPLICATE', row.sourceId);
        const node = nodes.get(row.node);
        if (!node) fail('CREATOR_PROXY_NONDRAW_SOURCE_NODE_MISSING', row.node);
        const component = sourceRenderer(node, row.sourceType, false, false);
        if (claimed.has(component) || nonDrawComponents.has(component)) fail('CREATOR_PROXY_NONDRAW_COMPONENT_IDENTITY_DUPLICATE', row.sourceId);
        const actualNativeType = component.constructor.name;
        const sourceActive = sourceNodeActiveInContract(spec, row.node, parents);
        const sourceFieldsOK = !!row.sourceFields && sourceFieldsJsonMatches(row as unknown as CreatorProxyRendererSpec, row.sourceFields) &&
            typeof row.sourceFieldsSha256 === 'string' && /^[a-f0-9]{64}$/.test(row.sourceFieldsSha256);
        const actualSpriteFrame = component instanceof Sprite ? refId(component.spriteFrame) : null;
        const actualText = component instanceof Label || component instanceof RichText ? component.string : null;
        const actualFontUuid = component instanceof Label || component instanceof RichText ? refId(component.font) : null;
        const creatorMarkup = row.sourceType === 'cc.RichText' ? row.creatorMarkup ?? null : null;
        const richTextActualOK = !(component instanceof RichText) ||
            (typeof row.creatorMarkup === 'string' && component.string === row.creatorMarkup &&
             (!row.targetSystemFontFamily || (component.useSystemFont && component.font === null &&
                 component.fontFamily === row.targetSystemFontFamily)));
        const nativeTextExpectation = row.nativeTextExpectation ?? null;
        const sourceTextEmpty = row.sourceTextEmpty ?? null;
        const textIdentityOK = component instanceof Label ? row.sourceText !== null && actualText === (nativeTextExpectation ?? row.sourceText) :
            component instanceof RichText ? row.sourceFields._N$string === row.sourceText && actualText === nativeTextExpectation && richTextActualOK :
                row.sourceText === null && nativeTextExpectation === null;
        const graphicsPaths: unknown = component instanceof Graphics ? (component as any).impl?.paths : null;
        const actualGraphicsPaths = component instanceof Graphics ? (Array.isArray(graphicsPaths) ? graphicsPaths.length : -1) : null;
        const graphicsMaterial = component instanceof Graphics ? creatorStaticGraphicsMaterialVerified(component) : null;
        const graphicsSourceMaterialRefs = component instanceof Graphics && Array.isArray(row.sourceFields?._materials) ?
            row.sourceFields._materials.map((value: any) => refId(value && typeof value === 'object' ? value.__uuid__ : value)) : [];
        const graphicsNoDrawChecks = {
            sourceEnabled: row.sourceEnabled === true,
            sourceActive: row.sourceActive === true,
            nativeDisabled: row.nativeEnabledExpected === false && component.enabled === false,
            emptyInitialStream: row.initialCommandStreamEmpty === true,
            fixedEmptySentinel: row.sourceDrawingCommands === 'not-serialized-empty-in-fixed-state',
            sourceMaterialIdsPresent: Array.isArray(row.sourceMaterialIds) && row.sourceMaterialIds.length > 0,
            actualPathsEmpty: actualGraphicsPaths === 0,
            sourceRawGraphicsType: row.sourceFields?.__type__ === 'cc.Graphics',
            sourceRawMaterialFieldsPresent: Array.isArray(row.sourceFields?._materials) && row.sourceFields._materials.length > 0,
            builtinMaterialIdentity: graphicsMaterial?.verified === true,
        };
        const nativeEnabledExpected = row.nativeEnabledExpected;
        const spriteBindingProofOK = row.sourceType !== 'cc.Sprite' ||
            (typeof row.sourceNeedsSpriteBinding === 'boolean' &&
                (row.sourceNeedsSpriteBinding ? row.sourceSpriteFrameUuid === null &&
                    row.nativeSpriteFrameUuidExpected === null && actualSpriteFrame === null :
                    row.sourceSpriteFrameUuid !== null && typeof row.nativeSpriteFrameUuidExpected === 'string' &&
                    actualSpriteFrame === row.nativeSpriteFrameUuidExpected));
        const nativeEnabledPolicyExpected = row.sourceType === 'cc.Sprite' ?
            (row.sourceEnabled && row.sourceNeedsSpriteBinding === false) :
            row.sourceType === 'cc.Graphics' ? false : row.sourceEnabled;
        let noDrawReasonVerified = false;
        if (row.noDrawReason === 'disabled-source')
            noDrawReasonVerified = row.sourceEnabled === false && row.nativeEnabledExpected === nativeEnabledPolicyExpected &&
                component.enabled === nativeEnabledPolicyExpected;
        else if (row.noDrawReason === 'inactive-source')
            noDrawReasonVerified = row.sourceActive === false && row.nativeEnabledExpected === nativeEnabledPolicyExpected &&
                component.enabled === nativeEnabledPolicyExpected;
        else if (row.noDrawReason === 'null-sprite-frame')
            noDrawReasonVerified = component instanceof Sprite && row.sourceSpriteFrameUuid === null &&
                row.nativeSpriteFrameUuidExpected === null && row.sourceNeedsSpriteBinding === true &&
                row.nativeEnabledExpected === nativeEnabledPolicyExpected &&
                component.enabled === nativeEnabledPolicyExpected && actualSpriteFrame === null;
        else if (row.noDrawReason === 'empty-text')
            noDrawReasonVerified = (component instanceof Label || component instanceof RichText) && row.sourceEnabled && row.sourceActive &&
                sourceTextEmpty === true && row.nativeEnabledExpected === true && component.enabled && textIdentityOK &&
                (component instanceof RichText ? richTextSegments(component).length === 0 : actualText === '');
        else if (row.noDrawReason === 'empty-command-stream')
            noDrawReasonVerified = component instanceof Graphics && row.sourceEnabled && row.sourceActive &&
                row.nativeEnabledExpected === false && !component.enabled && row.initialCommandStreamEmpty === true &&
                row.sourceDrawingCommands === 'not-serialized-empty-in-fixed-state' &&
                Array.isArray(row.sourceMaterialIds) && row.sourceMaterialIds.length > 0 && actualGraphicsPaths === 0 &&
                row.sourceFields.__type__ === 'cc.Graphics' && Array.isArray(row.sourceFields._materials) && row.sourceFields._materials.length > 0 &&
                !!graphicsMaterial?.verified;
        const nativeEnabledOK = typeof nativeEnabledExpected === 'boolean' && component.enabled === nativeEnabledExpected;
        const verified = actualNativeType === row.expectedNativeType && nativeEnabledOK &&
            node.active === spec.sourceNodeActive[row.node] && sourceActive === row.sourceActive &&
            spriteBindingProofOK && row.nativeEnabledExpected === nativeEnabledPolicyExpected &&
            noDrawReasonVerified && sourceFieldsOK && richTextActualOK && textIdentityOK &&
            (component instanceof Sprite ? actualSpriteFrame === row.nativeSpriteFrameUuidExpected : row.sourceSpriteFrameUuid === null);
        if (!verified) {
            const checks: Record<string, boolean> = {
                nativeType: actualNativeType === row.expectedNativeType,
                nativeEnabled: nativeEnabledOK,
                nodeActive: node.active === spec.sourceNodeActive[row.node],
                effectiveSourceActive: sourceActive === row.sourceActive,
                nativeEnabledPolicy: row.nativeEnabledExpected === nativeEnabledPolicyExpected,
                spriteBinding: spriteBindingProofOK,
                noDrawReason: noDrawReasonVerified,
                sourceFieldsIdentity: sourceFieldsOK,
                richTextIdentity: richTextActualOK,
                textIdentity: textIdentityOK,
                nonSpriteFrameContract: component instanceof Sprite || row.sourceSpriteFrameUuid === null,
            };
            if (row.noDrawReason === 'empty-command-stream') Object.assign(checks, graphicsNoDrawChecks);
            const sourceMaterialRows = row.sourceFields && Array.isArray(row.sourceFields._materials) ? row.sourceFields._materials : [];
            fail('CREATOR_PROXY_NONDRAW_SOURCE_FIELD_OR_ACTIVITY_MISMATCH', row.sourceId + ':' + JSON.stringify({
                failedChecks: Object.keys(checks).filter(key => !checks[key]),
                expected: {nativeType: row.expectedNativeType, enabled: nativeEnabledPolicyExpected,
                    sourceEnabled: row.sourceEnabled, sourceActive: row.sourceActive,
                    sourceSpriteFrameUuid: row.sourceSpriteFrameUuid, nativeSpriteFrameUuidExpected: row.nativeSpriteFrameUuidExpected,
                    noDrawReason: row.noDrawReason, initialCommandStreamEmpty: row.initialCommandStreamEmpty,
                    sourceDrawingCommands: row.sourceDrawingCommands, sourceMaterialIds: row.sourceMaterialIds,
                    sourceFieldsSha256: row.sourceFieldsSha256},
                actual: {nativeType: actualNativeType, enabled: component.enabled, nodeActive: node.active,
                    spriteFrameUuid: actualSpriteFrame, sourceFieldsJsonMatches: sourceFieldsOK,
                    sourceRawType: row.sourceFields?.__type__ ?? null,
                    sourceRawMaterials: sourceMaterialRows.map((value: any) => value && typeof value === 'object' ? value.__uuid__ ?? null : value),
                    graphicsPathCount: actualGraphicsPaths,
                    graphicsMaterial: graphicsMaterial && {verified: graphicsMaterial.verified, materialUuid: graphicsMaterial.materialUuid,
                        effectUuid: graphicsMaterial.effectUuid, rendererMaterialUuid: graphicsMaterial.rendererMaterialUuid,
                        rendererMaterialMatchesCustom: graphicsMaterial.rendererMaterialMatchesCustom},
                    sourceFieldsJsonLength: row.sourceFieldsJson?.length ?? null}}));
        }
        nonDrawById.set(row.sourceId, row); nonDrawComponents.set(component, row);
        nonDrawReadback.push({sourceId: row.sourceId, nativeId: row.nativeId, node: row.node, sourceType: row.sourceType,
            expectedNativeType: row.expectedNativeType, actualNativeType, componentUuid: component.uuid,
            sourceEnabled: row.sourceEnabled, sourceActive: row.sourceActive,
            componentEnabled: component.enabled, nativeEnabledExpected: row.nativeEnabledExpected!,
            sourceNeedsSpriteBinding: row.sourceNeedsSpriteBinding ?? null,
            nodeActive: node.active, effectiveActive: sourceActive,
            sourceFieldsJson: row.sourceFieldsJson, sourceFieldsSha256: row.sourceFieldsSha256,
            sourceSpriteFrameUuid: row.sourceSpriteFrameUuid, nativeSpriteFrameUuid: actualSpriteFrame,
            sourceSpriteFrameAssetId: row.sourceSpriteFrameAssetId,
            nativeSpriteImageUuidExpected: row.nativeSpriteImageUuidExpected,
            nativeSpriteFrameUuidExpected: row.nativeSpriteFrameUuidExpected,
            sourceText: row.sourceText, actualText, sourceFontId: row.sourceFontId,
            nativeFontAssetId: row.nativeFontAssetId ?? null, nativeFallbackAssetIds: row.nativeFallbackAssetIds ?? null,
            targetSystemFontFamily: row.targetSystemFontFamily ?? null, creatorMarkup,
            noDrawReason: row.noDrawReason ?? null,
            sourceTextEmpty, nativeTextExpectation, initialCommandStreamEmpty: row.initialCommandStreamEmpty ?? null,
            sourceDrawingCommands: row.sourceDrawingCommands ?? null, sourceMaterialIds: row.sourceMaterialIds ?? null,
            graphicsPathCount: actualGraphicsPaths, nativeMaterialUuid: graphicsMaterial?.materialUuid ?? null,
            nativeEffectUuid: graphicsMaterial?.effectUuid ?? null, nativeMaterialVerified: graphicsMaterial?.verified ?? null,
            verified});
    }
    const originalEvents = spec.sourceOriginalDrawEvents;
    if (!Array.isArray(originalEvents)) fail('CREATOR_PROXY_ORIGINAL_SOURCE_QUEUE_MISSING');
    const noDrawIds = new Set(spec.nonDrawRenderers.map(row => row.sourceId));
    const projectedEvents = originalEvents.filter(event => event.kind !== 'renderer' ||
        !noDrawIds.has(event.sourceComponentId || ''));
    if (!equalValue(projectedEvents, spec.sourceDrawEvents)) fail('CREATOR_PROXY_ORIGINAL_QUEUE_PROJECTION_MISMATCH');
    if (!Array.isArray(spec.sourceNonDrawRenderers) || spec.sourceNonDrawRenderers.length !== spec.nonDrawRenderers.length)
        fail('CREATOR_PROXY_NON_DRAW_SOURCE_MAPPING_COUNT_MISMATCH');
    const mappings = new Map<string, CreatorProxySourceNonDrawMapping>();
    for (const mapping of spec.sourceNonDrawRenderers) {
        if (!mapping.sourceComponentId || mappings.has(mapping.sourceComponentId))
            fail('CREATOR_PROXY_NON_DRAW_SOURCE_MAPPING_DUPLICATE', mapping.sourceComponentId);
        const row = nonDrawById.get(mapping.sourceComponentId);
        if (!row || row.node !== mapping.node || row.noDrawReason !== mapping.noDrawReason)
            fail('CREATOR_PROXY_NON_DRAW_SOURCE_MAPPING_IDENTITY_MISMATCH', mapping.sourceComponentId);
        mappings.set(mapping.sourceComponentId, mapping);
    }
    const originalRendererIds = originalEvents.filter(event => event.kind === 'renderer').map(event => event.sourceComponentId || '');
    if (new Set(originalRendererIds).size !== originalRendererIds.length) fail('CREATOR_PROXY_ORIGINAL_QUEUE_DUPLICATE_RENDERER');
    for (const event of originalEvents) {
        if (event.kind !== 'renderer') continue;
        const id = event.sourceComponentId || '';
        const node = rowsById.get(id)?.node ?? nonDrawById.get(id)?.node;
        if (!node || node !== event.node) fail('CREATOR_PROXY_ORIGINAL_QUEUE_RENDERER_UNMAPPED', id);
    }
    for (const row of spec.nonDrawRenderers) {
        const mapping = mappings.get(row.sourceId)!;
        const eventIndices = originalEvents.map((event, index) => event.kind === 'renderer' && event.sourceComponentId === row.sourceId ? index : -1)
            .filter(index => index >= 0);
        if (eventIndices.length > 1 ||
            (eventIndices.length === 1 && (mapping.disposition !== 'source-render-event' || mapping.sourceEventIndex !== eventIndices[0])) ||
            (eventIndices.length === 0 && (mapping.disposition !== 'source-component-only' || mapping.sourceEventIndex !== null)))
            fail('CREATOR_PROXY_NON_DRAW_SOURCE_EVENT_INDEX_MISMATCH', row.sourceId);
        if (row.noDrawReason === 'empty-command-stream' && !originalRendererIds.includes(row.sourceId))
            fail('CREATOR_PROXY_EMPTY_GRAPHICS_SOURCE_EVENT_MISSING', row.sourceId);
    }
    const drawEvents = spec.sourceDrawEvents.filter(event => event.kind === 'renderer');
    if (drawEvents.length !== spec.renderers.length) fail('CREATOR_PROXY_RENDERER_EVENT_CONTRACT_COUNT_MISMATCH');
    const seenEvents = new Set<string>();
    for (const event of drawEvents) {
        const id = event.sourceComponentId || '', row = rowsById.get(id);
        if (!row || row.node !== event.node || seenEvents.has(id)) fail('CREATOR_PROXY_RENDERER_EVENT_IDENTITY_MISMATCH', id);
        seenEvents.add(id);
    }
    for (const id of spec.sourceNodeIds) {
        const node = nodes.get(id);
        if (!node) fail('CREATOR_PROXY_SOURCE_NODE_MISSING', id);
        for (const renderer of node.getComponents(UIRenderer)) {
            if (isMaskBacking(node, renderer)) continue;
            if (!claimed.has(renderer) && !nonDrawComponents.has(renderer)) fail('CREATOR_PROXY_UNCOVERED_SOURCE_UIRENDERER', id + ':' + renderer.constructor.name);
        }
        for (const richText of node.getComponents(RichText)) {
            if (!claimed.has(richText) && !nonDrawComponents.has(richText)) fail('CREATOR_PROXY_UNCOVERED_SOURCE_RICHTEXT', id);
        }
    }
    return nonDrawReadback;
}
function richTextSegments(renderer: RichText): Node[] {
    return renderer.node.children.filter(child => isGeneratedRichTextSegment(renderer.node, child));
}
function segmentRenderer(node: Node): UIRenderer {
    const renderers = node.getComponents(UIRenderer);
    if (renderers.length !== 1) fail('CREATOR_PROXY_RICHTEXT_SEGMENT_RENDERER_COUNT', node.name);
    return renderers[0];
}
function richTextSegmentFingerprint(renderer: RichText): unknown[] {
    return richTextSegments(renderer).map((node, index) => {
        const childRenderer = segmentRenderer(node);
        const type = childRenderer instanceof Label ? 'cc.Label' : childRenderer instanceof Sprite ? 'cc.Sprite' : '';
        if (!type) fail('CREATOR_PROXY_RICHTEXT_SEGMENT_TYPE_UNSUPPORTED', node.name);
        return { index, name: node.name, active: node.active, type, renderer: rendererFingerprint(childRenderer, type) };
    });
}
function rendererFingerprint(renderer: Component, type: string, includeGeneratedSegments = true): string {
    if (type === 'cc.RichText') {
        const rich = renderer as RichText;
        const base = { type, enabled: rich.enabled, string: rich.string, font: refId(rich.font), useSystemFont: rich.useSystemFont,
            fontFamily: rich.fontFamily, imageAtlas: refId(rich.imageAtlas), fontSize: rich.fontSize,
            fontColor: colorValue(rich.fontColor), maxWidth: rich.maxWidth, lineHeight: rich.lineHeight,
            horizontalAlign: rich.horizontalAlign, verticalAlign: rich.verticalAlign, cacheMode: rich.cacheMode,
            handleTouchEvent: rich.handleTouchEvent, generatedSegments: includeGeneratedSegments ? richTextSegmentFingerprint(rich) : null };
        return JSON.stringify(base);
    }
    const nativeRenderer = renderer as UIRenderer;
    const base: any = { type, enabled: nativeRenderer.enabled, color: colorValue(nativeRenderer.color),
        customMaterial: refId(nativeRenderer.customMaterial), sharedMaterials: nativeRenderer.sharedMaterials.map(refId) };
    if (type === 'cc.Sprite') {
        const sprite = renderer as Sprite;
        Object.assign(base, { frame: refId(sprite.spriteFrame), atlas: refId(sprite.spriteAtlas), spriteType: sprite.type,
            fillType: sprite.fillType, fillStart: sprite.fillStart, fillRange: sprite.fillRange,
            fillCenter: [sprite.fillCenter.x, sprite.fillCenter.y], trim: sprite.trim, sizeMode: sprite.sizeMode });
    } else if (type === 'cc.Label') {
        const label = renderer as Label;
        Object.assign(base, { string: label.string, font: refId(label.font), fontFamily: label.fontFamily,
            fontSize: label.fontSize, lineHeight: label.lineHeight, spacingX: label.spacingX, overflow: label.overflow,
            wrap: label.enableWrapText, horizontalAlign: label.horizontalAlign, verticalAlign: label.verticalAlign,
            cacheMode: label.cacheMode, bold: label.isBold, italic: label.isItalic, enableOutline: label.enableOutline,
            outlineColor: colorValue(label.outlineColor), outlineWidth: label.outlineWidth,
            enableShadow: label.enableShadow, shadowColor: colorValue(label.shadowColor),
            shadowOffset: [label.shadowOffset.x, label.shadowOffset.y], shadowBlur: label.shadowBlur });
    } else if (type === 'sp.Skeleton') {
        const skeleton: any = renderer;
        Object.assign(base, { skeletonData: refId(skeleton.skeletonData), animation: skeleton.animation,
            skin: skeleton.defaultSkin, defaultAnimation: skeleton.defaultAnimation,
            premultipliedAlpha: skeleton.premultipliedAlpha, timeScale: skeleton.timeScale,
            useTint: skeleton.useTint, enableBatch: skeleton.enableBatch, paused: skeleton.paused, loop: skeleton.loop,
            cacheMode: skeleton.cacheMode, sockets: Array.from(skeleton.socketNodes?.values?.() || []).length });
    } else if (type === 'cc.Graphics') {
        const graphics: any = renderer;
        const paths = graphics.impl?.paths || [];
        if (paths.length !== 0) fail('CREATOR_PROXY_GRAPHICS_SOURCE_COMMANDS_NOT_EMPTY', type);
        Object.assign(base, { pathCount: paths.length, lineWidth: graphics.lineWidth, lineJoin: graphics.lineJoin,
            lineCap: graphics.lineCap, strokeColor: colorValue(graphics.strokeColor), fillColor: colorValue(graphics.fillColor),
            miterLimit: graphics.miterLimit });
    } else {
        fail('CREATOR_PROXY_RENDERER_TYPE_UNSUPPORTED', type);
    }
    return JSON.stringify(base);
}
function boundedFingerprintDiff(sourceFingerprint: string, proxyFingerprint: string, maxDifferences = 16): Array<{field: string; source: unknown; proxy: unknown}> {
    let source: any, proxy: any;
    try { source = JSON.parse(sourceFingerprint); proxy = JSON.parse(proxyFingerprint); }
    catch (_) { return [{field: '$', source: sourceFingerprint.slice(0, 160), proxy: proxyFingerprint.slice(0, 160)}]; }
    const differences: Array<{field: string; source: unknown; proxy: unknown}> = [];
    const parseEmbeddedObject = (value: unknown): any | null => {
        if (typeof value !== 'string' || value.length < 2 || value[0] !== '{') return null;
        try {
            const parsed = JSON.parse(value);
            return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null;
        } catch (_) { return null; }
    };
    const preview = (value: any): unknown => {
        const serialized = JSON.stringify(value);
        return serialized.length <= 160 ? value : serialized.slice(0, 157) + '...';
    };
    const visit = (path: string, left: any, right: any): void => {
        if (differences.length >= maxDifferences || equalValue(left, right)) return;
        if (typeof left === 'string' && typeof right === 'string') {
            const parsedLeft = parseEmbeddedObject(left), parsedRight = parseEmbeddedObject(right);
            if (parsedLeft && parsedRight) { visit(path, parsedLeft, parsedRight); return; }
        }
        if (Array.isArray(left) && Array.isArray(right)) {
            if (left.length !== right.length) differences.push({field: path + '.length', source: left.length, proxy: right.length});
            const count = Math.min(left.length, right.length);
            for (let index = 0; index < count && differences.length < maxDifferences; index++)
                visit(path + '[' + index + ']', left[index], right[index]);
            return;
        }
        if (left && right && typeof left === 'object' && typeof right === 'object' && !Array.isArray(left) && !Array.isArray(right)) {
            const keys = Array.from(new Set(Object.keys(left).concat(Object.keys(right)))).sort();
            for (const key of keys) {
                if (differences.length >= maxDifferences) break;
                if (!(key in left) || !(key in right)) differences.push({field: path ? path + '.' + key : key,
                    source: key in left ? preview(left[key]) : '<missing>', proxy: key in right ? preview(right[key]) : '<missing>'});
                else visit(path ? path + '.' + key : key, left[key], right[key]);
            }
            return;
        }
        differences.push({field: path || '$', source: preview(left), proxy: preview(right)});
    };
    visit('', source, proxy);
    return differences;
}
function boundedMaskFailureSummary(row: CreatorProxyMaskReadback, maxChars = 900): string {
    const failedChecks = Object.keys(row.checks).filter(key => !row.checks[key]);
    const summary: any = {sourceId: row.sourceId, failedChecks};
    const maskOrSpriteChecks = failedChecks.some(key => ['maskPresent','expectedSourceMaskPresent','sourceAndProxyMaskRefs',
        'markerSourceComponentId','markerMaskType','maskType','enabled','inverted','alphaThreshold','backingType','spriteFrame',
        'sourceAndNativeSpriteFields'].includes(key));
    if (maskOrSpriteChecks) {
        summary.mask = {expectedType: row.expectedMaskType, nativeType: row.nativeMaskType,
            expectedEnabled: row.expectedMaskEnabled, nativeEnabled: row.enabled,
            expectedInverted: row.expectedInverted, nativeInverted: row.inverted,
            expectedAlpha: row.expectedAlphaThreshold, sourceAlpha: row.sourceAlphaThreshold, nativeAlpha: row.alphaThreshold};
        summary.sprite = {expectedFrame: row.expectedSpriteFrameUuid, sourceFrame: row.sourceSpriteFrameUuid,
            nativeFrame: row.spriteFrameUuid, expectedNativeFrame: row.nativeSpriteFrameExpectedUuid,
            sourceType: row.sourceSpriteType, nativeType: row.nativeSpriteType,
            sourceEnabled: row.sourceSpriteEnabled, nativeEnabled: row.nativeSpriteEnabled};
    }
    if (failedChecks.some(key => key.startsWith('identity'))) summary.identity = {
        sourceId: row.identitySourceId, nativeId: row.identityNativeId, maskReference: row.identityNativeMaskRefMatches};
    if (failedChecks.includes('sourceAndNativeSpriteFields') && row.sourceSpriteFingerprint && row.nativeSpriteFingerprint)
        summary.spriteRendererDiff = boundedFingerprintDiff(row.sourceSpriteFingerprint, row.nativeSpriteFingerprint, 3);
    if (failedChecks.some(key => ['transform','worldMatrix','uiContentSize','uiAnchor'].includes(key))) summary.transform = {
        worldMatrixVerified: row.checks.worldMatrix, uiContentSizeVerified: row.checks.uiContentSize,
        uiAnchorVerified: row.checks.uiAnchor, sourceWorld: row.sourceWorldMatrix, nativeWorld: row.nativeWorldMatrix,
        sourceSizeAnchor: row.sourceSizeAnchor, nativeSizeAnchor: row.nativeSizeAnchor,
        sourceLocal: row.sourceLocalTransform, nativeLocal: row.nativeLocalTransform};
    if (failedChecks.includes('opacity')) summary.opacity = {source: row.sourceOpacityFactor, native: row.nativeOpacityFactor};
    if (failedChecks.includes('layer')) summary.layer = {source: row.sourceLayer, native: row.nativeLayer};
    const serialized = JSON.stringify(summary);
    return serialized.length <= maxChars ? serialized : serialized.slice(0, maxChars - 3) + '...';
}
function copyRenderer(source: Component, proxyNode: Node, type: string, sourceComponentId = '', existingTarget?: Component): Component {
    // RichText regenerates its label segments synchronously from onEnable and
    // from each serialized field setter. Keep the node inactive until every
    // field is copied so the proxy is laid out once from its final state. This
    // avoids cycling half-configured segments through Creator's shared Label
    // pool, whose outline defaults and cached layout state otherwise depend on
    // which RichText happened to initialize first.
    const deferRichTextActivation = type === 'cc.RichText';
    if (deferRichTextActivation) {
        if (!proxyNode.activeInHierarchy) fail('CREATOR_PROXY_RICHTEXT_NODE_NOT_ACTIVE_AT_CREATE', sourceComponentId);
        proxyNode.active = false;
    }
    let restoreRichTextActivation = deferRichTextActivation;
    try {
    const uiSource = source.node.getComponent(UITransform);
    const uiProxy = proxyNode.getComponent(UITransform) || proxyNode.addComponent(UITransform);
    if (uiSource) {
        uiProxy.setContentSize(uiSource.contentSize);
        uiProxy.setAnchorPoint(uiSource.anchorPoint);
    }
    const renderer: any = source;
    let proxy: any;
    if (existingTarget) {
        if (existingTarget.node !== proxyNode) fail('CREATOR_PROXY_RENDERER_EXISTING_TARGET_NODE_MISMATCH', sourceComponentId);
        proxy = existingTarget;
    } else if (type === 'cc.Sprite') proxy = proxyNode.addComponent(Sprite);
    else if (type === 'cc.Label') proxy = proxyNode.addComponent(Label);
    else if (type === 'sp.Skeleton') proxy = proxyNode.addComponent('sp.Skeleton');
    else if (type === 'cc.Graphics') proxy = proxyNode.addComponent(Graphics);
    else if (type === 'cc.RichText') proxy = proxyNode.addComponent(RichText);
    else fail('CREATOR_PROXY_RENDERER_TYPE_UNSUPPORTED', type);
    proxy.enabled = renderer.enabled;
    if (type !== 'cc.RichText') {
        proxy.color = new Color(renderer.color.r, renderer.color.g, renderer.color.b, renderer.color.a);
        proxy.sharedMaterials = renderer.sharedMaterials.slice();
        proxy.customMaterial = renderer.customMaterial;
        (proxy as UIRenderer).priority = SortingLayers.getDefaultPriority();
    }
    if (type === 'cc.Sprite') {
        proxy.spriteAtlas = renderer.spriteAtlas; proxy.spriteFrame = renderer.spriteFrame;
        proxy.type = renderer.type; proxy.fillType = renderer.fillType; proxy.fillStart = renderer.fillStart;
        proxy.fillRange = renderer.fillRange; proxy.fillCenter = renderer.fillCenter;
        proxy.trim = renderer.trim; proxy.sizeMode = renderer.sizeMode;
    } else if (type === 'cc.Label') {
        for (const field of ['string','font','fontFamily','fontSize','lineHeight','spacingX','overflow','enableWrapText',
            'horizontalAlign','verticalAlign','cacheMode','isBold','isItalic','enableOutline','outlineWidth',
            'enableShadow','shadowBlur']) proxy[field] = renderer[field];
        proxy.outlineColor = new Color(renderer.outlineColor.r, renderer.outlineColor.g, renderer.outlineColor.b, renderer.outlineColor.a);
        proxy.shadowColor = new Color(renderer.shadowColor.r, renderer.shadowColor.g, renderer.shadowColor.b, renderer.shadowColor.a);
        proxy.shadowOffset = renderer.shadowOffset;
    } else if (type === 'cc.Graphics') {
        if ((renderer.impl?.paths || []).length !== 0) fail('CREATOR_PROXY_GRAPHICS_SOURCE_COMMANDS_NOT_EMPTY', type);
        proxy.lineWidth = renderer.lineWidth; proxy.lineJoin = renderer.lineJoin; proxy.lineCap = renderer.lineCap;
        proxy.strokeColor = new Color(renderer.strokeColor.r, renderer.strokeColor.g, renderer.strokeColor.b, renderer.strokeColor.a);
        proxy.fillColor = new Color(renderer.fillColor.r, renderer.fillColor.g, renderer.fillColor.b, renderer.fillColor.a);
        proxy.miterLimit = renderer.miterLimit;
    } else if (type === 'cc.RichText') {
        const rich = renderer as RichText, clone = proxy as RichText;
        clone.useSystemFont = rich.useSystemFont;
        clone.font = rich.font;
        clone.fontFamily = rich.fontFamily;
        clone.imageAtlas = rich.imageAtlas;
        clone.fontSize = rich.fontSize;
        clone.fontColor = new Color(rich.fontColor.r, rich.fontColor.g, rich.fontColor.b, rich.fontColor.a);
        clone.maxWidth = rich.maxWidth;
        clone.lineHeight = rich.lineHeight;
        clone.horizontalAlign = rich.horizontalAlign;
        clone.verticalAlign = rich.verticalAlign;
        clone.cacheMode = rich.cacheMode;
        clone.handleTouchEvent = rich.handleTouchEvent;
        clone.string = rich.string;
    } else if (type === 'sp.Skeleton') {
        const clone: any = proxy;
        const src: any = renderer;
        if (src.socketNodes && src.socketNodes.size) fail('CREATOR_PROXY_SPINE_SOCKET_REFERENCES_UNSUPPORTED', type);
        clone.skeletonData = src.skeletonData;
        clone.premultipliedAlpha = src.premultipliedAlpha; clone.timeScale = src.timeScale;
        clone.useTint = src.useTint; clone.enableBatch = src.enableBatch; clone.paused = src.paused;
        clone.cacheMode = src.cacheMode; clone.loop = src.loop;
        clone.defaultSkin = src.defaultSkin; clone.defaultAnimation = src.defaultAnimation;
        if (src.animation && src.animation !== src.defaultAnimation) fail('CREATOR_PROXY_SPINE_RUNTIME_POSE_NOT_STATIC', type);
        if (src.defaultSkin) clone.setSkin(src.defaultSkin);
        if (src.defaultAnimation) clone.setAnimation(0, src.defaultAnimation, src.loop);
    }
    // Sprite.spriteFrame/sizeMode may call Sprite._applySpriteSize and mutate
    // the owning UITransform. The source node's authored size and anchor are
    // independent source evidence; restore them after all renderer setters.
    if (uiSource) {
        uiProxy.setContentSize(uiSource.contentSize);
        uiProxy.setAnchorPoint(uiSource.anchorPoint);
    }
    if (restoreRichTextActivation) {
        proxyNode.active = true;
        restoreRichTextActivation = false;
    }
    if (type === 'cc.RichText')
        syncGeneratedRichTextSegments(source as RichText, proxy as RichText, sourceComponentId);
    const sourceFingerprint = rendererFingerprint(source, type), proxyFingerprint = rendererFingerprint(proxy, type);
    if (!equalValue(sourceFingerprint, proxyFingerprint))
        fail('CREATOR_PROXY_TYPED_RENDERER_FIELDS_DIVERGED', type + ':' + sourceComponentId + ':' +
            JSON.stringify({differences: boundedFingerprintDiff(sourceFingerprint, proxyFingerprint)}));
    return proxy as Component;
    } finally {
        if (restoreRichTextActivation && proxyNode.isValid) proxyNode.active = true;
    }
}
function addRendererSortRank(component: Component, sourceType: string, order: number): UIRenderer[] {
    const targets = sourceType === 'cc.RichText' ? richTextSegments(component as RichText).map(segmentRenderer) :
        [component as UIRenderer];
    for (const renderer of targets) {
        if (!(renderer instanceof UIRenderer)) fail('CREATOR_PROXY_SORT_TARGET_NOT_UIRENDERER', sourceType);
        const sorting = renderer.node.getComponent(Sorting2D) || renderer.node.addComponent(Sorting2D);
        sorting.sortingOrder = order;
    }
    return targets;
}
function rendererSortRankVerified(component: Component, sourceType: string, order: number): boolean {
    const targets = sourceType === 'cc.RichText' ? richTextSegments(component as RichText).map(segmentRenderer) :
        [component as UIRenderer];
    return targets.every(renderer => renderer instanceof UIRenderer &&
        renderer.node.getComponent(Sorting2D)?.sortingOrder === order);
}
const PLANAR_EPSILON = 1e-8;
function planarLocalForCollapsedParent(parent: Mat4, source: Mat4, nodeName: string): Mat4 {
    // Creator UI occupies the XY plane. A zero Z scale makes the parent's full
    // 4x4 matrix singular while leaving its XY affine transform invertible.
    // Handle only that evidenced case; tilted planes and differing world-Z
    // positions cannot be represented under the collapsed parent.
    const planeTerms = [parent.m02, parent.m06, parent.m08, parent.m09, parent.m10,
        source.m02, source.m06, source.m08, source.m09, source.m10,
        parent.m03, parent.m07, parent.m11, source.m03, source.m07, source.m11];
    if (planeTerms.some(value => !Number.isFinite(value) || Math.abs(value) > PLANAR_EPSILON) ||
        Math.abs(parent.m15 - 1) > PLANAR_EPSILON || Math.abs(source.m15 - 1) > PLANAR_EPSILON ||
        Math.abs(source.m14 - parent.m14) > PLANAR_EPSILON)
        fail('CREATOR_PROXY_COLLAPSED_PARENT_NOT_COPLANAR_2D', nodeName);
    const det = parent.m00 * parent.m05 - parent.m04 * parent.m01;
    if (!Number.isFinite(det) || Math.abs(det) <= 1e-10)
        fail('CREATOR_PROXY_COLLAPSED_PARENT_XY_NOT_INVERTIBLE', nodeName);
    const i00 = parent.m05 / det, i01 = -parent.m04 / det;
    const i10 = -parent.m01 / det, i11 = parent.m00 / det;
    const local = new Mat4();
    local.m00 = i00 * source.m00 + i01 * source.m01;
    local.m01 = i10 * source.m00 + i11 * source.m01;
    local.m02 = 0;
    local.m04 = i00 * source.m04 + i01 * source.m05;
    local.m05 = i10 * source.m04 + i11 * source.m05;
    local.m06 = 0;
    local.m08 = 0; local.m09 = 0; local.m10 = 1; local.m11 = 0;
    const dx = source.m12 - parent.m12, dy = source.m13 - parent.m13;
    local.m12 = i00 * dx + i01 * dy;
    local.m13 = i10 * dx + i11 * dy;
    local.m14 = 0;
    return local;
}
function cross3(a: number[], b: number[]): number[] {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}
function normalize3(value: number[], nodeName: string): number[] {
    const length = Math.hypot(value[0], value[1], value[2]);
    if (!Number.isFinite(length) || length === 0) fail('CREATOR_PROXY_ZERO_SCALE_SYNTHETIC_BASIS_DEGENERATE', nodeName);
    return value.map(channel => channel / length);
}
function withSyntheticZeroScaleBasis(local: Mat4, nodeName: string, authoredWorldZeroAxes?: boolean[]): {matrix: Mat4; zeroAxes: boolean[]} {
    const columns = [
        [local.m00, local.m01, local.m02],
        [local.m04, local.m05, local.m06],
        [local.m08, local.m09, local.m10],
    ];
    const lengths = columns.map(column => Math.hypot(column[0], column[1], column[2]));
    const zeroAxes = lengths.map((length, index) => length === 0 || authoredWorldZeroAxes?.[index] === true);
    const numericalTolerance = Math.max(1, ...lengths) * 1e-8;
    for (let index = 0; index < 3; index++) if (authoredWorldZeroAxes?.[index] && lengths[index] > numericalTolerance)
        fail('CREATOR_PROXY_ZERO_SCALE_AXIS_MATRIX_MISMATCH', nodeName + ':' + index + ':' + lengths[index]);
    if (!zeroAxes.some(Boolean)) return {matrix: new Mat4(local), zeroAxes};
    const basis: Array<number[] | null> = columns.map((column, index) => zeroAxes[index] ? null :
        column.map(value => value / lengths[index]));
    const known = basis.map((axis, index) => axis ? index : -1).filter(index => index >= 0);
    for (let left = 0; left < known.length; left++) for (let right = left + 1; right < known.length; right++) {
        const a = basis[known[left]]!, b = basis[known[right]]!;
        const dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
        if (!Number.isFinite(dot) || Math.abs(dot) > 1e-7)
            fail('CREATOR_PROXY_ZERO_SCALE_WITH_SHEAR', nodeName);
    }
    if (known.length === 2) {
        if (zeroAxes[0]) basis[0] = normalize3(cross3(basis[1]!, basis[2]!), nodeName);
        else if (zeroAxes[1]) basis[1] = normalize3(cross3(basis[2]!, basis[0]!), nodeName);
        else basis[2] = normalize3(cross3(basis[0]!, basis[1]!), nodeName);
    } else if (known.length === 1) {
        const axis = known[0], current = basis[axis]!;
        const reference = Math.abs(current[2]) < 0.9 ? [0, 0, 1] : [0, 1, 0];
        if (axis === 0) {
            basis[1] = normalize3(cross3(reference, current), nodeName);
            basis[2] = normalize3(cross3(current, basis[1]!), nodeName);
        } else if (axis === 1) {
            basis[2] = normalize3(cross3(current, reference), nodeName);
            basis[0] = normalize3(cross3(basis[1]!, basis[2]!), nodeName);
        } else {
            basis[0] = normalize3(cross3(reference, current), nodeName);
            basis[1] = normalize3(cross3(current, basis[0]!), nodeName);
        }
    } else {
        basis[0] = [1, 0, 0]; basis[1] = [0, 1, 0]; basis[2] = [0, 0, 1];
    }
    const copy = new Mat4(local);
    const setters: Array<(x: number, y: number, z: number) => void> = [
        (x, y, z) => { copy.m00 = x; copy.m01 = y; copy.m02 = z; },
        (x, y, z) => { copy.m04 = x; copy.m05 = y; copy.m06 = z; },
        (x, y, z) => { copy.m08 = x; copy.m09 = y; copy.m10 = z; },
    ];
    for (let index = 0; index < 3; index++) if (zeroAxes[index]) setters[index](basis[index]![0], basis[index]![1], basis[index]![2]);
    return {matrix: copy, zeroAxes};
}
function copyWorldNode(source: Node, target: Node, parent: Node, layer: number, withUITransform = true): void {
    // Start from the authored source world matrix. setParent(..., true) would
    // preserve the new proxy Node's identity world matrix, not the source's.
    // Convert sourceWorld into the chosen proxy parent's local space explicitly;
    // Node.matrix uses Creator's Mat4.toSRT decomposition and handles negative
    // determinant reflections by moving the sign to X plus a compensating
    // rotation. The world-matrix readback below rejects any unrepresentable
    // shear introduced by a cross-scope proxy parent.
    const sourceWorld = new Mat4(source.worldMatrix), parentWorld = new Mat4(parent.worldMatrix);
    const determinant = Mat4.determinant(parentWorld);
    let localMatrix: Mat4, collapsedParent = false;
    if (!Number.isFinite(determinant)) fail('CREATOR_PROXY_PARENT_WORLD_MATRIX_NONFINITE', source.name);
    if (Math.abs(determinant) <= 1e-10) {
        localMatrix = planarLocalForCollapsedParent(parentWorld, sourceWorld, source.name);
        collapsedParent = true;
    } else {
        const parentInverse = Mat4.invert(new Mat4(), parentWorld);
        localMatrix = Mat4.multiply(new Mat4(), parentInverse, sourceWorld);
    }
    const localValues = [localMatrix.m00,localMatrix.m01,localMatrix.m02,localMatrix.m03,
        localMatrix.m04,localMatrix.m05,localMatrix.m06,localMatrix.m07,
        localMatrix.m08,localMatrix.m09,localMatrix.m10,localMatrix.m11,
        localMatrix.m12,localMatrix.m13,localMatrix.m14,localMatrix.m15];
    if (localValues.some(value => !Number.isFinite(value))) fail('CREATOR_PROXY_LOCAL_MATRIX_NONFINITE', source.name);
    target.setParent(parent, false);
    const authoredWorldZeroAxes = collapsedParent ? undefined : [
        Math.hypot(sourceWorld.m00, sourceWorld.m01, sourceWorld.m02) === 0,
        Math.hypot(sourceWorld.m04, sourceWorld.m05, sourceWorld.m06) === 0,
        Math.hypot(sourceWorld.m08, sourceWorld.m09, sourceWorld.m10) === 0,
    ];
    const decomposition = withSyntheticZeroScaleBasis(localMatrix, source.name, authoredWorldZeroAxes);
    target.matrix = decomposition.matrix;
    if (decomposition.zeroAxes.some(Boolean)) {
        const decomposedScale = target.scale;
        target.setScale(decomposition.zeroAxes[0] ? 0 : decomposedScale.x,
            decomposition.zeroAxes[1] ? 0 : decomposedScale.y,
            decomposition.zeroAxes[2] ? 0 : decomposedScale.z);
    } else if (collapsedParent) {
        // The planar inverse supplies the unobservable collapsed Z basis as 1.
        // The source world matrix check below proves the resulting XY plane.
        target.setScale(target.scale.x, target.scale.y, 1);
    }
    const sourceUI = source.getComponent(UITransform);
    if (withUITransform) {
        const targetUI = target.getComponent(UITransform) || target.addComponent(UITransform);
        if (sourceUI) {
            targetUI.setContentSize(sourceUI.contentSize);
            targetUI.setAnchorPoint(sourceUI.anchorPoint);
        }
    } else if (target.getComponent(UITransform)) {
        fail('CREATOR_PROXY_STRUCTURAL_ROOT_MUST_NOT_HAVE_UI_TRANSFORM', target.name);
    }
    target.layer = layer;
    if (!matricesMatch(source, target)) fail('CREATOR_PROXY_WORLD_MATRIX_NOT_EXACT', source.name);
}
function authoredOpacityWithin(node: Node, boundary: Node): number {
    let opacity = 1, current: Node | null = node;
    while (current) {
        if (current === boundary) return opacity;
        const component = current.getComponent(UIOpacity);
        if (component?.enabled) opacity *= component.opacity / 255;
        current = current.parent;
    }
    fail('CREATOR_PROXY_OPACITY_BOUNDARY_MISSING', node.name);
}
function opacityPathReadback(node: Node, boundary: Node, sourceNodeIds: Map<Node, string>): CreatorProxyGraphicReadback['sourceOpacityPath'] {
    const rows: CreatorProxyGraphicReadback['sourceOpacityPath'] = [];
    let current: Node | null = node;
    while (current) {
        if (current === boundary) return rows;
        const matches = current.getComponents(UIOpacity);
        if (matches.length > 1) fail('CREATOR_PROXY_OPACITY_COMPONENT_AMBIGUOUS', current.name);
        const component = matches[0] || null;
        const enabled = component ? component.enabled : null;
        const opacity = component ? component.opacity : null;
        rows.push({nodeUuid: current.uuid, nodeName: current.name, sourceNodeId: sourceNodeIds.get(current) ||
                current.getComponent(CreatorStaticSortQueueProxyMarker)?.sourceNode || null,
            componentUuid: component?.uuid || null, enabled, opacity,
            localFactor: component?.enabled ? component.opacity / 255 : 1});
        if (rows.length > 64) fail('CREATOR_PROXY_OPACITY_PATH_DEPTH_EXCEEDED', node.name);
        current = current.parent;
    }
    fail('CREATOR_PROXY_OPACITY_BOUNDARY_MISSING', node.name);
}
function setOpacityProjection(source: Node, proxy: Node, parentOpacity: number, sourceRoot: Node, proxyRoot: Node): number {
    const desired = authoredOpacityWithin(source, sourceRoot);
    const local = parentOpacity > 1e-7 ? desired / parentOpacity : desired <= 1e-7 ? 1 : NaN;
    if (!Number.isFinite(local) || local < -1e-6 || local > 1.000001)
        fail('CREATOR_PROXY_OPACITY_SCOPE_MISMATCH', source.name);
    const opacity = proxy.getComponent(UIOpacity) || proxy.addComponent(UIOpacity);
    opacity.opacity = Math.max(0, Math.min(255, local * 255));
    if (Math.abs(authoredOpacityWithin(proxy, proxyRoot) - desired) > 1 / 255 + 1e-6)
        fail('CREATOR_PROXY_OPACITY_NOT_EXACT', source.name);
    return desired;
}
function addIdentity(node: Node, fields: Partial<CreatorStaticSortQueueProxyMarker>): CreatorStaticSortQueueProxyMarker {
    const identity = node.addComponent(CreatorStaticSortQueueProxyMarker);
    Object.assign(identity, fields);
    return identity;
}

function sourceSortIdentityRows(specs: CreatorProxySpec[], nodes: Map<string, Node>, createMissing: boolean): CreatorSourceSortIdentityReadback {
    if (!Array.isArray(specs) || !nodes) fail('CREATOR_PROXY_SOURCE_SORT_IDENTITY_PLAN_INVALID');
    const orderById = new Map<string, CreatorSortOrderField>(), rootsById = new Map<string, CreatorSortRootField>();
    const same = (left: any, right: any): boolean => left.sourceId === right.sourceId && left.nativeId === right.nativeId &&
        left.node === right.node && left.sortOrder === right.sortOrder && left.enabled === right.enabled;
    const sameRoot = (left: any, right: any): boolean => left.sourceId === right.sourceId && left.nativeId === right.nativeId &&
        left.node === right.node && left.enabled === right.enabled;
    for (const spec of specs) {
        if (!spec || !Array.isArray(spec.sourceNodeIds) || !Array.isArray(spec.sourceSortOrderFields) || !Array.isArray(spec.sourceSortRoots))
            fail('CREATOR_PROXY_SOURCE_SORT_IDENTITY_SPEC_INVALID');
        for (const nodeId of spec.sourceNodeIds) if (!nodes.has(nodeId)) fail('CREATOR_PROXY_SOURCE_SORT_IDENTITY_NODE_MISSING', nodeId);
        for (const row of spec.sourceSortOrderFields) {
            if (!row || !row.sourceId || !row.nativeId || !row.node || !Number.isFinite(row.sortOrder) || typeof row.enabled !== 'boolean')
                fail('CREATOR_PROXY_SORTORDER_IDENTITY_CONTRACT_INVALID', row?.sourceId || '');
            const previous = orderById.get(row.sourceId);
            if (previous && !same(previous, row)) fail('CREATOR_PROXY_SORTORDER_IDENTITY_CONTRACT_AMBIGUOUS', row.sourceId);
            orderById.set(row.sourceId, row);
        }
        for (const row of spec.sourceSortRoots) {
            if (!row || !row.sourceId || !row.nativeId || !row.node || typeof row.enabled !== 'boolean')
                fail('CREATOR_PROXY_SORTROOT_IDENTITY_CONTRACT_INVALID', row?.sourceId || '');
            const previous = rootsById.get(row.sourceId);
            if (previous && !sameRoot(previous, row)) fail('CREATOR_PROXY_SORTROOT_IDENTITY_CONTRACT_AMBIGUOUS', row.sourceId);
            rootsById.set(row.sourceId, row);
        }
    }
    const allNodes = Array.from(new Set(Array.from(nodes.values())));
    const orderReadback: CreatorSourceSortIdentityReadback['sourceSortOrderFields'] = [];
    for (const row of orderById.values()) {
        const expectedNode = nodes.get(row.node);
        if (!expectedNode) fail('CREATOR_PROXY_SORTORDER_NODE_MISSING', row.sourceId);
        const matches: Array<{node: Node; component: MonkeyStaticSortOrderField}> = [];
        for (const node of allNodes) for (const component of node.getComponents(MonkeyStaticSortOrderField))
            if (component.sourceId === row.sourceId) matches.push({node, component});
        if (matches.length > 1 || (matches.length === 1 && matches[0].node !== expectedNode))
            fail('CREATOR_PROXY_SORTORDER_IDENTITY_DUPLICATE_OR_WRONG_NODE', row.sourceId);
        let identity = matches.length === 1 ? matches[0].component : null;
        if (!identity && createMissing) {
            identity = expectedNode.addComponent(MonkeyStaticSortOrderField);
            identity.sourceId = row.sourceId; identity.nativeId = row.nativeId;
            identity.sourceSortOrder = row.sortOrder; identity.effectiveSourceSortOrder = row.enabled ? row.sortOrder : 0;
            identity.enabledInSource = row.enabled; identity.renderedOnNode = false;
        }
        const verified = !!identity && identity.node === expectedNode && identity.nativeId === row.nativeId && identity.sourceSortOrder === row.sortOrder &&
            identity.effectiveSourceSortOrder === (row.enabled ? row.sortOrder : 0) && identity.enabledInSource === row.enabled &&
            identity.renderedOnNode === false && typeof identity.uuid === 'string' && identity.uuid.length > 0;
        if (!verified) fail('CREATOR_PROXY_SORTORDER_IDENTITY_MISMATCH', row.sourceId + ':expected=' + JSON.stringify(row) +
            ':actual=' + JSON.stringify(identity && {node: identity.node && nodes.get(row.node) === identity.node ? row.node : null,
                nativeId: identity.nativeId, sourceSortOrder: identity.sourceSortOrder,
                effectiveSourceSortOrder: identity.effectiveSourceSortOrder, enabledInSource: identity.enabledInSource,
                renderedOnNode: identity.renderedOnNode}));
        orderReadback.push({...row, componentUuid: identity!.uuid, verified});
    }
    const rootReadback: CreatorSourceSortIdentityReadback['sourceSortRoots'] = [];
    for (const row of rootsById.values()) {
        const expectedNode = nodes.get(row.node);
        if (!expectedNode) fail('CREATOR_PROXY_SORTROOT_NODE_MISSING', row.sourceId);
        const matches: Array<{node: Node; component: CreatorStaticSortRootField}> = [];
        for (const node of allNodes) for (const component of node.getComponents(CreatorStaticSortRootField))
            if (component.sourceId === row.sourceId) matches.push({node, component});
        if (matches.length > 1 || (matches.length === 1 && matches[0].node !== expectedNode))
            fail('CREATOR_PROXY_SORTROOT_IDENTITY_DUPLICATE_OR_WRONG_NODE', row.sourceId);
        let identity = matches.length === 1 ? matches[0].component : null;
        if (!identity && createMissing) {
            identity = expectedNode.addComponent(CreatorStaticSortRootField);
            identity.sourceId = row.sourceId; identity.nativeId = row.nativeId; identity.enabledInSource = row.enabled;
        }
        const verified = !!identity && identity.node === expectedNode && identity.nativeId === row.nativeId && identity.enabledInSource === row.enabled &&
            typeof identity.uuid === 'string' && identity.uuid.length > 0;
        if (!verified) fail('CREATOR_PROXY_SORTROOT_IDENTITY_MISMATCH', row.sourceId + ':expected=' + JSON.stringify(row) +
            ':actual=' + JSON.stringify(identity && {nativeId: identity.nativeId, enabledInSource: identity.enabledInSource}));
        rootReadback.push({...row, componentUuid: identity!.uuid, verified});
    }
    return {sourceSortOrderFields: orderReadback, sourceSortRoots: rootReadback,
        verified: orderReadback.every(row => row.verified) && rootReadback.every(row => row.verified)};
}

/** Adds source-level typed identity components once for all Prefabs before relation preparation. */
export function attachStaticSortSourceIdentities(specs: CreatorProxySpec[], nodes: Map<string, Node>): CreatorSourceSortIdentityReadback {
    return sourceSortIdentityRows(specs, nodes, true);
}

export function createStaticSortQueueProxy(spec: CreatorProxySpec, nodes: Map<string, Node>,
    resolveSprite: (uuid: string) => any): CreatorProxyReadback {
    if (!spec || !nodes || !nodes.has(spec.rootScope)) fail('CREATOR_PROXY_PLAN_INVALID');
    sourceSortIdentityRows([spec], nodes, false);
    assertSourceRendererCoverage(spec, nodes);
    const sourceParents = sourceParentByChild(spec);
    const sourceRoot = nodes.get(spec.rootScope)!;
    if (sourceRoot.getComponentsInChildren(CreatorStaticSortQueueProxyMarker).some(marker =>
        marker.kind === 'root' && marker.sourceRootOwner === sourceRoot && isGeneratedSortProxyRoot(marker.node)))
        fail('CREATOR_PROXY_ROOT_ALREADY_EXISTS', spec.rootScope);
    const reverseIds = new Map<Node, string>(); for (const [id, node] of nodes) reverseIds.set(node, id);
    const nestedProxyRoots: Node[] = [];
    for (const marker of sourceRoot.getComponentsInChildren(CreatorStaticSortQueueProxyMarker)) {
        if (marker.kind !== 'root' || marker.sourceRootOwner === sourceRoot) continue;
        const candidate = marker.node;
        if (!isGeneratedSortProxyRoot(candidate)) continue;
        let ownerInScope = false;
        for (let owner: Node | null = marker.sourceRootOwner; owner; owner = owner.parent)
            if (owner === sourceRoot) { ownerInScope = true; break; }
        if (!ownerInScope) fail('CREATOR_PROXY_NESTED_ROOT_OWNER_OUTSIDE_SOURCE_SCOPE', marker.sourceNode);
        nestedProxyRoots.push(candidate);
    }
    const sourceLayers = new Map<string, number>(), runtimeLayersBefore = new Map<string, number>();
    for (const id of spec.sourceNodeIds) {
        const node = nodes.get(id); if (!node) fail('CREATOR_PROXY_SOURCE_NODE_MISSING', id);
        const authoredLayer = spec.sourceNodeLayers && spec.sourceNodeLayers[id];
        if (!Number.isInteger(authoredLayer)) fail('CREATOR_PROXY_SOURCE_LAYER_CONTRACT_MISSING', id);
        runtimeLayersBefore.set(id, node.layer);
        if (node.layer !== authoredLayer && !nestedPresenter(node, authoredLayer, nestedProxyRoots))
            fail('CREATOR_PROXY_SOURCE_LAYER_UNPROVEN_BEFORE_NESTED_SUSPEND', id + ':expected=' + authoredLayer + ':actual=' + node.layer);
        sourceLayers.set(id, authoredLayer);
    }
    const nestedProxyRootActiveBefore = nestedProxyRoots.map(root => root.active);
    let proxyRoot: Node | null = null, completed = false;
    try {
    for (const root of nestedProxyRoots.slice().sort((a, b) => depth(a) - depth(b))) if (root.active) root.active = false;
    for (const id of spec.sourceNodeIds) nodes.get(id)!.layer = sourceLayers.get(id)!;
    for (const id of spec.sourceNodeIds) if (nodes.get(id)!.layer !== sourceLayers.get(id))
        fail('CREATOR_PROXY_SOURCE_LAYER_RESTORE_MISMATCH', id + ':expected=' + sourceLayers.get(id) + ':actual=' + nodes.get(id)!.layer);
    proxyRoot = new Node('__NativeStaticSortQueueProxy_' + spec.rootScope.replace(/[^a-zA-Z0-9]/g, '_').slice(-24));
    // A structural child under an authored Layout must not enter its child
    // layout list. Creator Layout only includes active children with UITransform.
    copyWorldNode(sourceRoot, proxyRoot, sourceRoot, sourceRoot.layer, false);
    addIdentity(proxyRoot, { kind: 'root', sourceNode: spec.rootScope, sourceRootOwner: sourceRoot,
        generatedRootActiveBefore: true });
    const maskByNode = new Map(spec.masks.map(mask => [mask.node, mask]));
    const rendererById = new Map(spec.renderers.map(renderer => [renderer.sourceComponentId, renderer]));
    const containerStack: Node[] = [proxyRoot]; const maskStack: string[] = [];
    const proxyNodes: Node[] = [proxyRoot];
    // The outer source root is common to both original and proxy branches; it
    // is excluded from the per-branch projection product below.
    const proxyOpacity = new Map<Node, number>([[proxyRoot, 1]]);
    const sourceRendererRefs = new Map<string, Component>(), proxyRendererRefs = new Map<string, Component>();
    const sourceMaskRefs = new Map<string, Mask>(), proxyMaskRefs = new Map<string, Mask>();
    let queueIndex = 0;
    for (const event of spec.sourceDrawEvents) {
        if (event.kind === 'maskEnter') {
            const maskSpec = maskByNode.get(event.node); const sourceMaskNode = nodes.get(event.node);
            if (!maskSpec || !sourceMaskNode) fail('CREATOR_PROXY_MASK_SOURCE_MISSING', event.node);
            const maskNode = new Node('__sort_mask_' + queueIndex++);
            copyWorldNode(sourceMaskNode, maskNode, containerStack[containerStack.length - 1], sourceLayers.get(event.node)!);
            // A newly-added Mask immediately creates the renderer required by
            // its current type in onLoad. Configure its intended type before
            // activation so a SpriteStencil mask never creates a transient
            // Graphics beside the existing Sprite backing.
            maskNode.active = false;
            const maskParent = containerStack[containerStack.length - 1];
            const maskParentOpacity = proxyOpacity.get(maskParent);
            if (maskParentOpacity === undefined) fail('CREATOR_PROXY_PARENT_OPACITY_MISSING', event.node);
            proxyOpacity.set(maskNode, setOpacityProjection(sourceMaskNode, maskNode, maskParentOpacity, sourceRoot, proxyRoot));
            const nativeType = maskSpec.maskType === 0 ? Mask.Type.GRAPHICS_RECT :
                maskSpec.maskType === 1 ? Mask.Type.GRAPHICS_ELLIPSE : Mask.Type.SPRITE_STENCIL;
            let frame: SpriteFrame | null = null;
            let sourceSprite: Sprite | null = null;
            if (maskSpec.maskType === 2) {
                frame = resolveSprite(maskSpec.spriteFrameUuid || '');
                if (!frame) fail('CREATOR_PROXY_MASK_SPRITE_MISSING', maskSpec.sourceId);
                sourceSprite = sourceMaskNode.getComponent(Sprite);
                if (!sourceSprite || sourceSprite.spriteFrame !== frame)
                    fail('CREATOR_PROXY_MASK_SOURCE_SPRITE_IDENTITY_MISMATCH', maskSpec.sourceId);
            }
            const mask = maskNode.addComponent(Mask);
            mask.type = nativeType;
            if (!mask.subComp && typeof (mask as any).onLoad === 'function') (mask as any).onLoad();
            if (!mask.subComp) fail('CREATOR_PROXY_MASK_NATIVE_BACKING_MISSING', maskSpec.sourceId);
            if (maskSpec.maskType === 2) {
                const sprite = mask.subComp;
                if (!(sprite instanceof Sprite) || !sourceSprite || !frame)
                    fail('CREATOR_PROXY_MASK_NATIVE_SPRITE_BACKING_MISSING', maskSpec.sourceId);
                copyRenderer(sourceSprite, maskNode, 'cc.Sprite', maskSpec.sourceId, sprite);
                if (sprite.spriteFrame !== frame) fail('CREATOR_PROXY_MASK_PROXY_SPRITE_MISMATCH', maskSpec.sourceId);
                mask.spriteFrame = frame;
            } else if (!(mask.subComp instanceof Graphics)) {
                fail('CREATOR_PROXY_MASK_NATIVE_GRAPHICS_BACKING_MISSING', maskSpec.sourceId);
            }
            maskNode.active = true;
            mask.inverted = maskSpec.inverted; mask.alphaThreshold = maskSpec.alphaThreshold;
            mask.enabled = maskSpec.enabled;
            const maskIdentity = maskNode.addComponent(MonkeyStaticMaskIdentity);
            maskIdentity.sourceId = maskSpec.sourceId; maskIdentity.nativeId = maskSpec.nativeId;
            maskIdentity.sourceMaskType = maskSpec.maskType; maskIdentity.sourceInverted = maskSpec.inverted;
            maskIdentity.sourceAlphaThreshold = maskSpec.alphaThreshold; maskIdentity.sourceFieldsJson = maskSpec.sourceFieldsJson;
            maskIdentity.sourceSpriteFrameUuid = maskSpec.spriteFrameUuid || '';
            maskIdentity.sourceSpriteFrame = maskSpec.maskType === 2 ? mask.spriteFrame : null;
            maskIdentity.nativeMask = mask; maskIdentity.enabled = false;
            const sourceNativeMask = sourceMaskNode.getComponent(Mask);
            if (!sourceNativeMask) fail('CREATOR_PROXY_SOURCE_MASK_COMPONENT_MISSING', maskSpec.sourceId);
            sourceMaskRefs.set(maskSpec.node, sourceNativeMask); proxyMaskRefs.set(maskSpec.node, mask);
            addIdentity(maskNode, { kind: 'mask', sourceNode: event.node, sourceComponentId: maskSpec.sourceId,
                sourceType: 'cc.Mask', maskType: maskSpec.maskType, inverted: maskSpec.inverted, queueIndex });
            containerStack[containerStack.length - 1].addChild(maskNode);
            containerStack.push(maskNode); maskStack.push(event.node); proxyNodes.push(maskNode);
        } else if (event.kind === 'maskExit') {
            if (containerStack.length <= 1 || maskStack.pop() !== event.node) fail('CREATOR_PROXY_MASK_STACK_MISMATCH', event.node);
            containerStack.pop();
        } else if (event.kind === 'renderer') {
            const row = rendererById.get(event.sourceComponentId || ''); const sourceNode = nodes.get(event.node);
            if (!row || !sourceNode) fail('CREATOR_PROXY_RENDERER_SOURCE_MISSING', event.sourceComponentId || '');
            if (row.sourceType === 'cc.Graphics' && (!row.initialCommandStreamEmpty || !row.sourceFieldsSha256 ||
                !row.sourceFields || row.sourceFields.__type__ !== 'cc.Graphics' ||
                Object.keys(row.sourceFields).some(key => !['__type__','_materials','node'].includes(key))))
                fail('CREATOR_PROXY_GRAPHICS_SOURCE_COMMAND_PROOF_MISSING', row.sourceComponentId);
            const source = sourceRenderer(sourceNode, row.sourceType, sourceNodeActiveInContract(spec, event.node, sourceParents));
            const proxyNode = new Node('__sort_renderer_' + queueIndex++);
            const rendererParent = containerStack[containerStack.length - 1];
            copyWorldNode(sourceNode, proxyNode, rendererParent, sourceLayers.get(event.node)!);
            const rendererParentOpacity = proxyOpacity.get(rendererParent);
            if (rendererParentOpacity === undefined) fail('CREATOR_PROXY_PARENT_OPACITY_MISSING', event.node);
            const rendererOpacity = setOpacityProjection(sourceNode, proxyNode, rendererParentOpacity, sourceRoot, proxyRoot);
            proxyOpacity.set(proxyNode, rendererOpacity);
            const proxyRenderer = copyRenderer(source, proxyNode, row.sourceType, row.sourceComponentId);
            if (!Number.isInteger(row.nativeSortingOrder) || row.nativeSortingOrder < -32768 || row.nativeSortingOrder > 32767)
                fail('CREATOR_PROXY_SORT_RANK_OUT_OF_RANGE', event.sourceComponentId || '');
            addRendererSortRank(proxyRenderer, row.sourceType, row.nativeSortingOrder);
            sourceRendererRefs.set(row.sourceComponentId, source); proxyRendererRefs.set(row.sourceComponentId, proxyRenderer);
            addIdentity(proxyNode, { kind: 'renderer', sourceNode: event.node, sourceComponentId: row.sourceComponentId,
                sourceType: row.sourceType, queueIndex, sortOrder: row.nativeSortingOrder });
            containerStack[containerStack.length - 1].addChild(proxyNode);
            proxyNodes.push(proxyNode);
        } else fail('CREATOR_PROXY_DRAW_EVENT_UNKNOWN', event.kind);
    }
    if (containerStack.length !== 1 || maskStack.length) fail('CREATOR_PROXY_MASK_SCOPE_UNCLOSED');
    const presenter = proxyRoot.addComponent(CreatorStaticSortQueueProxyPresenter);
    presenter.sourceRootId = spec.rootScope; presenter.sourcePrefabId = spec.sourcePrefabId;
    presenter.prefabPath = spec.prefabPath; presenter.sourceRoot = sourceRoot; presenter.proxyRoot = proxyRoot;
    presenter.hiddenLayer = spec.sourceLayerHiddenValue;
    presenter.captureOriginalLayers(spec.sourceNodeIds.map(id => nodes.get(id)!));
    presenter.proxyNodes = proxyNodes;
    presenter.nestedProxyRoots = nestedProxyRoots;
    presenter.nestedProxyRootActiveBefore = nestedProxyRootActiveBefore;
    presenter.sourceRenderers = spec.renderers.map(row => sourceRendererRefs.get(row.sourceComponentId)!);
    presenter.proxyRenderers = spec.renderers.map(row => proxyRendererRefs.get(row.sourceComponentId)!);
    presenter.proxySortOrders = spec.renderers.map(row => row.nativeSortingOrder);
    presenter.sourceMasks = spec.masks.map(row => sourceMaskRefs.get(row.node)!);
    presenter.proxyMasks = spec.masks.map(row => proxyMaskRefs.get(row.node)!);
    presenter.queueSha256 = spec.sourceManifestSha256 + ':' + JSON.stringify(spec.sourceDrawEvents);
    presenter.initializeEditorInstance();
    const readback = readStaticSortQueueProxy(spec, nodes, proxyRoot, presenter, resolveSprite, true);
    if (!readback.verified) fail('CREATOR_PROXY_CREATE_READBACK_FAILED:' + JSON.stringify({
        falseChecks: readback.failedChecks, badSourceIds: readback.failedSourceIds,
        badMaskRows: readback.masks.filter(row => !row.verified).slice(0, 4).map(row => boundedMaskFailureSummary(row))}));
    completed = true;
    return readback;
    } finally {
        if (!completed) {
            if (proxyRoot && proxyRoot.isValid) {
                try { proxyRoot.removeFromParent(); proxyRoot.destroy(); } catch (_) { /* Restore author state below even if cleanup fails. */ }
            }
            for (let index = nestedProxyRoots.length - 1; index >= 0; index--) {
                const root = nestedProxyRoots[index];
                if (root && root.isValid && root.active !== nestedProxyRootActiveBefore[index]) root.active = nestedProxyRootActiveBefore[index];
            }
            for (const [id, layer] of runtimeLayersBefore) {
                const node = nodes.get(id); if (node && node.isValid) node.layer = layer;
            }
        }
    }
}

export function readStaticSortQueueProxy(spec: CreatorProxySpec, nodes: Map<string, Node>, proxyRoot: Node,
    presenter: CreatorStaticSortQueueProxyPresenter, resolveSprite: (uuid: string) => any,
    runtimeSuppressionExpected = false): CreatorProxyReadback {
    const sourceNonDrawRenderers = assertSourceRendererCoverage(spec, nodes);
    const observed: Array<[string,string,string|null]> = [];
    const graphics: CreatorProxyGraphicReadback[] = []; const masks: CreatorProxyMaskReadback[] = [];
    const sourceNodeIdByNode = new Map<Node, string>(); for (const [sourceId, node] of nodes) sourceNodeIdByNode.set(node, sourceId);
    const sourceLayerById = new Map<string, number>();
    presenter.sourceNodes.forEach((node, index) => sourceLayerById.set(spec.sourceNodeIds[index], presenter.originalLayers[index]));
    function visit(node: Node): void {
        const marker = node.getComponent(CreatorStaticSortQueueProxyMarker);
        if (marker?.kind === 'mask') {
            observed.push(['maskEnter', marker.sourceNode, null]);
            const mask = node.getComponent(Mask); const source = nodes.get(marker.sourceNode);
            const sourceUI = source?.getComponent(UITransform), proxyUI = node.getComponent(UITransform);
            const worldMatrixVerified = !!source && matricesMatch(source, node);
            const uiSizeVerified = !!sourceUI && !!proxyUI && equalValue(sourceUI.contentSize, proxyUI.contentSize);
            const uiAnchorVerified = !!sourceUI && !!proxyUI && equalValue(sourceUI.anchorPoint, proxyUI.anchorPoint);
            const transformVerified = worldMatrixVerified && uiSizeVerified && uiAnchorVerified;
            const opacityVerified = !!source &&
                Math.abs(authoredOpacityWithin(source, nodes.get(spec.rootScope)!) - authoredOpacityWithin(node, proxyRoot)) <= 1 / 255 + 1e-6;
            const sprite = node.getComponent(Sprite);
            const expected = spec.masks.find(row => row.node === marker.sourceNode);
            const maskIndex = spec.masks.findIndex(row => row.node === marker.sourceNode);
            const sourceMaskRef = source?.getComponent(Mask);
            const expectedNativeType = expected?.maskType === 0 ? Mask.Type.GRAPHICS_RECT :
                expected?.maskType === 1 ? Mask.Type.GRAPHICS_ELLIPSE : Mask.Type.SPRITE_STENCIL;
            const expectedSprite = expected?.maskType === 2 && expected.spriteFrameUuid ? resolveSprite(expected.spriteFrameUuid) : null;
            const sourceSprite = source?.getComponent(Sprite) || null;
            const identity = node.getComponent(MonkeyStaticMaskIdentity);
            const sourceOpacityFactor = source ? authoredOpacityWithin(source, nodes.get(spec.rootScope)!) : null;
            const nativeOpacityFactor = authoredOpacityWithin(node, proxyRoot);
            const expectedLayer = sourceLayerById.get(marker.sourceNode) ?? -1;
            const sourceSpriteFingerprint = sourceSprite ? rendererFingerprint(sourceSprite, 'cc.Sprite') : null;
            const nativeSpriteFingerprint = sprite ? rendererFingerprint(sprite, 'cc.Sprite') : null;
            const spriteFrameMatches = expected?.maskType !== 2 || (!!sprite && !!expectedSprite && sprite.spriteFrame === expectedSprite);
            const spriteRendererMatches = expected?.maskType !== 2 || (!!sourceSprite && !!sprite && sourceSpriteFingerprint === nativeSpriteFingerprint);
            const expectedBackingRenderer = expected?.maskType === 2 ? sprite : node.getComponent(Graphics);
            const backingTypeMatches = !!mask && !!expectedBackingRenderer &&
                maskBackingMatches(node, mask, expectedBackingRenderer, runtimeSuppressionExpected) &&
                (expected?.maskType === 2 ? node.getComponents(Sprite).length === 1 && node.getComponents(Graphics).length === 0 :
                    node.getComponents(Graphics).length === 1 && node.getComponents(Sprite).length === 0);
            const checks: Record<string, boolean> = {
                maskPresent: !!mask,
                expectedSourceMaskPresent: !!sourceMaskRef,
                sourceAndProxyMaskRefs: maskIndex >= 0 && presenter.sourceMasks[maskIndex] === sourceMaskRef && presenter.proxyMasks[maskIndex] === mask,
                markerSourceComponentId: !!expected && marker.sourceComponentId === expected.sourceId,
                markerMaskType: !!expected && marker.maskType === expected.maskType,
                maskType: !!expected && mask?.type === expectedNativeType,
                enabled: !!expected && mask?.enabled === expected.enabled,
                inverted: !!expected && mask?.inverted === expected.inverted,
                alphaThreshold: !!expected && Math.abs((mask?.alphaThreshold ?? NaN) - expected.alphaThreshold) < 1e-6,
                backingType: backingTypeMatches,
                spriteFrame: spriteFrameMatches,
                sourceAndNativeSpriteFields: spriteRendererMatches,
                identityPresent: !!identity,
                identityDisabled: !!identity && !identity.enabled,
                identitySourceId: !!expected && identity?.sourceId === expected.sourceId,
                identityNativeId: !!expected && identity?.nativeId === expected.nativeId,
                identitySourceMaskType: !!expected && identity?.sourceMaskType === expected.maskType,
                identityInverted: !!expected && identity?.sourceInverted === expected.inverted,
                identityAlphaThreshold: !!expected && identity?.sourceAlphaThreshold === expected.alphaThreshold,
                identityFieldsJson: !!expected && identity?.sourceFieldsJson === expected.sourceFieldsJson,
                identitySpriteFrameUuid: !!expected && identity?.sourceSpriteFrameUuid === (expected.spriteFrameUuid || ''),
                identityNativeMaskReference: !!identity && identity.nativeMask === mask,
                identitySpriteFrameReference: !!expected && (expected.maskType === 2 ? identity?.sourceSpriteFrame === expectedSprite : identity?.sourceSpriteFrame === null),
                transform: transformVerified,
                worldMatrix: worldMatrixVerified,
                uiContentSize: uiSizeVerified,
                uiAnchor: uiAnchorVerified,
                opacity: opacityVerified,
                layer: node.layer === expectedLayer,
            };
            const verified = Object.values(checks).every(Boolean);
            const sourcePosition = source?.position, sourceRotation = source?.rotation, sourceScale = source?.scale;
            const nativePosition = node.position, nativeRotation = node.rotation, nativeScale = node.scale;
            masks.push({ sourceId: marker.sourceComponentId, sourceNode: marker.sourceNode,
                sourceMaskType: expected?.maskType ?? -1, nativeMaskType: mask?.type ?? -1,
                inverted: mask?.inverted ?? false, enabled: mask?.enabled ?? false,
                alphaThreshold: mask?.alphaThreshold ?? -1, spriteFrameUuid: sprite ? refId(sprite.spriteFrame) : null,
                transformVerified, opacityVerified, verified, checks,
                sourceMaskEnabled: sourceMaskRef?.enabled ?? null, sourceMaskInverted: sourceMaskRef?.inverted ?? null,
                sourceAlphaThreshold: sourceMaskRef?.alphaThreshold ?? null,
                expectedMaskEnabled: expected?.enabled ?? null, expectedMaskType: expected?.maskType ?? null,
                expectedInverted: expected?.inverted ?? null, expectedAlphaThreshold: expected?.alphaThreshold ?? null,
                expectedSpriteFrameUuid: expected?.spriteFrameUuid || null,
                sourceSpriteType: sourceSprite?.constructor.name ?? null, sourceSpriteEnabled: sourceSprite?.enabled ?? null,
                sourceSpriteFrameUuid: sourceSprite ? refId(sourceSprite.spriteFrame) : null,
                nativeSpriteType: sprite?.constructor.name ?? null, nativeSpriteEnabled: sprite?.enabled ?? null,
                nativeSpriteFrameExpectedUuid: expectedSprite ? refId(expectedSprite) : null,
                sourceSpriteFingerprint, nativeSpriteFingerprint,
                identitySourceId: identity?.sourceId ?? null, identityNativeId: identity?.nativeId ?? null,
                identityNativeMaskRefMatches: !!identity && identity.nativeMask === mask,
                sourceLocalTransform: sourcePosition && sourceRotation && sourceScale ? [sourcePosition.x, sourcePosition.y, sourcePosition.z,
                    sourceRotation.x, sourceRotation.y, sourceRotation.z, sourceRotation.w, sourceScale.x, sourceScale.y, sourceScale.z] : null,
                nativeLocalTransform: [nativePosition.x, nativePosition.y, nativePosition.z, nativeRotation.x, nativeRotation.y,
                    nativeRotation.z, nativeRotation.w, nativeScale.x, nativeScale.y, nativeScale.z],
                sourceWorldMatrix: source ? matrixValues(source) : null, nativeWorldMatrix: matrixValues(node),
                sourceSizeAnchor: sourceUI ? [sourceUI.contentSize.width, sourceUI.contentSize.height,
                    sourceUI.anchorPoint.x, sourceUI.anchorPoint.y] : null,
                nativeSizeAnchor: proxyUI ? [proxyUI.contentSize.width, proxyUI.contentSize.height,
                    proxyUI.anchorPoint.x, proxyUI.anchorPoint.y] : null,
                sourceOpacityFactor, nativeOpacityFactor, sourceLayer: source ? source.layer : null, nativeLayer: node.layer });
            for (const child of node.children) visit(child);
            observed.push(['maskExit', marker.sourceNode, null]); return;
        }
        if (marker?.kind === 'renderer') {
            observed.push(['renderer', marker.sourceNode, marker.sourceComponentId]);
            const sourceNode = nodes.get(marker.sourceNode); const source = sourceNode ? sourceRenderer(sourceNode, marker.sourceType, runtimeSuppressionExpected) : null;
            const proxy = marker.sourceType === 'cc.RichText' ? node.getComponent(RichText) :
                node.getComponents(UIRenderer).find(item => !(item instanceof Mask));
            const rendererIndex = spec.renderers.findIndex(row => row.sourceComponentId === marker.sourceComponentId);
            const rendererSpec = rendererIndex >= 0 ? spec.renderers[rendererIndex] : null;
            const richSource = source instanceof RichText ? source : null;
            const originalLayer = sourceLayerById.get(marker.sourceNode) ?? -1;
            const sortingSegmentsVerified = !!proxy && rendererSortRankVerified(proxy, marker.sourceType, marker.sortOrder);
            const sourceSegmentsHidden = richSource && runtimeSuppressionExpected ?
                richTextSegments(richSource).every(segment => segment.layer === spec.sourceLayerHiddenValue) : null;
            const proxySegmentsCorrectLayer = proxy instanceof RichText && runtimeSuppressionExpected ?
                richTextSegments(proxy).every(segment => segment.layer === originalLayer) : null;
            const richTextLayersVerified = marker.sourceType !== 'cc.RichText' || !runtimeSuppressionExpected ||
                (sourceSegmentsHidden === true && proxySegmentsCorrectLayer === true);
            const sourceAuthoredOpacityWithinRoot = source ? authoredOpacityWithin(source.node, nodes.get(spec.rootScope)!) : null;
            const proxyAuthoredOpacityWithinProxy = authoredOpacityWithin(node, proxyRoot);
            const sourceOpacityPath = source ? opacityPathReadback(source.node, nodes.get(spec.rootScope)!, sourceNodeIdByNode) : [];
            const proxyOpacityPath = opacityPathReadback(node, proxyRoot, sourceNodeIdByNode);
            // The root node is the shared outer opacity boundary. Compare the
            // serialized local UIOpacity product below it, never _uiProps.opacity:
            // Creator updates that final-opacity cache during batcher walks.
            const opacityVerified = sourceAuthoredOpacityWithinRoot !== null &&
                Math.abs(sourceAuthoredOpacityWithinRoot - proxyAuthoredOpacityWithinProxy) <= 1 / 255 + 1e-6;
            const verified = !!source && !!proxy && rendererIndex >= 0 && presenter.sourceRenderers[rendererIndex] === source &&
                presenter.proxyRenderers[rendererIndex] === proxy && sortingSegmentsVerified &&
                rendererFingerprint(source, marker.sourceType, runtimeSuppressionExpected) === rendererFingerprint(proxy, marker.sourceType, runtimeSuppressionExpected) &&
                node.layer === originalLayer && matricesMatch(sourceNode!, node) && opacityVerified && richTextLayersVerified;
            graphics.push({ sourceComponentId: marker.sourceComponentId, sourceNode: marker.sourceNode,
                nativeType: proxy?.constructor?.name || '',
                sourceFingerprint: source ? rendererFingerprint(source, marker.sourceType, runtimeSuppressionExpected) : '',
                proxyFingerprint: proxy ? rendererFingerprint(proxy, marker.sourceType, runtimeSuppressionExpected) : '', originalLayer,
                proxyLayer: node.layer, opacityVerified,
                sourceAuthoredOpacityWithinRoot, proxyAuthoredOpacityWithinProxy,
                sourceOpacityPath, proxyOpacityPath,
                segmentCount: richSource ? richTextSegments(richSource).length : null,
                sortingSegmentsVerified, sourceSegmentsHidden, proxySegmentsCorrectLayer, verified,
                sourceFieldsJson: rendererSpec?.sourceFieldsJson || null, sourceFieldsSha256: rendererSpec?.sourceFieldsSha256 || null,
                sourceText: rendererSpec?.sourceText ?? null, renderedString: richSource?.string ?? null,
                sourceFontId: rendererSpec?.sourceFontId ?? null, nativeFontAssetId: rendererSpec?.nativeFontAssetId || null,
                nativeFallbackAssetIds: rendererSpec?.nativeFallbackAssetIds || null,
                targetSystemFontFamily: rendererSpec?.targetSystemFontFamily ?? null,
                creatorMarkup: rendererSpec?.creatorMarkup ?? null, fontAssetUuid: richSource ? refId(richSource.font) : null,
                fontFamily: richSource?.fontFamily ?? null, imageAtlasUuid: richSource ? refId(richSource.imageAtlas) : null });
        }
        for (const child of node.children) visit(child);
    }
    for (const child of proxyRoot.children) visit(child);
    const expected = spec.sourceDrawEvents.map(row => [row.kind, row.node, row.sourceComponentId || null] as [string,string,string|null]);
    const sourceSortOrderFields = spec.sourceSortOrderFields.map(field => {
        const node = nodes.get(field.node), matches = node?.getComponents(MonkeyStaticSortOrderField).filter(item => item.sourceId === field.sourceId) || [];
        const item = matches.length === 1 ? matches[0] : null;
        const verified = !!item && item.nativeId === field.nativeId && item.sourceSortOrder === field.sortOrder &&
            item.effectiveSourceSortOrder === (field.enabled ? field.sortOrder : 0) && item.enabledInSource === field.enabled &&
            item.renderedOnNode === false && typeof item.uuid === 'string' && item.uuid.length > 0;
        return {sourceId: item?.sourceId || null, expectedSourceId: field.sourceId, nativeId: item?.nativeId || null,
            expectedNativeId: field.nativeId, node: field.node, sourceSortOrder: item?.sourceSortOrder ?? null,
            effectiveSourceSortOrder: item?.effectiveSourceSortOrder ?? null, enabledInSource: item?.enabledInSource ?? null,
            renderedOnNode: item?.renderedOnNode ?? null, componentUuid: item?.uuid || null,
            nativeClass: item?.constructor?.name || null, verified};
    });
    const sourceSortRoots = spec.sourceSortRoots.map(field => {
        const node = nodes.get(field.node), matches = node?.getComponents(CreatorStaticSortRootField).filter(item => item.sourceId === field.sourceId) || [];
        const item = matches.length === 1 ? matches[0] : null;
        const verified = !!item && item.nativeId === field.nativeId && item.enabledInSource === field.enabled &&
            typeof item.uuid === 'string' && item.uuid.length > 0;
        return {sourceId: item?.sourceId || null, expectedSourceId: field.sourceId, nativeId: item?.nativeId || null,
            expectedNativeId: field.nativeId, node: field.node, enabledInSource: item?.enabledInSource ?? null,
            componentUuid: item?.uuid || null, nativeClass: item?.constructor?.name || null, verified};
    });
    const sourceFieldsPreserved = sourceSortOrderFields.length === spec.sourceSortOrderFields.length && sourceSortOrderFields.every(row => row.verified);
    const sortRootsPreserved = sourceSortRoots.length === spec.sourceSortRoots.length && sourceSortRoots.every(row => row.verified);
    const suppressed = spec.sourceNodeIds.every(id => nodes.get(id)?.layer === spec.sourceLayerHiddenValue) &&
        presenter.hiddenLayer === spec.sourceLayerHiddenValue && presenter.sourceRoot === nodes.get(spec.rootScope) &&
        presenter.sourceRootId === spec.rootScope && presenter.sourcePrefabId === spec.sourcePrefabId && presenter.prefabPath === spec.prefabPath &&
        presenter.proxyRoot === proxyRoot && presenter.sourceTreeStayedUnmodified &&
        presenter.queueSha256 === spec.sourceManifestSha256 + ':' + JSON.stringify(spec.sourceDrawEvents);
    const richTextSourceIds = new Set(spec.renderers.filter(row => row.sourceType === 'cc.RichText').map(row => row.sourceComponentId));
    const richTextSegmentSuppressionVerified = graphics.filter(row => richTextSourceIds.has(row.sourceComponentId))
        .every(row => row.sourceSegmentsHidden === true && row.proxySegmentsCorrectLayer === true);
    const sourceRootNode = nodes.get(spec.rootScope);
    const scene = sourceRootNode?.scene;
    const proxyScene = proxyRoot.scene;
    const canvas = ancestorCanvas(sourceRootNode || null);
    const canvasCamera = canvas?.cameraComponent || null;
    const cameras = scene?.getComponentsInChildren(Camera).filter(camera => camera.enabledInHierarchy && camera.node.activeInHierarchy) || [];
    const activeCanvas = !!canvas && canvas.node.scene === scene && canvas.enabledInHierarchy && canvas.node.activeInHierarchy &&
        nodeIsWithin(sourceRootNode || null, canvas.node);
    const cameraSafe = cameras.length > 0 && cameras.every(camera => (camera.visibility & spec.sourceLayerHiddenValue) === 0);
    const canvasCameraInScene = !!canvasCamera && canvasCamera.node.scene === scene && canvasCamera.enabledInHierarchy &&
        canvasCamera.node.activeInHierarchy && cameras.includes(canvasCamera);
    const initializedContext = !!scene && scene === proxyScene && activeCanvas && canvasCameraInScene && cameraSafe &&
        !!sourceRootNode?.activeInHierarchy && !!proxyRoot.activeInHierarchy;
    const sourceLayersPreserved = presenter.sourceNodes.length === presenter.originalLayers.length &&
        presenter.sourceNodes.every((node, index) => node && node.layer === presenter.originalLayers[index]);
    const sourceLayersMatchContract = presenter.sourceNodes.length === spec.sourceNodeIds.length &&
        presenter.originalLayers.length === spec.sourceNodeIds.length && presenter.sourceNodes.every((node, index) =>
            node === nodes.get(spec.sourceNodeIds[index]) && presenter.originalLayers[index] === spec.sourceNodeLayers[spec.sourceNodeIds[index]]);
    const sourceRoot = nodes.get(spec.rootScope)!, rootLayout = sourceRoot.getComponent(Layout);
    const layoutChildren = rootLayout ? sourceRoot.children.filter(child => child.activeInHierarchy && !!child.getComponent(UITransform)) : [];
    const structuralRootLayoutSafe = !proxyRoot.getComponent(UITransform) && !layoutChildren.includes(proxyRoot);
    const sourceVisibilityOK = runtimeSuppressionExpected ? suppressed && initializedContext && richTextSegmentSuppressionVerified : sourceLayersPreserved;
    const tree = treeMatches(spec, nodes);
    const referenceArraysValid = presenter.sourceRenderers.length === spec.renderers.length &&
        presenter.proxyRenderers.length === spec.renderers.length && presenter.sourceMasks.length === spec.masks.length &&
        presenter.proxyMasks.length === spec.masks.length && presenter.proxySortOrders.length === spec.renderers.length &&
        presenter.proxySortOrders.every((value, index) => value === spec.renderers[index].nativeSortingOrder);
    const nestedProxyRootReadbacks = presenter.nestedProxyRoots.map((nestedRoot, index) => {
        const marker = nestedRoot && nestedRoot.getComponent(CreatorStaticSortQueueProxyMarker);
        const nestedPresenter = nestedRoot && nestedRoot.getComponent(CreatorStaticSortQueueProxyPresenter);
        const markerOwnerMatches = !!marker && !!nestedRoot.parent && marker.sourceRootOwner === nestedRoot.parent;
        const presenterSourceRootMatches = !!nestedPresenter && nestedPresenter.sourceRoot === nestedRoot.parent;
        const presenterProxyRootMatches = !!nestedPresenter && nestedPresenter.proxyRoot === nestedRoot;
        const verified = !!nestedRoot && isGeneratedSortProxyRoot(nestedRoot) && !nestedRoot.active &&
            index < presenter.nestedProxyRootActiveBefore.length && typeof presenter.nestedProxyRootActiveBefore[index] === 'boolean' &&
            marker?.kind === 'root' && markerOwnerMatches &&
            !!nestedPresenter && presenterSourceRootMatches && presenterProxyRootMatches &&
            nestedPresenter.sourceRootId === marker.sourceNode;
        return {sourceNode: marker?.sourceNode || '', rootUuid: nestedRoot?.uuid || '', active: !!nestedRoot?.active,
            expectedActiveBefore: presenter.nestedProxyRootActiveBefore[index] ?? null,
            markerSourceNode: marker?.sourceNode || null, markerOwnerMatches, presenterPresent: !!nestedPresenter,
            presenterSourceRootMatches, presenterProxyRootMatches, presenterSourceRootId: nestedPresenter?.sourceRootId || null,
            verified};
    });
    const nestedProxyRootActiveArrayMatches = presenter.nestedProxyRoots.length === presenter.nestedProxyRootActiveBefore.length;
    const nestedProxyRootsDisabled = nestedProxyRootActiveArrayMatches &&
        nestedProxyRootReadbacks.length === presenter.nestedProxyRoots.length && nestedProxyRootReadbacks.every(row => row.verified);
    const activePreserved = Object.entries(spec.sourceNodeActive).every(([id, active]) => nodes.get(id)?.active === active);
    const rootIdentity = proxyRoot.getComponent(CreatorStaticSortQueueProxyMarker);
    const drawSequenceVerified = equalValue(observed, expected);
    const sourceNonDrawSourceMappings = spec.sourceNonDrawRenderers.map(row => ({...row,
        verified: sourceNonDrawRenderers.some(carrier => carrier.sourceId === row.sourceComponentId && carrier.node === row.node && carrier.verified)}));
    const sourceQueueProjectionVerified = sourceNonDrawSourceMappings.length === spec.nonDrawRenderers.length &&
        sourceNonDrawSourceMappings.every(row => row.verified);
    const checks: Record<string, boolean> = {
        sourceTreePreserved: tree,
        sourceNodeActivePreserved: activePreserved,
        sourceSortOrderFieldsPreserved: sourceFieldsPreserved,
        sourceSortRootsPreserved: sortRootsPreserved,
        sourceLayerContractMatches: sourceLayersMatchContract,
        nestedProxyRootActiveArrayMatches,
        nestedProxyRootsDisabled,
        sourceVisibilityVerified: sourceVisibilityOK,
        initializedContextVerified: !runtimeSuppressionExpected || initializedContext,
        cameraSafe: !runtimeSuppressionExpected || cameraSafe,
        drawSequenceVerified,
        sourceQueueProjectionVerified,
        structuralRootLayoutSafe,
        sourceNonDrawCountMatches: sourceNonDrawRenderers.length === spec.nonDrawRenderers.length,
        sourceNonDrawFieldsVerified: sourceNonDrawRenderers.every(row => row.verified),
        rendererCountMatches: graphics.length === spec.renderers.length,
        rendererFieldsVerified: graphics.every(row => row.verified),
        maskCountMatches: masks.length === spec.masks.length,
        maskFieldsVerified: masks.every(row => row.verified),
    };
    if (!runtimeSuppressionExpected) checks.sourceLayersPreserved = sourceLayersPreserved;
    const failedChecks = Object.keys(checks).filter(key => !checks[key]);
    const failedSourceIds: string[] = [];
    const addBadId = (id: string | null | undefined) => { if (id && !failedSourceIds.includes(id) && failedSourceIds.length < 64) failedSourceIds.push(id); };
    for (let index = 0; index < spec.sourceNodeIds.length; index++) {
        const id = spec.sourceNodeIds[index];
        if (presenter.sourceNodes[index] !== nodes.get(id) || presenter.originalLayers[index] !== spec.sourceNodeLayers[id]) addBadId(id);
    }
    for (const row of sourceNonDrawRenderers) if (!row.verified) addBadId(row.sourceId);
    for (const row of sourceSortOrderFields) if (!row.verified) addBadId(row.expectedSourceId);
    for (const row of sourceSortRoots) if (!row.verified) addBadId(row.expectedSourceId);
    for (const row of graphics) if (!row.verified) addBadId(row.sourceComponentId);
    for (const row of masks) if (!row.verified) addBadId(row.sourceId);
    for (const row of nestedProxyRootReadbacks) if (!row.verified) addBadId(row.sourceNode);
    const passed = tree && activePreserved && rootIdentity?.kind === 'root' && rootIdentity.sourceNode === spec.rootScope &&
        rootIdentity.sourceRootOwner === nodes.get(spec.rootScope) && sourceFieldsPreserved && sortRootsPreserved &&
        sourceLayersMatchContract && referenceArraysValid && nestedProxyRootsDisabled && sourceVisibilityOK && drawSequenceVerified && sourceQueueProjectionVerified && structuralRootLayoutSafe &&
        sourceNonDrawRenderers.length === spec.nonDrawRenderers.length && sourceNonDrawRenderers.every(row => row.verified) &&
        graphics.length === spec.renderers.length && graphics.every(row => row.verified) && masks.length === spec.masks.length && masks.every(row => row.verified);
    return { rootScope: spec.rootScope, sourceTreePreserved: tree, sourceFieldsPreserved, sourceSortRootsPreserved: sortRootsPreserved,
        sourceLayersPreserved, sourceSuppressed: runtimeSuppressionExpected && suppressed && initializedContext && richTextSegmentSuppressionVerified,
        sourceLayersMatchContract, failedChecks, failedSourceIds,
        initializedContextVerified: runtimeSuppressionExpected && initializedContext, cameraSafe: runtimeSuppressionExpected && cameraSafe,
        nestedProxyRootsDisabled, nestedProxyRootReadbacks,
        nestedProxyRootActiveArrayMatches,
        presentationMode: runtimeSuppressionExpected ? 'initialized' : 'persistent',
        sourceRendererCoverageVerified: true, sourceNonDrawRenderers, structuralRootLayoutSafe,
        drawSequenceVerified, sourceQueueProjectionVerified,
        sourceOriginalDrawEvents: spec.sourceOriginalDrawEvents.map(event => ({...event})), sourceNonDrawSourceMappings,
        sourceSortOrderFields, sourceSortRoots, graphics, masks, verified: passed,
        diagnostic: passed ? null : 'CREATOR_PROXY_NATIVE_RENDERER_MASK_LAYER_OR_TREE_READBACK_FAILED' };
}

/** Verifies the serialized Prefab contract while authored source layers are restored. */
export function readPersistentStaticSortQueueProxy(spec: CreatorProxySpec, nodes: Map<string, Node>, proxyRoot: Node,
    presenter: CreatorStaticSortQueueProxyPresenter, resolveSprite: (uuid: string) => any): CreatorProxyReadback {
    return readStaticSortQueueProxy(spec, nodes, proxyRoot, presenter, resolveSprite, false);
}

/** Verifies the active Editor/scene instance after presenter source suppression has run. */
export function readInitializedStaticSortQueueProxy(spec: CreatorProxySpec, nodes: Map<string, Node>, proxyRoot: Node,
    presenter: CreatorStaticSortQueueProxyPresenter, resolveSprite: (uuid: string) => any): CreatorProxyReadback {
    presenter.initializeEditorInstance();
    return readStaticSortQueueProxy(spec, nodes, proxyRoot, presenter, resolveSprite, true);
}

/** Registered bridge surface for Creator Editor extensions; instantiate no API component. */
@ccclass('MonkeyStaticSortQueueProxyApi')
export class CreatorStaticSortQueueProxyApi extends Component {
    static readonly moduleUuid = CREATOR_STATIC_SORT_QUEUE_PROXY_API_UUID;
    static attachSourceIdentities(specs: CreatorProxySpec[], nodes: Map<string, Node>): CreatorSourceSortIdentityReadback {
        return attachStaticSortSourceIdentities(specs, nodes);
    }
    static create(spec: CreatorProxySpec, nodes: Map<string, Node>, resolveSprite: (uuid: string) => any): CreatorProxyReadback {
        return createStaticSortQueueProxy(spec, nodes, resolveSprite);
    }
    static readPersistent(spec: CreatorProxySpec, nodes: Map<string, Node>, proxyRoot: Node,
        presenter: CreatorStaticSortQueueProxyPresenter, resolveSprite: (uuid: string) => any): CreatorProxyReadback {
        return readPersistentStaticSortQueueProxy(spec, nodes, proxyRoot, presenter, resolveSprite);
    }
    static readInitialized(spec: CreatorProxySpec, nodes: Map<string, Node>, proxyRoot: Node,
        presenter: CreatorStaticSortQueueProxyPresenter, resolveSprite: (uuid: string) => any): CreatorProxyReadback {
        return readInitializedStaticSortQueueProxy(spec, nodes, proxyRoot, presenter, resolveSprite);
    }
    static isGeneratedProxyRoot(node: Node): boolean { return isGeneratedSortProxyRoot(node); }
    static prepareForSerialization(presenter: CreatorStaticSortQueueProxyPresenter): void { presenter.prepareForSerialization(); }
    static restoreAfterSerialization(presenter: CreatorStaticSortQueueProxyPresenter): void { presenter.restoreAfterSerialization(); }
}
