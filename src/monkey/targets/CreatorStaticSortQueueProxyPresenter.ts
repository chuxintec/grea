import { _decorator, CCBoolean, CCInteger, Component, Label, Mask, Node, RichText, Sorting2D, Sprite, UITransform, UIRenderer } from 'cc';
const { ccclass, property, executeInEditMode } = _decorator;

@ccclass('MonkeyStaticSortQueueProxyPresenter')
@executeInEditMode
export class CreatorStaticSortQueueProxyPresenter extends Component {
    private serializationPrepared = false;
    @property public sourceRootId = '';
    @property public sourcePrefabId = '';
    @property public prefabPath = '';
    @property(Node) public sourceRoot: Node | null = null;
    @property(Node) public proxyRoot: Node | null = null;
    @property([Node]) public sourceNodes: Node[] = [];
    @property([Node]) public proxyNodes: Node[] = [];
    // Renderer identity can be a UIRenderer or a native cc.RichText component
    // whose generated child Labels/Sprites carry the Sorting2D priorities.
    @property([Component]) public sourceRenderers: Component[] = [];
    @property([Component]) public proxyRenderers: Component[] = [];
    @property({ type: [CCInteger] }) public proxySortOrders: number[] = [];
    @property([Mask]) public sourceMasks: Mask[] = [];
    @property([Mask]) public proxyMasks: Mask[] = [];
    @property([Node]) public nestedProxyRoots: Node[] = [];
    @property({ type: [CCBoolean] }) public nestedProxyRootActiveBefore: boolean[] = [];
    @property public originalLayers: number[] = [];
    @property public hiddenLayer = 1 << 28;
    @property public queueSha256 = '';
    @property public sourceTreeStayedUnmodified = true;

    onLoad(): void { this.suppressSourceLayers(); }
    onEnable(): void {
        this.suppressSourceLayers();
        // RichText's native segment Nodes have DontSave hide flags. Their
        // Sorting2D components are recreated from this persistent parent
        // binding after the RichText lifecycle generates those segments.
        this.scheduleOnce(this.initializeProxyRichTextSorting, 0);
    }
    onDisable(): void {
        this.clearGeneratedRichTextSorting();
        this.restoreSourceLayers();
        // Creator serialization temporarily detaches the source Prefab root.
        // Keep inherited/template proxy roots disabled in the bytes being
        // serialized; ordinary disable/destruction still restores them.
        if (!this.serializationPrepared) this.restoreNestedProxyRoots();
    }
    onDestroy(): void { this.clearGeneratedRichTextSorting(); }

    public captureOriginalLayers(nodes: Node[]): void {
        this.sourceNodes = nodes.slice();
        this.originalLayers = nodes.map(node => node.layer);
    }

    public suppressSourceLayers(): void {
        // Nested template presenters own overlapping source Node objects.
        // Deactivate them first so they restore their exact serializer hook
        // before this outer scope installs its own layer contract.
        this.disableNestedProxyRoots();
        for (const node of this.sourceNodes) if (node && node.isValid) node.layer = this.hiddenLayer;
    }

    public restoreSourceLayers(): void {
        for (let index = 0; index < this.sourceNodes.length; index++) {
            const node = this.sourceNodes[index];
            if (node && node.isValid && index < this.originalLayers.length) node.layer = this.originalLayers[index];
        }
    }

    /** Call immediately before serializing/saving the source Prefab asset. */
    public restoreAuthoredLayers(): void { this.restoreSourceLayers(); }
    public prepareForSerialization(): void {
        this.serializationPrepared = true;
        this.restoreAuthoredLayers();
        this.disableNestedProxyRoots();
    }
    public restoreAfterSerialization(): void {
        this.serializationPrepared = false;
        this.initializeEditorInstance();
    }
    public initializeEditorInstance(): void {
        this.serializationPrepared = false;
        this.suppressSourceLayers(); this.initializeProxyRichTextSorting();
    }

    private initializeProxyRichTextSorting(): void {
        if (this.proxyRenderers.length !== this.proxySortOrders.length) return;
        for (let index = 0; index < this.proxyRenderers.length; index++) {
            const richText = this.proxyRenderers[index];
            if (!(richText instanceof RichText)) continue;
            const sourceRichText = this.sourceRenderers[index];
            if (!(sourceRichText instanceof RichText))
                throw new Error(`CREATOR_PROXY_RICHTEXT_SOURCE_IDENTITY:${this.sourceRootId}:${index}`);
            syncGeneratedRichTextSegments(sourceRichText, richText, this.sourceRootId);
            for (const child of richText.node.children) {
                if (!child.hideFlags || (child.name !== 'RICHTEXT_CHILD' && child.name !== 'RICHTEXT_Image_CHILD')) continue;
                const renderers = child.getComponents(UIRenderer);
                if (renderers.length !== 1 || (!(renderers[0] instanceof Label) && !(renderers[0] instanceof Sprite)))
                    throw new Error(`CREATOR_PROXY_RICHTEXT_SEGMENT_RENDERER_IDENTITY:${child.name}`);
                let sorting = child.getComponent(Sorting2D);
                if (!sorting) sorting = child.addComponent(Sorting2D);
                sorting.sortingOrder = this.proxySortOrders[index];
            }
        }
    }

    private clearGeneratedRichTextSorting(): void {
        for (const component of this.proxyRenderers) {
            if (!(component instanceof RichText)) continue;
            for (const child of component.node.children) {
                if (!child.hideFlags || (child.name !== 'RICHTEXT_CHILD' && child.name !== 'RICHTEXT_Image_CHILD')) continue;
                const sorting = child.getComponent(Sorting2D);
                if (sorting) child.removeComponent(sorting);
            }
        }
    }

    private disableNestedProxyRoots(): void {
        for (const root of this.nestedProxyRoots.slice().sort((a, b) => this.depth(a) - this.depth(b)))
            if (root && root.isValid && root.active) root.active = false;
    }

    private restoreNestedProxyRoots(): void {
        const indexes = this.nestedProxyRoots.map((_, index) => index).sort((a, b) =>
            this.depth(this.nestedProxyRoots[b]) - this.depth(this.nestedProxyRoots[a]));
        for (const index of indexes) {
            const root = this.nestedProxyRoots[index];
            if (root && root.isValid && index < this.nestedProxyRootActiveBefore.length)
                root.active = this.nestedProxyRootActiveBefore[index];
        }
    }

    private depth(node: Node): number {
        let value = 0; for (let current: Node | null = node; current; current = current.parent) value++; return value;
    }
}

/**
 * RichText's generated children are DontSave runtime nodes. Pair proxy Labels
 * to the exact source child sequence after each activation so equal-priority
 * Sorting2D renderers retain source draw order after prefab reload. This is a
 * stable identity match by native segment payload, not a text sort.
 */
export function syncGeneratedRichTextSegments(source: RichText, proxy: RichText, ownerId: string): void {
    const generated = (parent: Node): Node[] => parent.children.filter(child => !!child.hideFlags &&
        (child.name === 'RICHTEXT_CHILD' || child.name === 'RICHTEXT_Image_CHILD'));
    const renderer = (node: Node): UIRenderer => {
        const rows = node.getComponents(UIRenderer);
        if (rows.length !== 1 || (!(rows[0] instanceof Label) && !(rows[0] instanceof Sprite)))
            throw new Error(`CREATOR_PROXY_RICHTEXT_SEGMENT_RENDERER_IDENTITY:${ownerId}:${node.name}`);
        return rows[0];
    };
    const refId = (value: any): string | null => value ? value.uuid || value._uuid || null : null;
    const color = (value: any): number[] => [value.r, value.g, value.b, value.a];
    const segmentKey = (node: Node): string => {
        const component = renderer(node);
        const transform = node.getComponent(UITransform);
        if (!transform) throw new Error(`CREATOR_PROXY_RICHTEXT_SEGMENT_TRANSFORM_MISSING:${ownerId}:${node.name}`);
        const position = node.position, rotation = node.rotation, scale = node.scale;
        const common = {
            type: component.constructor.name, active: node.active,
            position: [position.x, position.y, position.z],
            rotation: [rotation.x, rotation.y, rotation.z, rotation.w],
            scale: [scale.x, scale.y, scale.z],
            size: [transform.contentSize.width, transform.contentSize.height],
            anchor: [transform.anchorPoint.x, transform.anchorPoint.y],
            enabled: component.enabled, color: color(component.color),
            customMaterial: refId(component.customMaterial), sharedMaterials: component.sharedMaterials.map(refId),
        };
        if (component instanceof Label) return JSON.stringify({...common, string: component.string,
            font: refId(component.font), fontFamily: component.fontFamily, useSystemFont: component.useSystemFont,
            fontSize: component.fontSize, lineHeight: component.lineHeight, spacingX: component.spacingX,
            overflow: component.overflow, wrap: component.enableWrapText, horizontalAlign: component.horizontalAlign,
            verticalAlign: component.verticalAlign, cacheMode: component.cacheMode, bold: component.isBold,
            italic: component.isItalic, enableOutline: component.enableOutline, outlineColor: color(component.outlineColor),
            // Disabled outline widths are normalized only for the key: Creator's
            // actual pool callback resets to 0, while a fresh Label defaults to 2.
            outlineWidth: component.enableOutline ? component.outlineWidth : 'disabled',
            enableShadow: component.enableShadow, shadowColor: color(component.shadowColor),
            shadowOffset: [component.shadowOffset.x, component.shadowOffset.y], shadowBlur: component.shadowBlur});
        const sprite = component as Sprite;
        return JSON.stringify({...common, frame: refId(sprite.spriteFrame), atlas: refId(sprite.spriteAtlas),
            spriteType: sprite.type, fillType: sprite.fillType, fillStart: sprite.fillStart, fillRange: sprite.fillRange,
            fillCenter: [sprite.fillCenter.x, sprite.fillCenter.y], trim: sprite.trim, sizeMode: sprite.sizeMode});
    };
    const sourceSegments = generated(source.node);
    const proxySegments = generated(proxy.node);
    if (sourceSegments.length !== proxySegments.length || proxy.node.children.length !== proxySegments.length)
        throw new Error(`CREATOR_PROXY_RICHTEXT_SEGMENT_COUNT_MISMATCH:${ownerId}:${sourceSegments.length}:${proxySegments.length}`);
    const unused = new Set(proxySegments);
    const ordered: Node[] = [];
    for (let sourceIndex = 0; sourceIndex < sourceSegments.length; sourceIndex++) {
        const sourceNode = sourceSegments[sourceIndex];
        const sourceRenderer = renderer(sourceNode);
        const sourceKey = segmentKey(sourceNode);
        const matches = proxySegments.filter(candidate => unused.has(candidate) && segmentKey(candidate) === sourceKey);
        if (matches.length !== 1)
            throw new Error(`CREATOR_PROXY_RICHTEXT_SEGMENT_SOURCE_MATCH_${matches.length === 0 ? 'MISSING' : 'AMBIGUOUS'}:${ownerId}:${sourceIndex}:${matches.length}:${sourceKey.slice(0, 240)}`);
        const match = matches[0];
        const proxyRenderer = renderer(match);
        if (sourceRenderer instanceof Label && proxyRenderer instanceof Label && !sourceRenderer.enableOutline &&
            !proxyRenderer.enableOutline && sourceRenderer.outlineWidth !== proxyRenderer.outlineWidth &&
            [sourceRenderer.outlineWidth, proxyRenderer.outlineWidth].every(value => value === 0 || value === 2))
            proxyRenderer.outlineWidth = sourceRenderer.outlineWidth;
        unused.delete(match);
        ordered.push(match);
    }
    if (unused.size !== 0) throw new Error(`CREATOR_PROXY_RICHTEXT_SEGMENT_SOURCE_MATCH_EXTRA:${ownerId}:${unused.size}`);
    for (let index = 0; index < ordered.length; index++) ordered[index].setSiblingIndex(index);
}
