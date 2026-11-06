import { _decorator, Component, Size, view } from 'cc';
const { ccclass, property } = _decorator;

export interface ViewportNotchSnapshot {
    visibleSize: Size;
    statusNotchHeight: number;
}

@ccclass('MonkeyRecoveredViewportNotchProvider')
export class ViewportNotchProvider extends Component {
    // Negative is an unconfigured sentinel; zero must be deliberately supplied.
    @property statusNotchHeight = -1;

    tryGetSnapshot(): ViewportNotchSnapshot | null {
        if (!Number.isFinite(this.statusNotchHeight) || this.statusNotchHeight < 0) return null;
        const visibleSize = view.getVisibleSize();
        if (!(visibleSize.width > 0) || !(visibleSize.height > 0)) return null;
        return { visibleSize, statusNotchHeight: this.statusNotchHeight };
    }
}
