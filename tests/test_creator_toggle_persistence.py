import subprocess,shutil,unittest
from pathlib import Path
class CreatorTogglePersistenceTests(unittest.TestCase):
 def test_false_checked_state_survives_native_backing_field_roundtrip(self):
  node=shutil.which('node')
  if not node:self.skipTest('Node unavailable')
  js=r'''
const Module=require('module'),original=Module._load;
class Color{constructor(r,g,b,a){Object.assign(this,{r,g,b,a})}}
class Node{constructor(){this.components=[]}getComponent(T){return this.components.find(c=>c instanceof T)||null}addComponent(T){const c=new T();c.node=this;this.components.push(c);return c}}
class Toggle{constructor(){this.enabled=true;this._isChecked=true;this.interactable=true;this.normalColor=new Color(255,255,255,255);this.checkMark=null;this.target=null;this.transition=0}get isChecked(){return this._isChecked}setIsCheckedWithoutNotify(v){this._isChecked=v}}
class ToggleContainer{} class Sprite{}
Module._load=function(r){if(r==='cc')return {Node,Toggle,ToggleContainer,Sprite,Color};return original.apply(this,arguments)};
const api=require(process.argv[1]),n=new Node(),spec={bindings:[{sourceId:'toggle',kind:'cc.Toggle',nodeSourceId:'node',checkedPresent:true,checkedValue:false,interactablePresent:true,interactableValue:true,targetPresent:true,targetSourceId:'node',checkMarkPresent:true,checkMarkSourceId:null,gaps:[]}]};
const gaps=api.Create(spec,id=>id==='node'?n:null,()=>null);if(gaps.length)throw Error(gaps.join(','));
const t=n.getComponent(Toggle),saved=JSON.parse(JSON.stringify({_isChecked:t._isChecked,enabled:t.enabled,interactable:t.interactable}));
const reloaded=new Toggle();Object.assign(reloaded,saved);reloaded.node=n;reloaded.target=n;n.components=[reloaded];
const result=api.Read(spec,id=>id==='node'?n:null,()=>null);if(!result.fields[0].verified||reloaded.isChecked!==false)throw Error('false state not persisted');
'''
  r=subprocess.run([node,'-e',js,str(Path('src/monkey/targets/CreatorStaticToggle.js').resolve())],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr)

 def test_inherited_zoom_scale_survives_native_component_roundtrip_while_disabled(self):
  node=shutil.which('node')
  if not node:self.skipTest('Node unavailable')
  js=r'''
const Module=require('module'),original=Module._load;
class Color{constructor(r,g,b,a){Object.assign(this,{r,g,b,a})}}
class Node{constructor(){this.components=[]}getComponent(T){return this.components.find(c=>c instanceof T)||null}addComponent(T){const c=new T();c.node=this;this.components.push(c);return c}}
class Toggle{constructor(){this.enabled=true;this._isChecked=true;this.interactable=true;this.normalColor=new Color(255,255,255,255);this.checkMark=null;this.target=null;this.transition=0;this.zoomScale=1.2}get isChecked(){return this._isChecked}setIsCheckedWithoutNotify(v){this._isChecked=v}}
class ToggleContainer{} class Sprite{}
Module._load=function(r){if(r==='cc')return {Node,Toggle,ToggleContainer,Sprite,Color};return original.apply(this,arguments)};
const api=require(process.argv[1]),n=new Node(),spec={bindings:[{sourceId:'toggle',kind:'cc.Toggle',nodeSourceId:'node',checkedPresent:true,checkedValue:false,interactablePresent:true,interactableValue:true,targetPresent:true,targetSourceId:'node',checkMarkPresent:true,checkMarkSourceId:null,zoomScalePresent:true,zoomScaleValue:.9,gaps:[]}]};
const gaps=api.Create(spec,id=>id==='node'?n:null,()=>null);if(gaps.length)throw Error(gaps.join(','));
const t=n.getComponent(Toggle);if(t.enabled||t.zoomScale!==.9)throw Error('source zoomScale missing or Toggle still enabled');
const saved=JSON.parse(JSON.stringify({_isChecked:t._isChecked,enabled:t.enabled,interactable:t.interactable,zoomScale:t.zoomScale}));
const reloaded=new Toggle();Object.assign(reloaded,saved);reloaded.node=n;reloaded.target=n;n.components=[reloaded];
const result=api.Read(spec,id=>id==='node'?n:null,()=>null);if(!result.fields[0].verified||reloaded.zoomScale!==.9||reloaded.enabled)throw Error('zoomScale did not persist/read back');
'''
  r=subprocess.run([node,'-e',js,str(Path('src/monkey/targets/CreatorStaticToggle.js').resolve())],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr)

 def test_group_component_is_created_before_toggle_even_when_spec_order_is_reversed(self):
  node=shutil.which('node')
  if not node:self.skipTest('Node unavailable')
  js=r'''
const Module=require('module'),original=Module._load;
class Color{constructor(r,g,b,a){Object.assign(this,{r,g,b,a})}}
class Node{constructor(parent=null){this.parent=parent;this.components=[]}getComponent(T){return this.components.find(c=>c instanceof T)||null}addComponent(T){const c=new T();c.node=this;this.components.push(c);return c}}
class Toggle{constructor(){this.enabled=true;this._isChecked=true;this.interactable=true;this.normalColor=new Color(255,255,255,255);this.checkMark=null;this.target=null;this.transition=0}get isChecked(){return this._isChecked}setIsCheckedWithoutNotify(v){this._isChecked=v}}
class ToggleContainer{constructor(){this.enabled=true;this.allowSwitchOff=false}} class Sprite{}
Module._load=function(r){if(r==='cc')return {Node,Toggle,ToggleContainer,Sprite,Color};return original.apply(this,arguments)};
const api=require(process.argv[1]),parent=new Node(),childA=new Node(parent),childB=new Node(parent),nodes=new Map([['parent',parent],['a',childA],['b',childB]]);
const spec={bindings:[
 {sourceId:'toggle-a',kind:'cc.Toggle',nodeSourceId:'a',groupSourceId:'group',groupNodeSourceId:'parent',checkedPresent:true,checkedValue:true,gaps:[]},
 {sourceId:'toggle-b',kind:'cc.Toggle',nodeSourceId:'b',groupSourceId:'group',groupNodeSourceId:'parent',checkedPresent:true,checkedValue:false,gaps:[]},
 {sourceId:'group',kind:'cc.ToggleContainer',nodeSourceId:'parent',allowSwitchOffPresent:true,allowSwitchOffValue:false,gaps:[]}
]};
const gaps=api.Create(spec,id=>nodes.get(id)||null,()=>null);if(gaps.length)throw Error(gaps.join(','));
const group=parent.getComponent(ToggleContainer);if(!group||group.enabled||group.allowSwitchOff)throw Error('source-backed group component missing or fields differ');
if(!childA.getComponent(Toggle)||!childB.getComponent(Toggle))throw Error('toggle components absent');
const read=api.Read(spec,id=>nodes.get(id)||null,()=>null);if(read.fields.some(x=>!x.verified))throw Error(JSON.stringify(read.fields));
const noGroupSpec={bindings:[{sourceId:'misbound',kind:'cc.Toggle',nodeSourceId:'a',groupSourceId:'missing-group',groupNodeSourceId:'parent',gaps:[]}]};
if(!api.Create(noGroupSpec,id=>nodes.get(id)||null,()=>null).some(x=>x.includes('toggle_group_source_mismatch')))throw Error('missing source group was silently accepted');
'''
  r=subprocess.run([node,'-e',js,str(Path('src/monkey/targets/CreatorStaticToggle.js').resolve())],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr)
