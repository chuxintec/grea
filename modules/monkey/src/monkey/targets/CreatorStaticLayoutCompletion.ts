// Typed, persistent ownership for source Layout / Widget components.
// The actual engine components remain cc.Layout and cc.Widget; these slots keep
// source identity/order and typed references so duplicate Layouts survive saves.
import { _decorator, Component, Layout, Widget, CCString } from 'cc';
const { ccclass, property } = _decorator;

@ccclass('MonkeyStaticLayoutSlot')
export class MonkeyStaticLayoutSlot {
    @property public sourceComponentId = '';
    @property public componentOrder = 0;
    @property public sourceEnabled = false;
    @property public layoutType = 0;
    @property public resize = 0;
    @property public startAxis = 0;
    @property public horizontalDirection = 0;
    @property public verticalDirection = 1;
    @property public affectedByScale = false;
    @property public paddingLeft = 0;
    @property public paddingBottom = 0;
    @property public paddingRight = 0;
    @property public paddingTop = 0;
    @property public spacingX = 0;
    @property public spacingY = 0;
    @property public cellWidth = 40;
    @property public cellHeight = 40;
    @property public sourceLayoutCacheWidth = 0;
    @property public sourceLayoutCacheHeight = 0;
    @property public hasSourceLayoutCacheSize = false;
    @property({ type: Layout }) public nativeLayout: Layout | null = null;
    @property({ type: [CCString] }) public sourceFieldPresence: string[] = [];
    @property({ type: [CCString] }) public unknownSourceFields: string[] = [];
}

@ccclass('MonkeyStaticWidgetSlot')
export class MonkeyStaticWidgetSlot {
    @property public sourceComponentId = '';
    @property public componentOrder = 0;
    @property public sourceEnabled = false;
    @property public alignFlags = 0;
    @property public alignMode = 1;
    @property public left = 0;
    @property public bottom = 0;
    @property public right = 0;
    @property public top = 0;
    @property public isAbsLeft = true;
    @property public isAbsBottom = true;
    @property public isAbsRight = true;
    @property public isAbsTop = true;
    @property public horizontalCenter = 0;
    @property public verticalCenter = 0;
    @property public isAbsHorizontalCenter = true;
    @property public isAbsVerticalCenter = true;
    @property public originalWidth = 0;
    @property public originalHeight = 0;
    @property public hasOriginalWidth = false;
    @property public hasOriginalHeight = false;
    @property public targetSourceNodeId = '';
    @property({ type: Widget }) public nativeWidget: Widget | null = null;
    @property({ type: [CCString] }) public sourceFieldPresence: string[] = [];
    @property({ type: [CCString] }) public unknownSourceFields: string[] = [];
}

@ccclass('MonkeyStaticLayoutCompletion')
export class MonkeyStaticLayoutCompletion extends Component {
    @property public sourceNodeId = '';
    @property({ type: [CCString] }) public sourceChildNodeIds: string[] = [];
    @property({ type: [MonkeyStaticLayoutSlot] }) public layouts: MonkeyStaticLayoutSlot[] = [];
    @property({ type: MonkeyStaticWidgetSlot }) public widget: MonkeyStaticWidgetSlot | null = null;
}
