import { _decorator, Component, Node } from 'cc';
const { ccclass, property } = _decorator;

@ccclass('MonkeyStaticSortQueueProxyMarker')
export class CreatorStaticSortQueueProxyMarker extends Component {
    @property public kind = '';
    @property public sourceNode = '';
    @property(Node) public sourceRootOwner: Node | null = null;
    @property public sourceComponentId = '';
    @property public sourceType = '';
    @property public maskType = -1;
    @property public inverted = false;
    @property public queueIndex = -1;
    @property public sortOrder = -1;
    @property public sourceFingerprint = '';
    @property public generatedRootActiveBefore = true;
}
