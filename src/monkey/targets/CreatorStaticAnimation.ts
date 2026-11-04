// Persisted Creator marker for source-bound static animation references.
// All source order/identity data is typed; JSON is not used as a carrier.
import { _decorator, AnimationClip, Component, JsonAsset, CCString } from 'cc';
const { ccclass, property } = _decorator;

@ccclass('MonkeyStaticAnimationClipSlot')
export class MonkeyStaticAnimationClipSlot {
    @property public order = 0;
    @property public sourceClipId = '';
    @property public planAnimationId = '';
    @property public status = '';
    @property public curveStatus = '';
    @property public partial = true;
    @property public nativeClipPath = '';
    @property public nativeClipGuid = '';
    @property public nativeClipSha256 = '';
    @property public sourceEvidencePath = '';
    @property public sourceEvidenceGuid = '';
    @property public sourceEvidenceSha256 = '';
    @property({ type: [CCString] }) public gapCodes: string[] = [];
    @property({ type: AnimationClip }) public nativeClip: AnimationClip | null = null;
    @property({ type: JsonAsset }) public sourceEvidence: JsonAsset | null = null;
}

@ccclass('MonkeyNativeStaticAnimationBinding')
export class MonkeyNativeStaticAnimationBinding extends Component {
    @property public sourceComponentId = '';
    @property public sourceNodeId = '';
    @property public sourceEnabled = false;
    @property public sourceEnabledKnown = false;
    @property public sourcePlayOnLoad = false;
    @property public sourcePlayOnLoadKnown = false;
    @property public sourceDefaultClipId = '';
    @property public sourceDefaultClipKnown = false;
    @property public hasSourceDefaultClip = false;
    @property({ type: [CCString] }) public sourceClipOrder: string[] = [];
    @property({ type: [MonkeyStaticAnimationClipSlot] }) public sourceClips: MonkeyStaticAnimationClipSlot[] = [];
    @property({ type: AnimationClip }) public nativeDefaultClip: AnimationClip | null = null;
    @property({ type: [AnimationClip] }) public nativeClips: AnimationClip[] = [];
    @property({ type: [JsonAsset] }) public sourceEvidenceAssets: JsonAsset[] = [];
}
