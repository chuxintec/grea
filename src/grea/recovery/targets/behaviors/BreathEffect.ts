import { _decorator, Component, Node, Tween, Vec3, tween } from 'cc';
const { ccclass, property, disallowMultiple, menu } = _decorator;

@ccclass('MonkeyRecoveredBreathEffect')
@disallowMultiple
@menu('UIEffect/BreathEffect')
export class BreathEffect extends Component {
    @property delay = 0.3;
    @property tweenTime = 0.7;
    @property offset = 0.1;

    private _running = true;
    private startValue = 1;
    private endValue = 1;
    private action: Tween<Node> | null = null;

    get running(): boolean { return this._running; }
    set running(value: boolean) {
        if (this._running === value) return;
        this._running = value;
        this.playEffect();
    }

    onLoad(): void {
        this.startValue = this.node.scale.x;
        this.endValue = this.startValue + this.offset;
    }

    onEnable(): void { this.playEffect(); }

    onDisable(): void {
        this.action?.stop();
        this.action = null;
    }

    private playEffect(): void {
        this.action?.stop();
        this.action = null;
        if (!this._running || !this.enabled || !this.node.activeInHierarchy) return;
        const writeUniformScale = (node: Node): void => {
            const scale = node.scale.x;
            node.setScale(scale, scale, scale);
        };
        this.action = tween(this.node)
            .to(this.tweenTime, { scale: new Vec3(this.endValue, this.endValue, this.endValue) },
                { easing: 'quadInOut', onUpdate: writeUniformScale })
            .to(this.tweenTime, { scale: new Vec3(this.startValue, this.startValue, this.startValue) },
                { easing: 'quadInOut', onUpdate: writeUniformScale })
            .delay(this.delay)
            .call(() => this.playEffect())
            .start();
    }
}
