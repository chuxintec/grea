'use strict';
// Static lexical identity only. Never invoke a factory, import, getter or source program.
const fs=require('node:fs'),crypto=require('node:crypto'),acorn=require('./sources/acorn.cjs');
const raw=fs.readFileSync(0);
if(raw.length>32*1024*1024)throw Error('CODE_SOURCE_BYTE_BUDGET');
const source=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw);
const ast=acorn.parse(source,{ecmaVersion:2020,sourceType:'script',allowReturnOutsideFunction:true});
const offsets=require('./sources/source-offsets.cjs')(source),hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const range=n=>({start:offsets[n.start],end:offsets[n.end]}),digest=n=>hash(raw.subarray(offsets[n.start],offsets[n.end]));
const property=n=>n?.type==='MemberExpression'?(!n.computed&&n.property.type==='Identifier'?n.property.name:n.property.type==='Literal'&&typeof n.property.value==='string'?n.property.value:null):null;
const key=n=>n?.type==='Identifier'?n.name:n?.type==='Literal'&&typeof n.value==='string'?n.value:null;
const isFunction=n=>['FunctionExpression','FunctionDeclaration','ArrowFunctionExpression'].includes(n?.type);
const parent=new WeakMap(),ownerScope=new WeakMap(),scopes=[],bindings=[],functions=[],methods=[],classes=[],mutations=[],registrations=[];
const newScope=(node,outer,kind)=>{const s={id:scopes.length,parent:outer?.id??null,kind,sourceBytes:range(node),names:new Map()};scopes.push(s);return s;};
const root=newScope(ast,null,'program'),stack=[[ast,null,root,0]];let nodes=0;
const declare=(scope,id,node,kind)=>{
 if(!id)return null;
 if(id.type!=='Identifier')return null;
 let s=scope;if(kind==='var')while(s.kind!=='function'&&s.parent!==null)s=scopes[s.parent];
 const b={id:'binding@'+offsets[id.start],name:id.name,scope:s.id,kind,sourceBytes:range(node),identifierBytes:range(id),declarationSha256:digest(node)};
 bindings.push(b);const values=s.names.get(id.name)||[];values.push(b);s.names.set(id.name,values);return b;
};
while(stack.length){
 const[n,p,s,depth]=stack.pop();if(++nodes>3000000||depth>512)throw Error('CODE_AST_BUDGET');
 if(p)parent.set(n,p);let local=s;
 if(n.type==='FunctionDeclaration')declare(s,n.id,n,'function');
 if(isFunction(n)){
  local=newScope(n,s,'function');functions.push(n);
  if(n.type==='FunctionExpression'&&n.id)declare(local,n.id,n,'function-self');
  for(const arg of n.params)declare(local,arg,arg,'parameter');
 }else if(n.type==='BlockStatement')local=newScope(n,s,'block');
 else if(n.type==='CatchClause'){local=newScope(n,s,'catch');declare(local,n.param,n.param,'catch');}
 ownerScope.set(n,local);
 if(n.type==='VariableDeclarator')declare(local,n.id,n,parent.get(p)?.kind||p?.kind||'var');
 if(n.type==='ClassDeclaration'&&n.id)declare(local,n.id,n,'class');
 for(const[k,v]of Object.entries(n)){
  if(k==='start'||k==='end')continue;
  if(Array.isArray(v)){for(let i=v.length-1;i>=0;i--)if(v[i]&&typeof v[i].type==='string')stack.push([v[i],n,local,depth+1]);}
  else if(v&&typeof v.type==='string')stack.push([v,n,local,depth+1]);
 }
}
const resolve=(name,scope)=>{
 let s=scope;
 while(s){const values=s.names.get(name);if(values){const ids=[...new Set(values.map(b=>b.id))];return ids.length===1?values[0]:{ambiguous:true,name,bindingIds:ids};}s=s.parent===null?null:scopes[s.parent];}
 return null;
};
const literalString=n=>n?.type==='Literal'&&typeof n.value==='string'?n.value:null;
const dataStack=[ast];
while(dataStack.length){
 const n=dataStack.pop();
 if((n.type==='AssignmentExpression'||n.type==='UpdateExpression')&&(n.left||n.argument)?.type==='Identifier'){
  const id=n.left||n.argument,b=resolve(id.name,ownerScope.get(n));mutations.push({name:id.name,bindingId:b?.id??null,sourceBytes:range(n),operator:n.operator});
 }
 if(n.type==='CallExpression'&&property(n.callee)==='push'&&property(n.callee.object)==='_RF'&&n.callee.object.object?.name==='cc'&&n.arguments.length===3){
  const identity=literalString(n.arguments[1]),name=literalString(n.arguments[2]);
  if(identity&&name)registrations.push({identity,name,scope:ownerScope.get(n).id,sourceBytes:range(n)});
 }
 for(const[k,v]of Object.entries(n)){if(k==='start'||k==='end')continue;if(Array.isArray(v)){for(const x of v)if(x&&typeof x.type==='string')dataStack.push(x);}else if(v&&typeof v.type==='string')dataStack.push(v);}
}
const factoryClass=new WeakMap();
for(const fn of functions){
 const call=parent.get(fn),declaration=call&&parent.get(call);
 if(fn.type!=='FunctionExpression'||call?.type!=='CallExpression'||call.callee!==fn||declaration?.type!=='VariableDeclarator'||declaration.id.type!=='Identifier')continue;
 const returns=fn.body.body.filter(n=>n.type==='ReturnStatement');if(returns.length!==1)continue;
 let last=returns[0].argument;if(last?.type==='SequenceExpression')last=last.expressions.at(-1);
 if(last?.type!=='Identifier')continue;
 const constructor=resolve(last.name,ownerScope.get(last));
 if(!constructor||constructor.ambiguous||constructor.kind!=='function')continue;
 const b=resolve(declaration.id.name,ownerScope.get(declaration));
 if(!b||b.ambiguous)continue;
 const c={id:'class@'+b.id,name:declaration.id.name,bindingId:b.id,constructorBindingId:constructor.id,constructorAlias:last.name,
   sourceBytes:range(fn),sourceSha256:digest(fn),enclosingScope:ownerScope.get(declaration).id,methods:[],methodBindings:[],inheritance:'unresolved-unless-explicitly-proven',
   constructorDeclarationBytes:constructor.sourceBytes,constructorDeclarationSha256:constructor.declarationSha256,
   bindingMutations:mutations.filter(m=>m.bindingId===b.id||m.bindingId===constructor.id)};
 classes.push(c);factoryClass.set(fn,c);
}
for(const c of classes){
 const names=registrations.filter(r=>r.scope===c.enclosingScope&&r.sourceBytes.end<=c.sourceBytes.start).sort((a,b)=>b.sourceBytes.end-a.sourceBytes.end);
 c.precedingRegistration=names[0]||null;
 // Merely a preceding syntax observation, never proof that a runtime class registered.
}
const enclosingClass=n=>{for(let p=n;p;p=parent.get(p)){const c=factoryClass.get(p);if(c)return c;}return null;};
const methodByFunction=new WeakMap();
for(const fn of functions){
 const assignment=parent.get(fn);if(assignment?.type!=='AssignmentExpression'||assignment.operator!=='='||assignment.right!==fn)continue;
 const left=assignment.left,name=property(left);if(!name)continue;
 const base=left.object;let receiver=null,stat=true;
 if(property(base)==='prototype'&&base.object.type==='Identifier'){receiver=base.object;stat=false;}
 else if(base.type==='Identifier')receiver=base;
 if(!receiver)continue;
 const binding=resolve(receiver.name,ownerScope.get(assignment)),c=enclosingClass(assignment);
 const belongs=c&&binding&&!binding.ambiguous&&binding.id===c.constructorBindingId;
 const row={id:'method@'+offsets[assignment.start],name,ownerAlias:receiver.name,ownerBindingId:binding?.id??null,
   classId:belongs?c.id:null,static:stat,sourceBytes:range(assignment),sourceSha256:digest(assignment),
   functionBytes:range(fn),bodySha256:digest(fn.body),parameters:fn.params.map(n=>({name:n.type==='Identifier'?n.name:null,binding:n.type})),
   async:!!fn.async,generator:!!fn.generator,calls:[],captures:[],writes:[],sourceExecuted:false};
 methods.push(row);methodByFunction.set(fn,row);if(belongs){c.methods.push(row.id);c.methodBindings.push({id:row.id,name,static:stat,sourceSha256:row.sourceSha256});}
}
const bodyFacts=(fn,row)=>{
 const todo=[fn.body],captures=new Map();let visited=0;
 while(todo.length){
  const n=todo.pop();if(++visited>300000){row.calls=[];row.captures=[];row.writes=[];row.factsCoverage='deferred-method-node-budget';return;}
  if(n.type==='CallExpression'){
   let text=null,b=null,member=null;
   if(n.callee.type==='Identifier'){text=n.callee.name;b=resolve(text,ownerScope.get(n));}
   else if(n.callee.type==='MemberExpression'){
    member=property(n.callee);const receiver=n.callee.object;
    text=receiver.type==='Identifier'?receiver.name:receiver.type==='ThisExpression'?'this':null;
    if(receiver.type==='Identifier')b=resolve(receiver.name,ownerScope.get(n));
   }
   row.calls.push({receiver:text,member,bindingId:b&&!b.ambiguous?b.id:null,ambiguous:!!b?.ambiguous,
     argumentCount:n.arguments.length,sourceBytes:range(n),computed:n.callee.type==='MemberExpression'&&!member});
  }
  if(n.type==='AssignmentExpression'&&n.left.type==='Identifier')row.writes.push({name:n.left.name,binding:resolve(n.left.name,ownerScope.get(n)),sourceBytes:range(n)});
  if(n.type==='Identifier'){
   const p=parent.get(n);const isKey=p&&((p.type==='MemberExpression'&&p.property===n&&!p.computed)||(['Property','MethodDefinition'].includes(p.type)&&p.key===n&&!p.computed&&!p.shorthand));
   const isDeclaration=p&&((p.type==='VariableDeclarator'&&p.id===n)||(isFunction(p)&&(p.id===n||p.params.includes(n))));
   if(!isKey&&!isDeclaration){
    const b=resolve(n.name,ownerScope.get(n));
    if(b&&!b.ambiguous&&(b.identifierBytes.start<row.functionBytes.start||b.identifierBytes.end>row.functionBytes.end))captures.set(b.id,{name:n.name,bindingId:b.id,declarationBytes:b.sourceBytes});
   }
  }
  for(const[k,v]of Object.entries(n)){
   if(k==='start'||k==='end')continue;
   if(Array.isArray(v)){for(const x of v)if(x&&typeof x.type==='string')todo.push(x);}
   else if(v&&typeof v.type==='string')todo.push(v);
  }
 }
 row.captures=[...captures.values()].sort((a,b)=>a.bindingId.localeCompare(b.bindingId));
};
for(const fn of functions){const row=methodByFunction.get(fn);if(row)bodyFacts(fn,row);}
const functionById=new Map(functions.filter(fn=>methodByFunction.has(fn)).map(fn=>[methodByFunction.get(fn).id,fn]));
const mode=process.argv[2]||'index';let selected=[];
if(mode==='draft-stream'){
 let total=0;const send=row=>{const line=JSON.stringify(row,(_,v)=>typeof v==='bigint'?{unsupportedBigInt:v.toString()}:v)+'\n';total+=Buffer.byteLength(line);if(total>1024*1024*1024)throw Error('CODE_DRAFT_STREAM_BUDGET');fs.writeSync(1,line);};
 const boundedNodes=(start,limit)=>{const todo=[start];let count=0;while(todo.length){const n=todo.pop();if(++count>limit)return count;for(const[k,v]of Object.entries(n)){if(k==='start'||k==='end')continue;if(Array.isArray(v)){for(const x of v)if(x&&typeof x.type==='string')todo.push(x);}else if(v&&typeof v.type==='string')todo.push(v);}}return count;};
 const functionIds=new WeakMap(),flattenedFunctions=new WeakSet();let flattened=0,containers=0;
 for(const fn of functions){
  functionIds.set(fn,methodByFunction.get(fn)?.id||'function@'+offsets[fn.start]);
  if(factoryClass.has(fn)){flattenedFunctions.add(fn);flattened++;}
  else if(!methodByFunction.has(fn)&&boundedNodes(fn,300000)>300000){flattenedFunctions.add(fn);containers++;}
 }
 const enclosingFunction=n=>{let fn=parent.get(n);while(fn&&!isFunction(fn))fn=parent.get(fn);return fn;};
 const emittedParent=n=>{let fn=enclosingFunction(n);while(fn&&flattenedFunctions.has(fn))fn=enclosingFunction(fn);return fn?functionIds.get(fn):null;};
 const thisOwner=n=>{
  let fn=enclosingFunction(n);while(fn?.type==='ArrowFunctionExpression')fn=enclosingFunction(fn);
  const m=fn&&methodByFunction.get(fn);
  if(m?.ownerBindingId)return {ownerBindingId:m.ownerBindingId,static:m.static,methodId:m.id};
  if(fn){const c=enclosingClass(fn),b=fn.id&&resolve(fn.id.name,ownerScope.get(fn));if(c&&b?.id===c.constructorBindingId)return{ownerBindingId:b.id,static:false,constructor:true};}
  return null;
 };
 const convert=n=>{
  if(Array.isArray(n))return n.map(convert);if(!n||typeof n!=='object')return n;
  const out={};for(const[k,v]of Object.entries(n))if(k==='start'||k==='end')out[k]=offsets[v];else out[k]=convert(v);
  if(n.type==='Identifier'){const b=resolve(n.name,ownerScope.get(n));out.bindingId=b&&!b.ambiguous?b.id:null;if(b?.ambiguous)out.bindingAmbiguous=true;}
  if(n.type==='ThisExpression'){const owner=thisOwner(n);if(owner){out.thisOwnerBindingId=owner.ownerBindingId;out.thisStatic=owner.static;}}
  if(isFunction(n))out.draftFunctionId=functionIds.get(n)||'function@'+offsets[n.start];
  return out;
 };
 const byClassBinding=new Map();for(const c of classes){byClassBinding.set(c.bindingId,c);byClassBinding.set(c.constructorBindingId,c);}
 const knownOwners=new Set(methods.map(m=>m.ownerBindingId).filter(Boolean));for(const k of byClassBinding.keys())knownOwners.add(k);
 const fieldContexts=new WeakMap();
 const fieldContext=n=>{const fn=enclosingFunction(n);if(!fn)return 'program';if(fieldContexts.has(fn))return fieldContexts.get(fn);const context=factoryClass.has(fn)?'class_factory':!methodByFunction.has(fn)&&flattenedFunctions.has(fn)?'module':'runtime_write';fieldContexts.set(fn,context);return context;};
 const fieldRows=[],fieldsTodo=[ast];
 while(fieldsTodo.length){
  const n=fieldsTodo.pop();
  if(n.type==='AssignmentExpression'&&n.operator==='='&&n.left.type==='MemberExpression'&&n.left.object.type==='Identifier'&&!isFunction(n.right)){
   const receiver=n.left.object,b=resolve(receiver.name,ownerScope.get(n)),name=property(n.left);
   if(b&&!b.ambiguous&&knownOwners.has(b.id)&&name&&name!=='prototype'){
    const c=byClassBinding.get(b.id);const field={id:'field@'+offsets[n.start],name,ownerAlias:receiver.name,ownerBindingId:b.id,classId:c?.id??null,static:true,initializationContext:fieldContext(n),sourceBytes:range(n),sourceSha256:digest(n)};
    fieldRows.push({field,node:n.right});
   }
  }
  for(const[k,v]of Object.entries(n)){if(k==='start'||k==='end')continue;if(Array.isArray(v)){for(const x of v)if(x&&typeof x.type==='string')fieldsTodo.push(x);}else if(v&&typeof v.type==='string')fieldsTodo.push(v);}
 }
 const functionRows=[];
 for(const fn of functions){
  if(flattenedFunctions.has(fn))continue;
  const existing=methodByFunction.get(fn),c=enclosingClass(fn);
  const method=existing?{...existing}:{id:functionIds.get(fn),name:fn.id?.name||'Function'+offsets[fn.start],classId:c?.id??null,
    ownerAlias:c?.constructorAlias??null,ownerBindingId:null,static:false,sourceBytes:range(fn),functionBytes:range(fn),sourceSha256:digest(fn),bodySha256:digest(fn.body),parameters:fn.params.map(n=>({name:n.type==='Identifier'?n.name:null,binding:n.type})),async:!!fn.async,generator:!!fn.generator,calls:[],captures:[],writes:[]};
  method.parentFunctionId=emittedParent(fn);method.lexicalParentFunctionId=enclosingFunction(fn)?functionIds.get(enclosingFunction(fn)):null;
  if(!existing)bodyFacts(fn,method);
  functionRows.push({fn,method,kind:existing?'indexed_method':'auxiliary_function'});
 }
 const metadataKeys=['id','name','classId','ownerAlias','ownerBindingId','static','sourceBytes','sourceSha256','functionBytes','parentFunctionId','lexicalParentFunctionId'];
 send({record:'header',schemaVersion:1,source:{sha256:hash(raw),bytes:raw.length},sourceExecuted:false,
  summary:{astNodes:nodes,classes:classes.length,methods:methods.length,functions:functions.length},classes,registrations,
  draftDeclarations:functionRows.map(({method,kind})=>({...Object.fromEntries(metadataKeys.map(k=>[k,method[k]])),kind})),
  draftFields:fieldRows.map(r=>r.field),draftMutatedBindings:[...new Set(mutations.map(m=>m.bindingId).filter(Boolean))]});
 for(const{field,node}of fieldRows){const value=boundedNodes(node,100000)>100000?{type:'UnsupportedDraftFragment',start:offsets[node.start],end:offsets[node.end],reason:'Large field initializer retained for repair'}:convert(node);send({record:'field',field,ast:value});}
 for(const{fn,method,kind}of functionRows){
  let astRow;
  if(kind==='indexed_method'&&boundedNodes(fn,300000)>300000){
   astRow={type:fn.type,start:offsets[fn.start],end:offsets[fn.end],draftFunctionId:method.id,params:convert(fn.params),body:{type:'BlockStatement',start:offsets[fn.body.start],end:offsets[fn.body.end],body:fn.body.body.map(n=>boundedNodes(n,100000)>100000?{type:'UnsupportedDraftFragment',start:offsets[n.start],end:offsets[n.end],reason:'Large source fragment retained locally; other statements continue'}:convert(n))}};
  }else astRow=convert(fn);
  let record={record:'function',kind,method,ast:astRow};
  if(Buffer.byteLength(JSON.stringify(record))>64*1024*1024)record={record:'function',kind,method,ast:null,diagnostic:'AST fragment exceeds64MiB; exact source is retained for local transcription'};
  send(record);
 }
 send({record:'footer',functionsEmitted:functionRows.length,classFactoriesFlattened:flattened,moduleContainersFlattened:containers,staticFields:fieldRows.length,indexedMethods:methods.length,sourceExecuted:false});process.exit(0);
}

if(mode==='methods'){
 const request=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
 if(!Array.isArray(request)||request.length>256||new Set(request).size!==request.length)throw Error('CODE_METHOD_SELECTION');
 selected=request.map(id=>{const method=methods.find(m=>m.id===id),fn=functionById.get(id);if(!method||!fn)throw Error('CODE_METHOD_NOT_FOUND');return{method,ast:fn};});
}
if(mode==='methods'){
 const convert=n=>{
  if(Array.isArray(n))return n.map(convert);
  if(!n||typeof n!=='object')return n;
  const out={};for(const[k,v]of Object.entries(n))if(k==='start'||k==='end')out[k]=offsets[v];else out[k]=convert(v);
  if(n.type==='Identifier'){
   const b=resolve(n.name,ownerScope.get(n));out.bindingId=b&&!b.ambiguous?b.id:null;
   if(b?.ambiguous)out.bindingAmbiguous=true;
  }
  return out;
 };
 selected=selected.map(row=>({method:row.method,ast:convert(row.ast)}));
}
const selectedIds=new Set(selected.map(r=>r.method.id));
const selectedRanges=selected.map(r=>r.method.functionBytes),selectedCaptures=new Set(selected.flatMap(r=>r.method.captures.map(c=>c.bindingId)));
const exportBindings=mode==='methods'?bindings.filter(b=>selectedCaptures.has(b.id)||selectedRanges.some(r=>r.start<=b.identifierBytes.start&&b.identifierBytes.end<=r.end)):bindings;
const report={schemaVersion:1,kind:'javascript-code-graph-v1',source:{sha256:hash(raw),bytes:raw.length},sourceExecuted:false,astOffsets:'utf8-bytes',
 summary:{astNodes:nodes,scopes:scopes.length,bindings:bindings.length,classes:classes.length,methods:methods.length,functions:functions.length},
 scopes:mode==='methods'?[]:scopes.map(({names,...s})=>s),bindings:exportBindings,classes,methods:mode==='methods'?methods.filter(m=>selectedIds.has(m.id)):methods,selected,mutations,registrations,
 methodInventory:mode==='methods'?methods.map(m=>({id:m.id,name:m.name,classId:m.classId,static:m.static,sourceBytes:m.sourceBytes,sourceSha256:m.sourceSha256,parameterCount:m.parameters.length})):undefined,
 limitations:['Lexical binding is not proof of initialization/order, runtime type or method behavior.','Dynamic property names and ambiguous/mutated bindings require a typed semantic contract.','Only constructor-returning literal IIFE classes are grouped here; other methods remain ungrouped evidence.']};
process.stdout.write(JSON.stringify(report,(_,v)=>typeof v==='bigint'?{unsupportedBigInt:v.toString()}:v));
