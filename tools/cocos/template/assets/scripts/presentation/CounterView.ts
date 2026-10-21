import { Node, Label, UITransform, Layers } from 'cc';
import { CounterSession } from '../gameplay/CounterSession';
export class CounterView {
    private label: Label;
    private readonly click = () => { this.label.string = `SIGNAL ${this.session.press().value}\nTap to increment`; };
    constructor(private node: Node, private session: CounterSession) {
        node.layer = Layers.Enum.UI_2D;
        node.addComponent(UITransform).setContentSize(600, 240);
        this.label = node.addComponent(Label);
        this.label.fontSize = 40; this.label.lineHeight = 56;
        this.label.string = `SIGNAL ${session.snapshot().value}\nTap to increment`;
        node.on(Node.EventType.TOUCH_END, this.click);
    }
    dispose() { this.node.off(Node.EventType.TOUCH_END, this.click); }
}
