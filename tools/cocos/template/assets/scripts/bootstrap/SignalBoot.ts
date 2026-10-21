import { _decorator, Component, Node, Canvas, Camera, Layers, view, ResolutionPolicy, Color } from 'cc';
import { CounterSession } from '../gameplay/CounterSession';
import { CounterView } from '../presentation/CounterView';
import { JsonCounterConfig } from '../services/JsonCounterConfig';
const { ccclass } = _decorator;
@ccclass('SignalBoot')
export class SignalBoot extends Component {
    private alive = true;
    private session?: CounterSession;
    private screen?: CounterView;
    async start() {
        view.setDesignResolutionSize(__WIDTH__, __HEIGHT__, ResolutionPolicy.SHOW_ALL);
        const step = await new JsonCounterConfig().load();
        if (!this.alive) return;
        const canvasNode = new Node('Canvas'); canvasNode.layer = Layers.Enum.UI_2D; this.node.addChild(canvasNode);
        const canvas = canvasNode.addComponent(Canvas);
        const cameraNode = new Node('UICamera'); this.node.addChild(cameraNode); cameraNode.setPosition(0, 0, 1000);
        const camera = cameraNode.addComponent(Camera); camera.projection = Camera.ProjectionType.ORTHO;
        camera.orthoHeight = __HEIGHT__ / 2; camera.visibility = Layers.Enum.UI_2D; camera.clearColor = new Color(24, 32, 48, 255);
        canvas.cameraComponent = camera;
        const control = new Node('Counter'); canvasNode.addChild(control);
        this.session = new CounterSession(step); this.screen = new CounterView(control, this.session);
    }
    onDestroy() { this.alive = false; this.screen?.dispose(); this.session?.dispose(); }
}
