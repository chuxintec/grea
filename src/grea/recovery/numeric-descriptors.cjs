'use strict';
// Static descriptor facts only. No helper, constructor or source function runs.
module.exports=function descriptors(ast,range,hashBytes) {
 const property=n=>n?.type==='MemberExpression'&&!n.computed&&n.property.type==='Identifier'?n.property.name:null;
 const key=p=>p?.type==='Property'&&!p.computed?(p.key.type==='Identifier'?p.key.name:p.key.type==='Literal'?p.key.value:null):null;
 const get=(o,name)=>o?.type==='ObjectExpression'?o.properties.filter(p=>key(p)===name):[];
 const one=(o,name)=>{const p=get(o,name);return p.length===1?p[0].value:null;};
 const exprs=n=>n?.type==='SequenceExpression'?n.expressions.flatMap(exprs):n?[n]:[];
 const root=ast.type==='FunctionExpression'?ast:ast.type==='Program'&&ast.body.length===1&&ast.body[0].type==='ExpressionStatement'&&ast.body[0].expression.type==='FunctionExpression'?ast.body[0].expression:null;
 const imports=[],classes=[],methods=[],registrations=[];
 if(!root||root.params.length!==1||root.params[0].type!=='Identifier')return {imports,classes,methods,registrations};
 const exportAlias=root.params[0].name;
 const returns=root.body.body.filter(s=>s.type==='ReturnStatement');
 if(returns.length!==1)return {imports,classes,methods,registrations};
 const object=returns[0].argument,setters=one(object,'setters'),execute=one(object,'execute');
 if(!setters||setters.type!=='ArrayExpression'||!execute||execute.type!=='FunctionExpression'||execute.params.length||execute.async||execute.generator)return {imports,classes,methods,registrations};
 const setterScopes=new Map();
 setters.elements.forEach((fn,index)=>{
  if(fn?.type!=='FunctionExpression'||fn.id||fn.async||fn.generator||fn.params.length!==1||fn.params[0].type!=='Identifier')return;
  const input=fn.params[0].name;
  const discovered=[];
  for(const statement of fn.body.body){
   if(statement.type!=='ExpressionStatement')return;
   for(const e of exprs(statement.expression)){
    if(e.type!=='AssignmentExpression'||e.operator!=='='||e.left.type!=='Identifier'||property(e.right)===null||e.right.object.type!=='Identifier'||e.right.object.name!==input)return;
    discovered.push({local:e.left.name,imported:property(e.right),setterIndex:index,sourceBytes:range(e),setterBytes:range(fn)});
   }
  }
  imports.push(...discovered);setterScopes.set(fn,index);
 });
 // Bindings must be unique and may not be changed outside their literal setter.
 const invalid=new Set();
 function shadow(scope,name){
  if(scope.id?.name===name)return true;
  if(scope.params?.some(p=>p.type==='Identifier'&&p.name===name))return true;
  let found=false;const stack=[scope.body];
  while(stack.length){const n=stack.pop();if(!n)continue;
   if(n!==scope.body&&['FunctionExpression','ArrowFunctionExpression','FunctionDeclaration'].includes(n.type)){if(n.type==='FunctionDeclaration'&&n.id?.name===name)found=true;continue;}
   if(n.type==='VariableDeclarator'&&n.id.type==='Identifier'&&n.id.name===name)found=true;
   for(const v of Object.values(n))if(Array.isArray(v)){for(const x of v)if(x&&typeof x.type==='string')stack.push(x);}else if(v&&typeof v.type==='string')stack.push(v);
  }return found;
 }
 const nodes=[],stack=[[root,[]]];let count=0;
 while(stack.length){const [n,parents]=stack.pop();if(++count>1000000||parents.length>256)throw Error('Descriptor AST budget');nodes.push([n,parents]);
  const assigned=n.type==='AssignmentExpression'?n.left:n.type==='UpdateExpression'?n.argument:null;
  if(assigned?.type==='Identifier'){
   const name=assigned.name,bound=imports.filter(i=>i.local===name),scope=[...parents].reverse().find(p=>['FunctionExpression','FunctionDeclaration','ArrowFunctionExpression'].includes(p.type));
   if(bound.length&&scope!==root&&!shadow(scope,name)&&!bound.some(i=>JSON.stringify(i.sourceBytes)===JSON.stringify(range(n))))invalid.add(name);
   if(bound.length&&scope===root)invalid.add(name);
  }
  for(const v of Object.values(n))if(Array.isArray(v)){for(const x of v)if(x&&typeof x.type==='string')stack.push([x,[...parents,n]]);}else if(v&&typeof v.type==='string')stack.push([v,[...parents,n]]);
 }
 const lexicalClear=(parents,name)=>!parents.some(p=>p!==root&&['FunctionExpression','FunctionDeclaration','ArrowFunctionExpression'].includes(p.type)&&shadow(p,name));
 const parentsByNode=new Map(nodes);
 const binding=(name,member)=>{const values=imports.filter(i=>i.local===name&&i.imported===member);return name!==exportAlias&&name!=='Math'&&values.length===1&&!invalid.has(name)&&imports.filter(i=>i.local===name).length===1?values[0]:null;};
 function numeric(n,params,depth=0){
  if(!n||depth>32)return null;
  if(n.type==='Literal'&&typeof n.value==='number'&&Number.isFinite(n.value))return {kind:'literal',value:n.value};
  if(n.type==='Identifier'&&params.includes(n.name))return {kind:'parameter',name:n.name};
  if(property(n)==='PI'&&n.object.type==='Identifier'&&n.object.name==='Math'&&!params.includes('Math'))return {kind:'math-pi'};
  if(n.type==='UnaryExpression'&&['+','-'].includes(n.operator)){const operand=numeric(n.argument,params,depth+1);return operand?{kind:'unary',operator:n.operator,operand}:null;}
  if(n.type==='BinaryExpression'&&['+','-','*','/'].includes(n.operator)){const left=numeric(n.left,params,depth+1),right=numeric(n.right,params,depth+1);return left&&right?{kind:'binary',operator:n.operator,left,right}:null;}
  return null;
 }
 for(const [n,parents]of nodes){
  if(n.type!=='CallExpression')continue;
  if(property(n.callee)==='push'&&property(n.callee.object)==='_RF'&&n.callee.object.object.type==='Identifier'){
   const imported=binding(n.callee.object.object.name,'cclegacy');
   if(imported&&lexicalClear(parents,n.callee.object.object.name)&&n.arguments.length===4&&n.arguments[1].type==='Literal'&&typeof n.arguments[1].value==='string'&&n.arguments[2].type==='Literal'&&typeof n.arguments[2].value==='string')registrations.push({identity:n.arguments[1].value,name:n.arguments[2].value,sourceBytes:range(n),importBinding:imported,declarationKind:'creator3-cclegacy-import-candidate'});
  }
  if(n.callee.type!=='Identifier'||n.arguments.length!==3||n.arguments[0].type!=='Identifier')continue;
  const imported=binding(n.callee.name,'createClass');if(!imported)continue;
  const owner=n.arguments[0].name,scope=[...parents].reverse().find(p=>p.type==='FunctionExpression');
  if(!scope||scope===root||!lexicalClear(parents,n.callee.name)||!lexicalClear(parents,'Math'))continue;
  const ctor=scope.body.body.filter(s=>s.type==='FunctionDeclaration'&&s.id.name===owner);if(ctor.length!==1)continue;
  const invoked=parents.find(p=>p.type==='CallExpression'&&p.callee===scope&&p.arguments.length===0);if(!invoked)continue;
  const exported=parents.filter(p=>p.type==='CallExpression'&&p.callee.type==='Identifier'&&p.callee.name===exportAlias&&p.arguments.length===2&&p.arguments[0].type==='Literal'&&typeof p.arguments[0].value==='string'&&p.arguments[1]===invoked);
  if(exported.length!==1||!lexicalClear(parentsByNode.get(exported[0])||[],exportAlias))continue;
  const statements=scope.body.body;
  if(statements.length!==2||statements[0]!==ctor[0]||statements[1].type!=='ReturnStatement')continue;
  const returned=exprs(statements[1].argument);
  if(returned.length!==2||returned[0]!==n||returned[1].type!=='Identifier'||returned[1].name!==owner)continue;
  const rootShape=!root.async&&!root.generator&&!shadow(root,'Math')&&object.properties.length===2&&object.properties.every(p=>p.type==='Property'&&p.kind==='init'&&!p.computed&&['setters','execute'].includes(key(p)))&&root.body.body.every(s=>s.type==='ReturnStatement'||s.type==='VariableDeclaration'&&s.declarations.every(d=>d.id.type==='Identifier'&&d.init===null));
  const execution=execute.body.body.every(s=>s.type==='ExpressionStatement')?execute.body.body.flatMap(s=>exprs(s.expression)):[];
  const first=execution[0],last=execution[2];
  const legacyAlias=first?.callee?.object?.object;
  const literalModuleShape=rootShape&&execution.length===3&&execution[1]===exported[0]&&property(first.callee)==='push'&&property(first.callee.object)==='_RF'&&first.arguments.length===4&&first.arguments[0].type==='ObjectExpression'&&first.arguments[0].properties.length===0&&first.arguments[3].type==='UnaryExpression'&&first.arguments[3].operator==='void'&&first.arguments[3].argument.type==='Literal'&&first.arguments[3].argument.value===0&&legacyAlias?.type==='Identifier'&&binding(legacyAlias.name,'cclegacy')&&property(last.callee)==='pop'&&property(last.callee.object)==='_RF'&&last.callee.object.object.type==='Identifier'&&last.callee.object.object.name===legacyAlias.name&&last.arguments.length===0;
  const descriptorTablesSafe=n.arguments.slice(1).every(table=>table.type==='Literal'&&table.value===null||table.type==='ArrayExpression'&&table.elements.every(d=>{
   if(d?.type!=='ObjectExpression')return false;
   const keys=d.properties.map(key);
   return keys.includes('key')&&new Set(keys).size===keys.length&&!(keys.includes('value')&&(keys.includes('get')||keys.includes('set')))&&d.properties.every(p=>p.type==='Property'&&p.kind==='init'&&!p.computed&&['key','value','get','set'].includes(key(p))&&(key(p)==='key'?p.value.type==='Literal'&&typeof p.value.value==='string':p.value.type==='FunctionExpression'&&!p.value.id));
  }));
  const cls={literalModuleShape:!!literalModuleShape,descriptorTablesSafe,declarationKind:'babel-createClass-import-candidate',scopeBytes:range(scope),sourceBytes:range(n),exportedName:exported[0].arguments[0].value,exportBindingBytes:range(exported[0]),constructorAlias:owner,importBinding:imported};
  classes.push(cls);
  for(let table=1;table<=2;table++){
   const list=n.arguments[table];if(list.type==='Literal'&&list.value===null)continue;if(list.type!=='ArrayExpression')continue;
   for(const descriptor of list.elements){
    if(!descriptor||descriptor.type!=='ObjectExpression')continue;
    const methodName=one(descriptor,'key');if(methodName?.type!=='Literal'||typeof methodName.value!=='string')continue;
    for(const accessor of ['value','get','set']){
     const fn=one(descriptor,accessor);if(fn?.type!=='FunctionExpression')continue;
     const parameters=fn.params.map(p=>p.type==='Identifier'?{name:p.name,sourceType:'unknown'}:{name:null,sourceType:'unsupported-binding',sourceBytes:range(p)});
     const params=parameters.map(p=>p.name);const body=fn.body.body;
     const expression=descriptor.properties.length===2&&descriptor.properties.every(p=>p.kind==='init'&&!p.computed)&&table===2&&accessor==='value'&&!fn.async&&!fn.generator&&params.every(Boolean)&&new Set(params).size===params.length&&body.length===1&&body[0].type==='ReturnStatement'?numeric(body[0].argument,params):null;
     methods.push({name:methodName.value,static:table===2,accessor,declarationKind:cls.declarationKind,ownerAlias:owner,scopeBytes:range(scope),sourceBytes:range(descriptor),sourceSha256:hashBytes(descriptor),parameters,
       semantic:expression?{kind:'pure-number-expression-candidate',expression}:{kind:'unsupported',reason:'Descriptor retained; helper binding, types or body semantics require recovery'}});
    }
   }
  }
 }
 return {imports,classes,methods,registrations};
};
