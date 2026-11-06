import { _decorator, Component, Rect, UITransform, Vec3, Widget } from 'cc';
import { ViewportNotchProvider } from './ViewportNotchProvider';
const { ccclass, property } = _decorator;

@ccclass('MonkeyRecoveredAutoScaleComp')
export class AutoScaleComp extends Component {
    @property(ViewportNotchProvider)
    viewportProvider: ViewportNotchProvider | null = null;

    private initialY = 0;

    onLoad(): void { this.initialY = this.node.position.y; }

    onEnable(): void {
        if (this.getComponent(Widget) !== null) {
            throw new Error('AutoScaleComp blocked: a Widget layout writer is attached to the same node.');
        }
        const metrics = this.viewportProvider?.tryGetSnapshot();
        const transform = this.getComponent(UITransform);
        if (!metrics || !transform) {
            throw new Error('AutoScaleComp blocked: explicit viewport/notch metrics and UITransform are required.');
        }
        const inset = metrics.statusNotchHeight > 0 ? metrics.statusNotchHeight : 0;
        const availableHeight = metrics.visibleSize.height - inset;
        const width = transform.width;
        const height = transform.height;
        this.node.setPosition(this.node.position.x, this.initialY - 0.5 * inset, this.node.position.z);
        const viewport = new Rect(0, -0.5 * inset, metrics.visibleSize.width, availableHeight);
        const nodeRect = new Rect(0, 0, width, height);
        if (!(viewport.containsRect(nodeRect) || height <= availableHeight)) {
            if (!(height > 0)) throw new Error('AutoScaleComp blocked: node height must be positive before scale division.');
            const scale = availableHeight / height;
            this.node.setScale(new Vec3(scale, scale, scale));
        }
    }
}
