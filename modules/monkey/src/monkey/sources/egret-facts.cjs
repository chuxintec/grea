'use strict';
// Tokenize the whole source, parse only bounded candidate expressions. Never evaluate source.
const fs=require('node:fs'),acorn=require('./acorn.cjs'),crypto=require('node:crypto');
const raw=fs.readFileSync(0);if(raw.length>32*1024*1024)throw Error('source byte budget');const s=new TextDecoder('utf-8',{fatal:true}).decode(raw);
const hash=b=>crypto.createHash('sha256').update(b).digest('hex'),span=n=>({start:Buffer.byteLength(s.slice(0,n.start)),end:Buffer.byteLength(s.slice(0,n.end))});
function bounded(start){
 const part=s.slice(start,start+65536),stream=acorn.tokenizer(part,{ecmaVersion:2020});let braces=0,body=false,end=0;
 for(;;){const token=stream.getToken(),label=token.type.label;if(label==='eof')throw Error('candidate byte budget');
  if(label==='{'){body=true;braces++;}else if(label==='${')braces++;else if(label==='}'){if(--braces===0&&body){end=token.end;break;}}
 }
 const n=acorn.parseExpressionAt(part.slice(0,end),0,{ecmaVersion:2020});
 // Offset the bounded AST root only; no source text is ever evaluated.
 return {start:start+n.start,end:start+n.end,type:n.type};
}
const wanted=new Set(['readAutoNumber','loadSinglePlistPack','readUnsignedShort','readFullJson','readString','readJsonField']),rows=[],history=[],tokens=acorn.tokenizer(s,{ecmaVersion:2020});let count=0;
for(;;){const t=tokens.getToken();if(++count>5000000)throw Error('token budget');if(t.type.label==='eof')break;
 let label=null,n=null;
 if(t.type.label==='function'){const peek=acorn.tokenizer(s.slice(t.end,t.end+80),{ecmaVersion:2020}).getToken();if(peek.type.label==='name'&&peek.value==='Be'){label='binJsonVarInt';n=bounded(t.start);}}
 if(t.type.label==='function'&&history.at(-1)?.type.label==='='&&wanted.has(history.at(-2)?.value)){label=history.at(-2).value;n=bounded(t.start);}
 if(t.type.label==='string'&&['resourceConfig','sheet'].includes(t.value)&&history.at(-1)?.type.label==='('&&history.at(-2)?.value==='map'&&history.at(-4)?.value==='processor'){
  const next=acorn.tokenizer(s.slice(t.end),{ecmaVersion:2020});const comma=next.getToken(),obj=next.getToken();if(comma.type.label!==','||obj.type.label!=='{')throw Error('processor shape');label='processor:'+t.value;n=bounded(t.end+obj.start);
 }
 if(label){if(n.type==='SequenceExpression')n=n.expressions[0];const r=span(n),body=raw.subarray(r.start,r.end);rows.push({name:label,sourceBytes:r,bytes:body.length,sha256:hash(body)});}
 history.push(t);if(history.length>8)history.shift();
}
let lexicalVarIntBinding=null;
if(rows.some(r=>r.name==='readFullJson')){
 if(raw.length>2*1024*1024)throw Error('lexical script byte budget');
 const tree=acorn.parse(s,{ecmaVersion:2020}),todo=[[tree,[]]],definitions=[],readers=[],writes=[];let nodes=0;
 while(todo.length){const [n,scopes]=todo.pop();if(++nodes>1000000)throw Error('lexical AST budget');
  if(n.type==='FunctionDeclaration'&&n.id?.name==='Be')definitions.push({node:n,owner:scopes.at(-1)});
  if((n.type==='AssignmentExpression'&&n.left.type==='Identifier'&&n.left.name==='Be'||n.type==='UpdateExpression'&&n.argument.type==='Identifier'&&n.argument.name==='Be'||n.type==='VariableDeclarator'&&n.id.type==='Identifier'&&n.id.name==='Be'))writes.push(scopes);
  if(n.type==='AssignmentExpression'&&n.right.type==='FunctionExpression'&&n.left.type==='MemberExpression'&&!n.left.computed&&['readFullJson','readJsonField'].includes(n.left.property.name))readers.push({node:n.right,owner:scopes.at(-1)});
  const next=['FunctionExpression','FunctionDeclaration','ArrowFunctionExpression'].includes(n.type)?[...scopes,n]:scopes;
  for(const v of Object.values(n))if(Array.isArray(v)){for(const x of v)if(x&&typeof x.type==='string')todo.push([x,next]);}else if(v&&typeof v.type==='string')todo.push([v,next]);
 }
 const wanted=readers.filter(r=>rows.some(f=>f.name==='readFullJson'&&f.sourceBytes.start===span(r.node).start));
 if(wanted.length!==1)throw Error('one exact BinJson reader required');
 const owner=wanted[0].owner,candidates=definitions.filter(d=>d.owner===owner);
 if(candidates.length!==1||writes.some(scopes=>scopes.includes(owner)))throw Error('ambiguous or mutable BinJson varint binding');
 const r=span(candidates[0].node);lexicalVarIntBinding={freeAlias:'Be',definitionBytes:r,definitionSha256:hash(raw.subarray(r.start,r.end)),ownerBytes:span(owner),sourceExecuted:false};
}
console.log(JSON.stringify({schemaVersion:1,sourceSha256:hash(raw),sourceBytes:raw.length,facts:rows,lexicalVarIntBinding,sourceExecuted:false},null,2));
