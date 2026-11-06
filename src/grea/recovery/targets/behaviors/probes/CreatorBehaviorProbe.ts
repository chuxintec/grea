import { _decorator, Component, Node, Vec3, isValid } from 'cc';
import { BreathEffect } from '../BreathEffect';
import { ScaleBackEffect } from '../ScaleBackEffect';

const { ccclass, property } = _decorator;

interface ProbeObservation {
    id: string;
    elapsedSeconds: number;
    scale: number[] | null;
    scaleState: 'measured' | 'unavailable';
    nodeExists: boolean;
    active: boolean;
    componentEnabled: boolean;
}

@ccclass('MonkeyRecoveredCreatorBehaviorProbe')
export class CreatorBehaviorProbe extends Component {
    @property runOnLoad = false;
    @property tweenSeconds = 0.4;
    @property breathDelaySeconds = 0.3;
    @property breathOffset = 0.2;
    @property scaleBackFrom = 0.6;

    private observations: ProbeObservation[] = [];
    private taskResults: Array<{ name: string; completed: boolean; faulted: boolean }> = [];
    private clockOrigin = 0;

    start(): void {
        if (!this.runOnLoad) return;
        this.runOnLoad = false;
        void this.runProbe().catch(error => console.error('MONKEY_BEHAVIOR_PROBE_ERROR', error));
    }

    /** Invoke manually from a serialized acceptance scene; never auto-runs. */
    async runProbe(): Promise<string> {
        this.observations = [];
        this.taskResults = [];
        await this.probeBreathCycle();
        await this.probeBreathLifecycle();
        await this.probeScaleBack();
        await this.probeScaleBackLifecycle();
        await this.probeScaleBackDestroy();
        const receipt = {
            schema: 'monkey-prefab-behavior-runtime-probe/1',
            targetEngine: 'Cocos Creator 3.8.8',
            sourceEngine: 'Cocos Creator 2.4.15',
            ruleVersion: 'monkey-prefab-local-behaviors/1',
            probeRevision: 'scaleBack-hide-isolated-02',
            sourceBundleSha256: '21af08e48846f6ad1a2e0673b0c945358136723b1664f0cd1f6ec9b3df6c5cb5',
            breathEffectSha256: 'a44e4524015e193da241958bfe2b47901a6232ac89e0e063b59a9a362da94617',
            scaleBackEffectSha256: 'ab661a87764aba785f3039b2767301d8b854031b1b57f813a559bf5a09e6c924',
            timeScale: null,
            tweenSeconds: this.tweenSeconds,
            breathDelaySeconds: this.breathDelaySeconds,
            breathOffset: this.breathOffset,
            scaleBackFrom: this.scaleBackFrom,
            sampleClock: 'performance.now; samples scheduled by wall-clock setTimeout, target tween uses Creator director frames',
            checkpointPlan: [
                { id: 'breath.start', relativeTo: 'breathCycleStart', seconds: 0, expectedScale: [2, 3, 4], sourceMeaning: 'onLoad reads scale.x without writing the node' },
                { id: 'breath.riseHalf', relativeTo: 'breathCycleStart', seconds: 0.2, expectedScale: [2.1, 2.1, 2.1], sourceMeaning: 'quadInOut midpoint after scalar X capture and uniform setScale' },
                { id: 'breath.riseEnd', relativeTo: 'breathCycleStart', seconds: 0.4, expectedScale: [2.2, 2.2, 2.2], sourceMeaning: 'first tween reaches captured X plus offset' },
                { id: 'breath.fallHalf', relativeTo: 'breathCycleStart', seconds: 0.6, expectedScale: [2.1, 2.1, 2.1], sourceMeaning: 'return tween quadInOut midpoint' },
                { id: 'breath.fallEnd', relativeTo: 'breathCycleStart', seconds: 0.8, expectedScale: [2, 2, 2], sourceMeaning: 'return tween reaches captured scalar X' },
                { id: 'scaleBack.showInstant', relativeTo: 'scaleBackStart', seconds: 0, expectedScale: [0.6, 0.6, 0.6], sourceMeaning: 'show assigns scaleFrom before starting the tween' },
                { id: 'scaleBack.showHalf', relativeTo: 'scaleBackStart', seconds: 0.2, expectedScale: [1.035, 1.035, 1.035], sourceMeaning: 'backOut midpoint checkpoint' },
                { id: 'scaleBack.showEnd', relativeTo: 'scaleBackStart', seconds: 0.4, expectedScale: [1, 1, 1], sourceMeaning: 'show tween reaches uniform scale one' },
                { id: 'scaleBack.overlapHideInitial', relativeTo: 'scaleBackOverlapStart', seconds: 0, expectedScale: [], sourceMeaning: 'immediate show-to-hide overlap observation; timer and tween frame order is unspecified' },
                { id: 'scaleBack.overlapHideHalf', relativeTo: 'scaleBackOverlapStart', seconds: 0.2, expectedScale: [], sourceMeaning: 'immediate show-to-hide overlap observation; no deterministic midpoint oracle' },
                { id: 'scaleBack.overlapHideEnd', relativeTo: 'scaleBackOverlapStart', seconds: 0.4, expectedScale: [], sourceMeaning: 'immediate show-to-hide overlap observation; source hide assigns zero after its timer' },
                { id: 'scaleBack.hideInitial', relativeTo: 'scaleBackHideOnlyStart', seconds: 0, expectedScale: [2, 3, 4], sourceMeaning: 'fresh node preserves nonuniform initial scale before hide tween update' },
                { id: 'scaleBack.hideHalf', relativeTo: 'scaleBackHideOnlyStart', seconds: 0.2, expectedScale: [2.123, 2.123, 2.123], sourceMeaning: 'isolated backIn midpoint from scalar X=2 toward scaleFrom' },
                { id: 'scaleBack.hideEnd', relativeTo: 'scaleBackHideOnlyStart', seconds: 0.4, expectedScale: [0, 0, 0], sourceMeaning: 'isolated hide sets scale zero after kt timer resolves' },
                { id: 'scaleBack.hideInstant', relativeTo: 'scaleBackHideOnlyStart', seconds: 0.4, expectedScale: [0, 0, 0], sourceMeaning: 'tweenHide false sets scale zero without a tween' },
            ].map(checkpoint => ({
                ...checkpoint,
                expectedScaleState: checkpoint.expectedScale.length === 0 ? 'unspecified' : 'specified',
            })),
            unknownSemantics: [
                'BaseEffect.reset stopAllActions node-wide cancellation remains unclosed because native tween/coroutine ownership is component-local and untracked node actions have no shared typed registry',
                'ScaleBackEffect disable/destroy tween cancellation is not specified by its source hooks',
                'Immediate ScaleBackEffect show-to-hide overlap is recorded without a deterministic midpoint oracle because wall-clock kt and engine-frame tween completion can race'
            ],
            taskExpectations: ['scaleBack.show', 'scaleBack.overlapHide', 'scaleBack.hideOnly', 'scaleBack.hideInstant', 'scaleBack.disabledShow', 'scaleBack.destroyDuringTweenShow'],
            destructionChecks: ['breath.destroyed', 'breath.lifecycleDestroyed', 'scaleBack.overlapDestroyed', 'scaleBack.destroyed', 'scaleBack.lifecycleDestroyed', 'scaleBack.destroyDuringTween'],
            stabilityChecks: [
                { name: 'running_false_holds_scale', beforeId: 'breath.runningFalseBefore', afterId: 'breath.runningFalseAfter', tolerance: 0.015 },
                { name: 'disabled_breath_cancels_owned_tween', beforeId: 'breath.disabledBefore', afterId: 'breath.disabledAfter', tolerance: 0.015 },
            ],
            observations: this.observations,
            taskResults: this.taskResults,
        };
        const json = JSON.stringify(receipt);
        console.log('MONKEY_BEHAVIOR_PROBE:' + json);
        return json;
    }

    private async probeBreathCycle(): Promise<void> {
        const node = this.newInactiveNode('BreathCycle', new Vec3(2, 3, 4));
        const behaviour = node.addComponent(BreathEffect);
        behaviour.tweenTime = this.tweenSeconds;
        behaviour.delay = this.breathDelaySeconds;
        behaviour.offset = this.breathOffset;
        this.clockOrigin = performance.now();
        node.active = true;
        this.record('breath.start', node, behaviour);
        await this.wait(this.tweenSeconds * 0.5);
        this.record('breath.riseHalf', node, behaviour);
        await this.wait(this.tweenSeconds * 0.5);
        this.record('breath.riseEnd', node, behaviour);
        await this.wait(this.tweenSeconds * 0.5);
        this.record('breath.fallHalf', node, behaviour);
        await this.wait(this.tweenSeconds * 0.5);
        this.record('breath.fallEnd', node, behaviour);
        node.destroy();
        await this.wait(0.05);
        this.recordDestroyed('breath.destroyed');
    }

    private async probeBreathLifecycle(): Promise<void> {
        const node = this.newInactiveNode('BreathLifecycle', new Vec3(2, 3, 4));
        const behaviour = node.addComponent(BreathEffect);
        behaviour.tweenTime = this.tweenSeconds;
        behaviour.delay = this.breathDelaySeconds;
        behaviour.offset = this.breathOffset;
        this.clockOrigin = performance.now();
        node.active = true;
        await this.wait(this.tweenSeconds * 0.5);
        behaviour.running = false;
        this.record('breath.runningFalseBefore', node, behaviour);
        await this.wait(0.12);
        this.record('breath.runningFalseAfter', node, behaviour);
        behaviour.running = true;
        await this.wait(this.tweenSeconds * 0.5);
        this.record('breath.resumedHalf', node, behaviour);
        behaviour.enabled = false;
        this.record('breath.disabledBefore', node, behaviour);
        await this.wait(0.12);
        this.record('breath.disabledAfter', node, behaviour);
        behaviour.enabled = true;
        await this.wait(0.08);
        node.destroy();
        await this.wait(0.05);
        this.recordDestroyed('breath.lifecycleDestroyed');
    }

    private async probeScaleBack(): Promise<void> {
        const node = this.newInactiveNode('ScaleBackShowOverlap', new Vec3(2, 3, 4));
        const behaviour = node.addComponent(ScaleBackEffect);
        behaviour.tweenTime = this.tweenSeconds;
        behaviour.scaleFrom = this.scaleBackFrom;
        behaviour.tweenHide = true;
        this.clockOrigin = performance.now();
        node.active = true;
        const show = behaviour.show();
        await Promise.resolve();
        this.record('scaleBack.showInstant', node, behaviour);
        await this.wait(this.tweenSeconds * 0.5);
        this.record('scaleBack.showHalf', node, behaviour);
        await show;
        this.taskResults.push({ name: 'scaleBack.show', completed: true, faulted: false });
        this.record('scaleBack.showEnd', node, behaviour);

        this.clockOrigin = performance.now();
        node.setScale(2, 3, 4);
        const overlapHide = behaviour.hide();
        this.record('scaleBack.overlapHideInitial', node, behaviour);
        await this.wait(this.tweenSeconds * 0.5);
        this.record('scaleBack.overlapHideHalf', node, behaviour);
        await overlapHide;
        this.taskResults.push({ name: 'scaleBack.overlapHide', completed: true, faulted: false });
        this.record('scaleBack.overlapHideEnd', node, behaviour);
        node.destroy();
        await this.wait(0.05);
        this.recordDestroyed('scaleBack.overlapDestroyed');

        const hideOnlyNode = this.newInactiveNode('ScaleBackHideOnly', new Vec3(2, 3, 4));
        const hideOnlyBehaviour = hideOnlyNode.addComponent(ScaleBackEffect);
        hideOnlyBehaviour.tweenTime = this.tweenSeconds;
        hideOnlyBehaviour.scaleFrom = this.scaleBackFrom;
        hideOnlyBehaviour.tweenHide = true;
        this.clockOrigin = performance.now();
        hideOnlyNode.active = true;
        const hide = hideOnlyBehaviour.hide();
        this.record('scaleBack.hideInitial', hideOnlyNode, hideOnlyBehaviour);
        await this.wait(this.tweenSeconds * 0.5);
        this.record('scaleBack.hideHalf', hideOnlyNode, hideOnlyBehaviour);
        await hide;
        this.taskResults.push({ name: 'scaleBack.hideOnly', completed: true, faulted: false });
        this.record('scaleBack.hideEnd', hideOnlyNode, hideOnlyBehaviour);

        hideOnlyBehaviour.tweenHide = false;
        await hideOnlyBehaviour.hide();
        this.taskResults.push({ name: 'scaleBack.hideInstant', completed: true, faulted: false });
        this.record('scaleBack.hideInstant', hideOnlyNode, hideOnlyBehaviour);
        hideOnlyNode.destroy();
        await this.wait(0.05);
        this.recordDestroyed('scaleBack.destroyed');
    }

    private async probeScaleBackLifecycle(): Promise<void> {
        const node = this.newInactiveNode('ScaleBackLifecycle', new Vec3(2, 3, 4));
        const behaviour = node.addComponent(ScaleBackEffect);
        behaviour.tweenTime = this.tweenSeconds;
        behaviour.scaleFrom = this.scaleBackFrom;
        this.clockOrigin = performance.now();
        node.active = true;
        const show = behaviour.show();
        await this.wait(0.1);
        node.active = false;
        this.record('scaleBack.disabled', node, behaviour);
        await show;
        this.taskResults.push({ name: 'scaleBack.disabledShow', completed: true, faulted: false });
        node.destroy();
        await this.wait(0.05);
        this.recordDestroyed('scaleBack.lifecycleDestroyed');
    }

    private async probeScaleBackDestroy(): Promise<void> {
        const node = this.newInactiveNode('ScaleBackDestroyDuringTween', new Vec3(2, 3, 4));
        const behaviour = node.addComponent(ScaleBackEffect);
        behaviour.tweenTime = this.tweenSeconds;
        behaviour.scaleFrom = this.scaleBackFrom;
        this.clockOrigin = performance.now();
        node.active = true;
        const show = behaviour.show();
        await this.wait(0.1);
        node.destroy();
        await this.wait(0.05);
        this.recordDestroyed('scaleBack.destroyDuringTween');
        await show;
        this.taskResults.push({ name: 'scaleBack.destroyDuringTweenShow', completed: true, faulted: false });
    }

    private newInactiveNode(name: string, scale: Vec3): Node {
        const node = new Node(name);
        node.active = false;
        node.setScale(scale);
        node.parent = this.node;
        return node;
    }

    private record(id: string, node: Node, component: Component): void {
        const scale = node.scale;
        this.observations.push({
            id,
            elapsedSeconds: (performance.now() - this.clockOrigin) / 1000,
            scale: [scale.x, scale.y, scale.z],
            scaleState: 'measured',
            nodeExists: isValid(node),
            active: node.activeInHierarchy,
            componentEnabled: component.enabled,
        });
    }

    private recordDestroyed(id: string): void {
        this.observations.push({
            id,
            elapsedSeconds: (performance.now() - this.clockOrigin) / 1000,
            scale: null,
            scaleState: 'unavailable',
            nodeExists: false,
            active: false,
            componentEnabled: false,
        });
    }

    private wait(seconds: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, Math.max(0, seconds * 1000)));
    }
}
