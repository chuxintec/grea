import { _decorator, Component } from 'cc';
const { ccclass, property } = _decorator;

@ccclass('MonkeyStaticSortRootField')
export class CreatorStaticSortRootField extends Component {
    @property public sourceId = '';
    @property public nativeId = '';
    @property public enabledInSource = true;
}
