import { _decorator, Component, Node, Tween, Widget } from 'cc';
const { ccclass, disallowMultiple, property } = _decorator;

@ccclass('MonkeyRecoveredBaseEffect')
@disallowMultiple
export class BaseEffect extends Component {
    @property delay = 0;
    @property tweenTime = 0.3;

    protected initScale = 1;
    protected readonly ownedActions = new Set<Tween<Node>>();
    private widget: Widget | null = null;

    onLoad(): void {
        this.initScale = this.node.scale.x;
        this.reset();
        this.widget = this.getComponent(Widget);
        this.widget?.updateAlignment();
    }

    protected reset(): void {
        for (const action of this.ownedActions) action.stop();
        this.ownedActions.clear();
    }

    protected startOwnedAction(action: Tween<Node>): void {
        this.ownedActions.add(action);
        action.call(() => this.ownedActions.delete(action)).start();
    }

    async show(_data: unknown = null): Promise<void> { this.reset(); }
    async hide(_data: unknown = null): Promise<void> {}

    async excute(action: () => Promise<void>): Promise<void> {
        if (this.node.activeInHierarchy) await action();
    }
}
