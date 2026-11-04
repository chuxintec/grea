// This component preserves source-authored UI geometry when Creator's Spine
// Skeleton initialization rewrites UITransform from SkeletonData. It contains
// no recovered gameplay behavior and never interprets the source object graph.
import { _decorator, Component, UITransform } from 'cc';

const { ccclass, property, executeInEditMode, executionOrder } = _decorator;
const GEOMETRY_EPSILON = 0.001;

@ccclass('MonkeySpineUITransformPreserver')
@executeInEditMode(true)
@executionOrder(1000)
export class CreatorSpineUITransformPreserver extends Component {
    @property({ type: UITransform, visible: false })
    public target: UITransform | null = null;

    @property({ visible: false }) public sourceNodeId = '';
    @property({ visible: false }) public sourceWidth = 0;
    @property({ visible: false }) public sourceHeight = 0;
    @property({ visible: false }) public sourceAnchorX = 0.5;
    @property({ visible: false }) public sourceAnchorY = 0.5;

    /** Called once by the importer after exact source geometry is assigned. */
    public configure(
        target: UITransform,
        sourceNodeId: string,
        size: [number, number],
        anchor: [number, number],
    ): void {
        if (!target || target.node !== this.node || typeof sourceNodeId !== 'string' || !sourceNodeId ||
            !CreatorSpineUITransformPreserver.isPair(size) || !CreatorSpineUITransformPreserver.isPair(anchor)) {
            throw new Error('SPINE_UI_TRANSFORM_PRESERVER_CONFIGURATION_INVALID');
        }
        this.target = target;
        this.sourceNodeId = sourceNodeId;
        this.sourceWidth = size[0];
        this.sourceHeight = size[1];
        this.sourceAnchorX = anchor[0];
        this.sourceAnchorY = anchor[1];
        // addComponent() may invoke onLoad/onEnable before the importer has
        // populated serialized fields. Configure is the construction-time
        // application; later callbacks cover reopen/instantiation naturally.
        this.restoreAuthoredNow();
    }

    /**
     * Lifecycle entry point for initial construction and normal scene/Prefab
     * reopen. High executionOrder runs after Spine's default-order onLoad and
     * onEnable callbacks; the component runs in the Editor as well as runtime.
     */
    public onLoad(): void {
        this.restoreFromLifecycle('onLoad');
    }

    public onEnable(): void {
        this.restoreFromLifecycle('onEnable');
    }

    /** Explicit construction-time hook. Reopen readback must never call this. */
    public restoreAuthoredNow(): { sourceNodeId: string; verified: boolean } {
        const target = this.target;
        if (!target || target.node !== this.node || !this.sourceNodeId ||
            !CreatorSpineUITransformPreserver.isPair([this.sourceWidth, this.sourceHeight]) ||
            !CreatorSpineUITransformPreserver.isPair([this.sourceAnchorX, this.sourceAnchorY])) {
            throw new Error('SPINE_UI_TRANSFORM_PRESERVER_STATE_INVALID:' + (this.sourceNodeId || 'unknown'));
        }

        target.setContentSize(this.sourceWidth, this.sourceHeight);
        target.setAnchorPoint(this.sourceAnchorX, this.sourceAnchorY);

        const verified = Math.abs(target.width - this.sourceWidth) <= GEOMETRY_EPSILON &&
            Math.abs(target.height - this.sourceHeight) <= GEOMETRY_EPSILON &&
            Math.abs(target.anchorX - this.sourceAnchorX) <= GEOMETRY_EPSILON &&
            Math.abs(target.anchorY - this.sourceAnchorY) <= GEOMETRY_EPSILON;
        return { sourceNodeId: this.sourceNodeId, verified };
    }

    private restoreFromLifecycle(callback: string): void {
        // A newly attached component is briefly unconfigured before the
        // importer calls configure(). A serialized component always has a
        // target/source ID, so malformed reopened data still reports an error.
        if (!this.target && !this.sourceNodeId) return;
        try {
            const result = this.restoreAuthoredNow();
            if (!result.verified) {
                console.error('SPINE_UI_TRANSFORM_PRESERVER_VERIFY_FAILED:' + callback + ':' + result.sourceNodeId);
            }
        } catch (error) {
            console.error('SPINE_UI_TRANSFORM_PRESERVER_FAILED:' + callback + ':' + String(error));
        }
    }

    private static isPair(value: unknown): value is [number, number] {
        return Array.isArray(value) && value.length === 2 &&
            value.every(channel => typeof channel === 'number' && Number.isFinite(channel));
    }
}
