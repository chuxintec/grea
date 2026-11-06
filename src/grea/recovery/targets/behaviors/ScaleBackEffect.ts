import { _decorator, Vec3, tween } from 'cc';
import { BaseEffect } from './BaseEffect';
const { ccclass, disallowMultiple, property, menu } = _decorator;

@ccclass('MonkeyRecoveredScaleBackEffect')
@disallowMultiple
@menu('UIEffect/ScaleBackEffect')
export class ScaleBackEffect extends BaseEffect {
    @property tweenHide = false;
    @property scaleFrom = 0.7;

    onLoad(): void { super.onLoad(); }

    async show(data: unknown = null): Promise<void> {
        await super.show(data);
        this.node.setScale(new Vec3(this.scaleFrom, this.scaleFrom, this.scaleFrom));
        this.startOwnedAction(tween(this.node)
            .to(this.tweenTime, { scale: new Vec3(1, 1, 1) }, {
                easing: 'backOut', onUpdate: node => {
                    const scale = node.scale.x;
                    node.setScale(scale, scale, scale);
                }
            }));
        await new Promise<void>(resolve => setTimeout(resolve, 1000 * this.tweenTime));
    }

    async hide(_data: unknown = null): Promise<void> {
        if (!this.tweenHide) {
            this.node.setScale(new Vec3(0, 0, 0));
            return;
        }
        this.startOwnedAction(tween(this.node)
            .to(this.tweenTime, { scale: new Vec3(this.scaleFrom, this.scaleFrom, this.scaleFrom) }, {
                easing: 'backIn', onUpdate: node => {
                    const scale = node.scale.x;
                    node.setScale(scale, scale, scale);
                }
            }));
        await new Promise<void>(resolve => setTimeout(resolve, 1000 * this.tweenTime));
        this.node.setScale(new Vec3(0, 0, 0));
    }
}
