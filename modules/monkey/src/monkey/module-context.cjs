'use strict';
// Prove a bounded original helper's lexical CommonJS dependency; never execute it.
const fs=require('node:fs'),crypto=require('node:crypto'),path=require('node:path').posix,acorn=require('./sources/acorn.cjs');
const job=JSON.parse(fs.readFileSync(0,'utf8')),raw=fs.readFileSync(job.source);
if(raw.length>32*1024*1024)throw Error('Context byte budget');
const source=new TextDecoder('utf-8',{fatal:true}).decode(raw),hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const start=raw.subarray(0,job.start).toString('utf8').length,end=raw.subarray(0,job.end).toString('utf8').length;
if(hash(raw.subarray(job.start,job.end))!==job.helperSha256)throw Error('Helper context bytes differ');
const ast=acorn.parse(source,{ecmaVersion:2020,sourceType:'script'}),stack=[[ast,[]]],definitions=[],mutations=[];
const funcs=new Set(['FunctionExpression','FunctionDeclaration','ArrowFunctionExpression']);
function names(pattern){
 if(!pattern)return [];
 if(pattern.type==='Identifier')return [pattern.name];
 if(pattern.type==='RestElement')return names(pattern.argument);
 if(pattern.type==='AssignmentPattern')return names(pattern.left);
 if(pattern.type==='ArrayPattern')return pattern.elements.flatMap(names);
 if(pattern.type==='ObjectPattern')return pattern.properties.flatMap(p=>names(p.type==='RestElement'?p.argument:p.value));
 return [];
}
const defineByFunction=new WeakMap();let found=null,count=0;
while(stack.length){
 const [n,scopes]=stack.pop();if(++count>1000000||scopes.length>512)throw Error('Context AST budget');
 const next=funcs.has(n.type)||n.type==='Program'||n.type==='CatchClause'?[...scopes,n]:scopes;
 if(n.type==='FunctionExpression'&&n.start===start&&n.end===end){if(found)throw Error('Ambiguous helper callback');found={node:n,scopes};}
 if(n.type==='CallExpression'&&n.callee.type==='Identifier'&&n.callee.name==='define'&&n.arguments.length===2&&n.arguments[0].type==='Literal'&&typeof n.arguments[0].value==='string'&&n.arguments[1].type==='FunctionExpression'){
  if(definitions.length>=50000)throw Error('Context module budget');definitions.push(n);defineByFunction.set(n.arguments[1],n);
 }
 const identifier=n.type==='AssignmentExpression'?n.left:n.type==='UpdateExpression'?n.argument:['ForOfStatement','ForInStatement'].includes(n.type)&&n.left.type!=='VariableDeclaration'?n.left:null;
 for(const name of names(identifier))if([job.freeAlias,'require'].includes(name))mutations.push({scopes,name});
 if(n.type==='WithStatement'||n.type==='CallExpression'&&n.callee.type==='Identifier'&&n.callee.name==='eval')mutations.push({scopes,name:'*dynamic*'});
 for(const v of Object.values(n))if(Array.isArray(v)){for(const x of v)if(x&&typeof x.type==='string')stack.push([x,next]);}else if(v&&typeof v.type==='string')stack.push([v,next]);
}
if(!found)throw Error('One exact helper callback required');
const bindingCache=new WeakMap();
function bindings(scope){
 if(bindingCache.has(scope))return bindingCache.get(scope);
 const list=[];const pending=[scope.body];if(Array.isArray(scope.body))pending.push(...scope.body);
 for(const p of scope.params||[])for(const name of names(p))list.push({name,node:p,param:p.type==='Identifier'});
 if(scope.type==='CatchClause')for(const name of names(scope.param))list.push({name,node:scope.param});
 if(scope.id?.type==='Identifier')list.push({name:scope.id.name,node:scope.id});
 while(pending.length){const n=pending.pop();if(!n||Array.isArray(n))continue;
  if(n!==scope.body&&funcs.has(n.type)){if(n.type==='FunctionDeclaration')list.push({name:n.id.name,node:n});continue;}
  if(n.type==='VariableDeclarator')for(const name of names(n.id))list.push({name,node:n});
  for(const v of Object.values(n))if(Array.isArray(v)){for(const x of v)if(x&&typeof x.type==='string')pending.push(x);}else if(v&&typeof v.type==='string')pending.push(v);
 }
 bindingCache.set(scope,list);return list;
}
let owner,decl;
for(const scope of [found.node,...found.scopes.slice().reverse()]){
 const matches=bindings(scope).filter(b=>b.name===job.freeAlias);if(matches.length){if(matches.length!==1)throw Error('Ambiguous lexical alias');owner=scope;decl=matches[0].node;break;}
}
if(!owner||decl.type!=='VariableDeclarator'||decl.init?.type!=='CallExpression'||decl.init.callee.type!=='Identifier'||decl.init.callee.name!=='require'||decl.init.arguments.length!==1||decl.init.arguments[0].type!=='Literal'||typeof decl.init.arguments[0].value!=='string')throw Error('Expected literal lexical require binding');
const enclosing=defineByFunction.get(owner);
if(!enclosing||owner.params.map(p=>p.type==='Identifier'?p.name:'').join(',')!=='require,module,exports')throw Error('Expected exact enclosing named CommonJS module');
const requireBinding=bindings(owner).filter(b=>b.name==='require');
if(requireBinding.length!==1||!requireBinding[0].param)throw Error('Require parameter is shadowed');
for(const {scopes,name} of mutations){
 if(!scopes.includes(owner))continue;
 if(name==='*dynamic*')throw Error('Dynamic lexical scope is unsupported');
 const resolution=scopes.slice().reverse().find(p=>bindings(p).some(b=>b.name===name));
 if(resolution===owner)throw Error('Lexical helper alias can be reassigned');
}
const definingName=enclosing.arguments[0].value,requested=decl.init.arguments[0].value;
if(!requested.startsWith('./')&&!requested.startsWith('../'))throw Error('Expected declared relative helper');
const normalized=path.normalize(path.join(path.dirname(definingName),requested));
const targets=definitions.filter(n=>[normalized,normalized+'.js'].includes(n.arguments[0].value));
if(targets.length!==1)throw Error('Original require identity unavailable or ambiguous');
const target=targets[0],fn=target.arguments[1];
const span=n=>({start:Buffer.byteLength(source.slice(0,n.start)),end:Buffer.byteLength(source.slice(0,n.end))});
const bodyRange=span(fn),bindingRange=span(decl),moduleRange=span(target);
process.stdout.write(JSON.stringify({schemaVersion:1,sourceSha256:hash(raw),sourceBytes:raw.length,helperSha256:job.helperSha256,helperBytes:{start:job.start,end:job.end},freeAlias:job.freeAlias,enclosingModule:definingName,
 requirePath:requested,bindingBytes:bindingRange,bindingSha256:hash(raw.subarray(bindingRange.start,bindingRange.end)),resolvedModule:target.arguments[0].value,moduleBytes:moduleRange,callbackBytes:bodyRange,
 callbackSha256:hash(raw.subarray(bodyRange.start,bodyRange.end)),sourceExecuted:false}));
