// Persisted provenance alongside the actual native cc.Mask. This component is
// disabled and carries source data only; the native Mask remains the renderer.
import { _decorator, Component, Mask, SpriteFrame } from 'cc';
const { ccclass, property } = _decorator;

@ccclass('MonkeyStaticMaskIdentity')
export class MonkeyStaticMaskIdentity extends Component {
    @property public sourceId = '';
    @property public nativeId = '';
    @property public sourceMaskType = -1;
    @property public sourceInverted = false;
    @property public sourceAlphaThreshold = 0.1;
    @property public sourceFieldsJson = '';
    @property public sourceSpriteFrameUuid = '';
    @property({ type: SpriteFrame }) public sourceSpriteFrame: SpriteFrame | null = null;
    @property({ type: Mask }) public nativeMask: Mask | null = null;
}
