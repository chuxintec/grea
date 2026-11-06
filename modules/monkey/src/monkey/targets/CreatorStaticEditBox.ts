// Typed, disabled EditBox carrier for fixed-state Prefabs. The base EditBox's
// __preload/onEnable mutate layout and create editing implementation state, so
// this subclass intentionally does not run those base lifecycle methods.
import { _decorator, EditBox, Label, Sprite } from 'cc';

const { ccclass, property } = _decorator;

@ccclass('MonkeyStaticEditBox')
export class MonkeyStaticEditBox extends EditBox {
    @property public sourceComponentId = '';
    @property public sourceNodeId = '';
    @property public sourceEnabled = false;
    @property({ type: Sprite }) public sourceBackground: Sprite | null = null;
    @property({ type: Label }) public sourcePlaceholderLabel: Label | null = null;
    @property({ type: Label }) public sourceTextLabel: Label | null = null;
    @property public sourceMaxLength = 0;

    public __preload(): void {}
    public onEnable(): void {}
    public onDisable(): void {}
    public onDestroy(): void {}
}
