'use strict';
// Static AST facts and a deliberately narrow semantic subset; no input execution.
const fs=require('node:fs'),crypto=require('node:crypto'),acorn=require('./sources/acorn.cjs');
const raw=fs.readFileSync(0);if(raw.length>32*1024*1024)throw Error('Source budget');
const source=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw);
let ast;try{ast=acorn.parse(source,{ecmaVersion:2020,sourceType:'script',allowReturnOutsideFunction:true});}
catch(error){ast=acorn.parseExpressionAt(source,0,{ecmaVersion:2020});if(ast.type!=='FunctionExpression'||!['',';'].includes(source.slice(ast.end).trim()))throw error;}
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const positions=require('./sources/source-offsets.cjs')(source);
const range=n=>({start:positions[n.start],end:positions[n.end]});
const property=n=>n?.type==='MemberExpression'&&!n.computed&&n.property.type==='Identifier'?n.property.name:null;
const field=n=>n?.type==='MemberExpression'&&n.object.type==='ThisExpression'?property(n):null;
const methods=[],calls=[],classScopes=[],registrations=[],members=[],stack=[[ast,[],0]];let count=0;
while(stack.length){
 const [n,parents,depth]=stack.pop();if(++count>3000000||depth>512)throw Error('AST budget');
 if(n.type==='CallExpression'){
  const method=property(n.callee);if(method)calls.push({method,sourceBytes:range(n)});
  if(method==='push'&&property(n.callee.object)==='_RF'&&n.callee.object.object.type==='Identifier'&&n.callee.object.object.name==='cc'&&n.arguments.length===3&&n.arguments[1].type==='Literal'&&typeof n.arguments[1].value==='string'&&n.arguments[2].type==='Literal'&&typeof n.arguments[2].value==='string')registrations.push({identity:n.arguments[1].value,name:n.arguments[2].value,sourceBytes:range(n)});
  if(n.callee.type==='FunctionExpression'&&n.callee.params.length===1&&n.callee.params[0].type==='Identifier'&&n.arguments.length===1&&property(n.arguments[0])==='Label'&&n.arguments[0].object.type==='Identifier'&&n.arguments[0].object.name==='cc'){
   const aliases=n.callee.body.body.filter(x=>x.type==='FunctionDeclaration').map(x=>x.id.name),base=n.callee.params[0].name,helpers=[];
   const inspect=e=>{if(!e)return;if(e.type==='SequenceExpression'){e.expressions.forEach(inspect);return;}if(e.type==='CallExpression'&&e.callee.type==='Identifier'&&e.arguments.length===2&&e.arguments[0].type==='Identifier'&&aliases.includes(e.arguments[0].name)&&e.arguments[1].type==='Identifier'&&e.arguments[1].name===base)helpers.push({alias:e.callee.name,constructorAlias:e.arguments[0].name,baseAlias:base,sourceBytes:range(e)});};
   for(const statement of n.callee.body.body)if(statement.type==='ReturnStatement')inspect(statement.argument);else if(statement.type==='ExpressionStatement')inspect(statement.expression);
   if(helpers.length===1)classScopes.push({scopeBytes:range(n.callee),constructorAliases:[helpers[0].constructorAlias],baseArgument:'cc.Label',inheritanceHelper:'unresolved-source-helper',inheritanceCall:helpers[0],sourceBytes:range(n)});
  }
 }
 if(n.type==='AssignmentExpression'&&n.operator==='='&&property(n.left)&&['FunctionExpression','ArrowFunctionExpression'].includes(n.right.type)){
  const fn=n.right,pname=property(n.left),owner=n.left.object;
  const prototype=property(owner)==='prototype'&&owner.object.type==='Identifier';
  const alias=prototype?owner.object.name:owner.type==='Identifier'?owner.name:null;
  if(alias){
   const scope=[...parents].reverse().find(p=>['FunctionExpression','FunctionDeclaration','Program'].includes(p.type));
   const body=fn.body.type==='BlockStatement'?fn.body.body:[];
   let semantic={kind:'unsupported',reason:'Statement/type/evaluation semantics require recovery'};
   if(prototype&&fn.type==='FunctionExpression'&&!fn.async&&!fn.generator&&fn.params.length===0&&body.length===1&&body[0].type==='ReturnStatement'&&field(body[0].argument))semantic={kind:'read-instance-field',field:field(body[0].argument)};
   if(prototype&&fn.type==='FunctionExpression'&&!fn.async&&!fn.generator&&fn.params.length===1&&fn.params[0].type==='Identifier'&&body.length===1){
    const e=body[0].type==='ExpressionStatement'?body[0].expression:null;
    if(e?.type==='AssignmentExpression'&&e.operator==='='&&field(e.left)&&e.right.type==='Identifier'&&e.right.name===fn.params[0].name)semantic={kind:'write-instance-field',field:field(e.left),parameter:fn.params[0].name};
   }
   const r=range(n),bytes=raw.subarray(r.start,r.end);
   methods.push({name:pname,static:!prototype,ownerAlias:alias,scopeBytes:range(scope),sourceBytes:r,sourceSha256:hash(bytes),
      parameters:fn.params.map(p=>p.type==='Identifier'?{name:p.name,sourceType:'unknown'}:{name:null,sourceType:'unsupported-binding',sourceBytes:range(p)}),semantic});
  }
 }
 for(const [k,v] of Object.entries(n)){
  if(k==='start'||k==='end')continue;
  if(Array.isArray(v)){for(let i=v.length-1;i>=0;i--)if(v[i]&&typeof v[i].type==='string')stack.push([v[i],[...parents,n],depth+1]);}
  else if(v&&typeof v.type==='string')stack.push([v,[...parents,n],depth+1]);
 }
}
const descriptors=require('./numeric-descriptors.cjs')(ast,range,n=>{const r=range(n);return hash(raw.subarray(r.start,r.end));});
methods.push(...descriptors.methods);registrations.push(...descriptors.registrations);
methods.sort((a,b)=>a.sourceBytes.start-b.sourceBytes.start);
process.stdout.write(JSON.stringify({schemaVersion:1,source:{sha256:hash(raw),bytes:raw.length},methods,calls,classScopes,registrations,descriptorClasses:descriptors.classes,importBindings:descriptors.imports,sourceExecuted:false,
  scope:'Static field-copy and candidate numeric descriptor facts; helper binding and call domains require explicit verification'}));
