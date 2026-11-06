'use strict';
// Static literal assignment evidence. No source imports, evaluation or factory calls.
const fs=require('node:fs'),crypto=require('node:crypto'),acorn=require('./acorn.cjs');
const {TextDecoder}=require('node:util');
if(acorn.version!=='8.15.0')throw Error('Pinned Acorn required');
const raw=fs.readFileSync(0);if(raw.length>32*1024*1024)throw Error('Source budget');
const source=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw);
const ast=acorn.parse(source,{ecmaVersion:2020,sourceType:'script'}),stack=[[ast,0]],facts=[],settings=[];
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');let count=0;
let literalValues=0;
function literal(node,depth=0){
 if(++literalValues>1000000||depth>96)throw Error('Settings value budget');
 if(node.type==='Literal'&&(node.value===null||['string','number','boolean'].includes(typeof node.value))){if(typeof node.value==='number'&&!Number.isFinite(node.value))throw Error('Number');return node.value;}
 if(node.type==='ArrayExpression'){if(node.elements.some(x=>!x))throw Error('Array holes');return node.elements.map(x=>literal(x,depth+1));}
 if(node.type==='ObjectExpression'){
  const result=Object.create(null),seen=new Set();
  for(const p of node.properties){if(p.type!=='Property'||p.kind!=='init'||p.method||p.computed||p.shorthand)throw Error('Nonliteral property');
   const key=p.key.type==='Identifier'?p.key.name:p.key.value;if(!['string','number'].includes(typeof key)||seen.has(String(key)))throw Error('Duplicate property');seen.add(String(key));result[key]=literal(p.value,depth+1);}
  return result;
 }
 if(node.type==='UnaryExpression'&&['!','-','+'].includes(node.operator)&&node.argument.type==='Literal'&&typeof node.argument.value==='number'){
  const v=node.argument.value;if(!Number.isFinite(v))throw Error('Number');return node.operator==='!'?!v:node.operator==='-'?-v:v;
 }
 throw Error('Nonliteral settings value');
}
while(stack.length){
 const [node,depth]=stack.pop();if(++count>3000000||depth>512)throw Error('AST budget');
 if(node.type==='AssignmentExpression'&&node.operator==='='&&node.left.type==='MemberExpression'&&node.left.object.type==='Identifier'&&node.left.object.name==='cc'){
  const member=node.left.computed?(node.left.property.type==='Literal'?node.left.property.value:null):node.left.property.name;
  if(member==='ENGINE_VERSION'&&node.right.type==='Literal'&&typeof node.right.value==='string'&&/^\d+\.\d+\.\d+$/.test(node.right.value)){
   const start=Buffer.byteLength(source.slice(0,node.start)),end=Buffer.byteLength(source.slice(0,node.end));
   facts.push({version:node.right.value,sourceBytes:{start,end},sha256:hash(raw.subarray(start,end)),confidence:'literal-assignment-not-runtime'});
   if(facts.length>16)throw Error('Version evidence budget');
  }
 }
 if(process.argv[2]==='--settings'&&node.type==='AssignmentExpression'&&node.operator==='='&&node.left.type==='MemberExpression'&&!node.left.computed&&node.left.object.type==='Identifier'&&node.left.object.name==='window'&&node.left.property.name==='_CCSettings'&&node.right.type==='ObjectExpression'){
  const start=Buffer.byteLength(source.slice(0,node.start)),end=Buffer.byteLength(source.slice(0,node.end));
  settings.push({data:literal(node.right),sourceBytes:{start,end},sha256:hash(raw.subarray(start,end))});if(settings.length>1)throw Error('Ambiguous settings assignment');
 }
 for(const value of Object.values(node))if(Array.isArray(value)){for(const child of value)if(child&&typeof child.type==='string')stack.push([child,depth+1]);}else if(value&&typeof value.type==='string')stack.push([value,depth+1]);
}
process.stdout.write(JSON.stringify({schemaVersion:1,source:{sha256:hash(raw),bytes:raw.length},facts,settings,sourceCodeExecuted:false}));
