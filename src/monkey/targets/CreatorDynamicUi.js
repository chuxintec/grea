'use strict';
const cc=require('cc');
const ownedUndo=require('./owned-import-undo.js');
const enabled=plan=>plan.uiGeometryReadback==='native-ui-layout-roundtrip-v1';
function capture(nodes){return [...nodes].map(([sourceId,n])=>({sourceId,position:[n.position.x,n.position.y,n.position.z],size:[n.getComponent(cc.UITransform).width,n.getComponent(cc.UITransform).height]}));}
function drivenFields(plan,sourceId){
    const result={};
    for(const [key,axes]of Object.entries((plan.uiDrivenFields||{})[sourceId]||{}))
        if(Array.isArray(axes))result[key]=[...new Set(axes)];
    return result;
}
function alignWidgets(nodes,root){
    const restore=[];
    try{
        // Creator 3.8.8 updateAlignment recursively aligns disabled ancestors,
        // unlike its normal frame traversal. Hide only disabled Widgets from
        // this synchronous lookup on owned node instances. Never patch Node's
        // prototype, the Editor scene, or a serialized/runtime component.
        for(const node of nodes.values()){
            const widget=node.getComponent(cc.Widget);if(!widget||widget.enabled)continue;
            const descriptor=Object.getOwnPropertyDescriptor(node,'getComponent'),original=node.getComponent;
            restore.push(()=>{if(descriptor)Object.defineProperty(node,'getComponent',descriptor);else delete node.getComponent;});
            Object.defineProperty(node,'getComponent',{configurable:true,writable:true,value:function(type){return type===cc.Widget&&!widget.enabled?null:original.call(this,type);}});
        }
        for(const node of nodes.values())if(node.activeInHierarchy&&node!==root){const widget=node.getComponent(cc.Widget);if(widget&&widget.enabled)widget.updateAlignment();}
    }finally{for(const undo of restore.reverse())undo();}
}
function settle(scene,nodes,plan,root=null,initialize=false){
    if(!enabled(plan))return;
    const manager=cc.widgetManager;
    if(!manager||typeof manager.isAligning!=='boolean')throw Error('Native Widget update context unavailable');
    const previous=manager.isAligning;manager.isAligning=true;
    try{return settleOwned(scene,nodes,plan,root,initialize);}finally{manager.isAligning=previous;}
}
function settleOwned(scene,nodes,plan,root=null,initialize=false){
    if(!enabled(plan))return;
    scene._load();scene._activate(true);
    // Editor component setters and Layout.onEnable can replace source geometry
    // (notably a zero-size Layout's default 300x200). Restore the input once,
    // then let only enabled native components compute their driven axes.
    if(initialize)for(const spec of (Array.isArray(initialize)?initialize:plan.nodes)){
        const node=nodes.get(spec.sourceId);if(!node)throw Error('Native UI initial node missing');
        const driven=drivenFields(plan,spec.sourceId),ui=node.getComponent(cc.UITransform);
        const position=[node.position.x,node.position.y,node.position.z],size=[ui.width,ui.height];
        for(let axis=0;axis<3;axis++)if(!(driven.position||[]).includes(axis))position[axis]=spec.position[axis];
        for(let axis=0;axis<2;axis++)if(!(driven.size||[]).includes(axis))size[axis]=spec.size[axis];
        if(position.some((v,i)=>v!==[node.position.x,node.position.y,node.position.z][i]))node.setPosition(...position);
        // Setting a RAW/TRIMMED Sprite's size in the Editor switches it to
        // CUSTOM. Leave component-driven dimensions and equal values alone.
        if(size[0]!==ui.width||size[1]!==ui.height)ui.setContentSize(...size);
    }
    let differences=[];
    for(let pass=0;pass<8;pass++){
        const before=capture(nodes);
        for(const n of nodes.values())if(n.activeInHierarchy){
            const label=n.getComponent(cc.Label);if(label&&label.enabled)label.updateRenderData(true);
            const richText=n.getComponent(cc.RichText);
            if(richText&&richText.enabled){
                const update=richText._updateRichTextStatus||richText._updateRichText;
                if(typeof update!=='function')throw Error('Native RichText size update unavailable');
                update.call(richText);
            }
        }
        alignWidgets(nodes,root);
        for(const n of [...nodes.values()].reverse())if(n.activeInHierarchy)for(const layout of n.getComponents(cc.Layout))if(layout.enabled)layout.updateLayout(true);
        const after=capture(nodes);differences=[];
        after.forEach((row,i)=>{for(const key of ['position','size'])if(row[key].some((v,j)=>!Number.isFinite(v)||Math.abs(v-before[i][key][j])>.001))differences.push({sourceId:row.sourceId,key,before:before[i][key],after:row[key]});});
        if(!differences.length)return;
    }
    throw Error('Native UI layout did not settle within eight passes: '+JSON.stringify(differences.slice(0,2)));
}
function settleRoot(root,nodes,plan,initialize=true){
    if(!enabled(plan))return capture(nodes);
    const scene=new cc.Scene('OwnedPrefabLayoutProbe'),context=new cc.Node('OwnedPrefabUiContext');
    ownedUndo.registerRoot(scene);ownedUndo.registerRoot(context);
    const ui=context.addComponent(cc.UITransform);ui.setContentSize(...plan.designSize);ui.setAnchorPoint(0,0);context.parent=scene;root.parent=context;
    try{settle(scene,nodes,plan,root,initialize?capture(nodes):false);return capture(nodes);}
    finally{root.parent=null;scene._activate(false);scene.destroy();}
}
function expected(source,plan,rows){
    if(!enabled(plan))return source;
    const row=(rows||[]).find(x=>x.sourceId===source.sourceId);if(!row)throw Error('Native pre-save geometry absent: '+source.sourceId);
    const result={...source};
    for(const [key,axes]of Object.entries(drivenFields(plan,source.sourceId))){
        result[key]=[...source[key]];for(const axis of axes)result[key][axis]=row[key][axis];
    }
    return result;
}
function release(scene){if(scene&&scene.activeInHierarchy)scene._activate(false);}
function state(action,node){const ui=node.getComponent(cc.UITransform),label=node.getComponent(cc.Label);return {action,size:[ui.width,ui.height],position:[node.position.x,node.position.y],fontSize:label?label.actualFontSize:0,children:node.children.map((n,index)=>{const u=n.getComponent(cc.UITransform);return {index,active:n.active,size:[u.width,u.height],position:[n.position.x,n.position.y],scale:[n.scale.x,n.scale.y]};})};}
function probeRoot(plan,design,spec){
    const source=new Map(plan.nodes.map(n=>[n.sourceId,n]));
    let owner=source.get(spec.node);if(!owner)throw Error('Native UI probe node missing');
    const ancestors=new Set();
    while(owner.parent!==null){
        if(ancestors.has(owner.sourceId))throw Error('Native UI probe parent cycle');
        ancestors.add(owner.sourceId);owner=source.get(owner.parent);
        if(!owner)throw Error('Native UI probe parent missing');
    }
    const included=new Set();
    function collect(sid){if(included.has(sid))throw Error('Native UI probe hierarchy repeats');included.add(sid);source.get(sid).children.forEach(collect);}
    collect(owner.sourceId);
    // Keep the entire source tree, including siblings used by Layout. External
    // node references must not silently point back into the saved scene.
    for(const c of plan.components)if(c.convertible&&included.has(c.node)){
        const reference=c.type==='cc.Widget'?c.target:c.type==='cc.ScrollView'?c.content:null;
        if(reference&&!included.has(reference))throw Error('Native UI probe crosses source roots: '+c.sourceId);
    }
    const roots=plan.nodes.filter(n=>n.parent===null),index=roots.indexOf(owner),original=design.children[index];
    if(!original||original.name!==owner.name)throw Error('Native UI probe root differs');
    const root=new cc.Node('OwnedDynamicUiContext'),ui=root.addComponent(cc.UITransform),designUi=design.getComponent(cc.UITransform);
    ownedUndo.registerRoot(root);
    root.layer=design.layer;root.setPosition(design.position);root.setRotation(design.rotation);root.setScale(design.scale);
    ui.setContentSize(designUi.width,designUi.height);ui.setAnchorPoint(designUi.anchorX,designUi.anchorY);
    const nodes=new Map();
    try{
        const branch=cc.instantiate(original);ownedUndo.registerRoot(branch);branch.parent=root;
        const sourceChildren=require('./static-richtext.js').sourceChildren;
        function walk(sid,n){const src=source.get(sid),children=n&&sourceChildren(n);if(!n||src.name!==n.name||src.children.length!==children.length)throw Error('Native UI probe hierarchy differs:'+sid+':'+JSON.stringify({expected:src.children,actual:children&&children.map(child=>child.name)}));nodes.set(sid,n);src.children.forEach((child,i)=>walk(child,children[i]));}
        walk(owner.sourceId,branch);return {root,nodes};
    }catch(error){root.destroy();throw error;}
}
async function probe(plan,design,onProgress=()=>{}){
    if(!enabled(plan))return [];
    const selected=new Map();for(const c of plan.components)if(c.convertible&&c.enabled&&((c.type==='cc.Label'&&c.text)||c.type==='cc.Widget'||c.type==='cc.Layout'&&[1,2].includes(c.layoutType)&&c.resize===1)){
        const key=c.type==='cc.Label'?c.type+'/'+c.overflow:c.type;if(!selected.has(key))selected.set(key,c);
    }
    const result=[],specs=plan.uiStateProbeVersion>=2?(plan.uiProbeSources||[]).map(sid=>plan.components.find(c=>c.sourceId===sid)):[...selected.values()].slice(0,6);
    for(const spec of specs){
        onProgress(result.length,specs.length);await new Promise(resolve=>setTimeout(resolve,0));
        if(plan.nativeDeadlineMs&&Date.now()>=plan.nativeDeadlineMs)throw Error('NATIVE_BUDGET_EXHAUSTED');
        if(!spec)throw Error('Native UI probe component missing');
        const {root,nodes}=probeRoot(plan,design,spec),scene=new cc.Scene('OwnedDynamicUiProbe');root.parent=scene;
        ownedUndo.registerRoot(scene);
        try{
            const node=nodes.get(spec.node);for(let p=node;p;p=p.parent)p.active=true;
            settle(scene,nodes,plan,root);const states=[state('baseline',node)],ui=node.getComponent(cc.UITransform);
            if(spec.type==='cc.Label'){
                const label=node.getComponent(cc.Label),original=label.string;label.string=spec.overflow===3?original+'\n'+original:original+original;
                settle(scene,nodes,plan,root);states.push(state('text-change',node));
                if(spec.overflow===0&&ui.width+.01<states[0].size[0]||spec.overflow===3&&ui.height+.01<states[0].size[1])throw Error('Native text sizing did not grow');
                node.active=false;label.string=original;node.active=true;settle(scene,nodes,plan,root);states.push(state('show-original-text',node));
                if(Math.abs(ui.width-states[0].size[0])>.01||Math.abs(ui.height-states[0].size[1])>.01)throw Error('Text hidden/restore geometry differs');
            }else if(spec.type==='cc.Widget'){
                const parent=node.parent&&node.parent.getComponent(cc.UITransform);if(!parent)continue;
                const size=[parent.width,parent.height];parent.setContentSize(size[0]+40,size[1]+20);settle(scene,nodes,plan,root);states.push(state('parent-resize',node));
                node.active=false;parent.width=size[0]+80;node.active=true;settle(scene,nodes,plan,root);states.push(state('show-after-resize',node));
            }else if(plan.uiStateProbeVersion>=2){
                const first=node.children.find(n=>n.active),firstUi=first&&first.getComponent(cc.UITransform);
                const child=new cc.Node('OwnedDynamicChild');ownedUndo.registerRoot(child);child.addComponent(cc.UITransform).setContentSize(firstUi?firstUi.width:40,firstUi?firstUi.height:20);if(first)child.setScale(first.scale);child.parent=node;
                settle(scene,nodes,plan,root);states.push(state('add-child',node));
                child.active=false;settle(scene,nodes,plan,root);states.push(state('hide-child',node));
                child.active=true;settle(scene,nodes,plan,root);states.push(state('show-child',node));
                child.parent=null;child.destroy();settle(scene,nodes,plan,root);states.push(state('remove-child',node));
                ui.setContentSize(ui.width+60,ui.height+30);settle(scene,nodes,plan,root);states.push(state('container-resize',node));
                if(first)first.setScale(first.scale.x*1.25,first.scale.y*.75,first.scale.z);
                settle(scene,nodes,plan,root);states.push(state('scale-child',node));
                if(firstUi)firstUi.setContentSize(firstUi.width+12,firstUi.height+8);
                settle(scene,nodes,plan,root);states.push(state('resize-child',node));
                node.active=false;node.active=true;settle(scene,nodes,plan,root);states.push(state('hide-show-container',node));
            }else{
                const child=new cc.Node('OwnedDynamicChild');ownedUndo.registerRoot(child);child.addComponent(cc.UITransform).setContentSize(40,20);child.parent=node;
                settle(scene,nodes,plan,root);states.push(state('add-child',node));const axis=spec.layoutType-1;
                const extent=states[0].size[axis]+(axis===0?40:20)+spec.spacingXY[axis];
                if(Math.abs(states[1].size[axis]-extent)>.01)throw Error('Dynamic child layout extent differs');
                child.active=false;settle(scene,nodes,plan,root);states.push(state('hide-child',node));
                child.active=true;settle(scene,nodes,plan,root);states.push(state('show-child',node));
                child.parent=null;child.destroy();settle(scene,nodes,plan,root);states.push(state('remove-child',node));
                if(Math.abs(states[states.length-1].size[axis]-states[0].size[axis])>.01)throw Error('Dynamic child removal did not restore extent');
            }
            result.push({sourceId:spec.sourceId,type:spec.type,status:'native-state-changes-passed',scopeSourceId:nodes.keys().next().value,scopeNodeCount:nodes.size,states});
        }finally{release(scene);scene.destroy();}
    }
    return result;
}
module.exports={enabled,capture,drivenFields,settle,settleRoot,expected,release,probeRoot,probe,alignWidgets};
