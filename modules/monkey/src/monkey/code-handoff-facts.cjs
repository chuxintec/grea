'use strict';
// Literal member declarations and exact source locations; no alias folding or execution.
module.exports=function facts(ast,source,byteRange,hash){
 const methods=[],fields=[],functions=[],stack=[[ast,[],0]];let visited=0;
 const prop=n=>n?.type==='MemberExpression'?(!n.computed&&n.property.type==='Identifier'?n.property.name:n.property.type==='Literal'&&typeof n.property.value==='string'?n.property.value:null):null;
 const key=n=>n?.type==='Identifier'?n.name:n?.type==='Literal'&&typeof n.value==='string'?n.value:null;
 const text=n=>source.slice(n.start,n.end);
 const span=n=>({sourceBytes:byteRange(n),sourceSha256:hash(Buffer.from(text(n),'utf8'))});
 const parameters=fn=>fn.params.map((p,i)=>({name:p.type==='Identifier'?p.name:null,sourceBinding:text(p),sourceType:'unknown',position:i}));
 const add=(fn,name,owner,stat,kind)=>{
  if(methods.length>=50000)throw Error('Code member budget');
  methods.push({name,ownerAlias:owner,static:stat,kind,parameters:parameters(fn),returnType:'unknown',...span(fn),implementation:'TODO: preserve and translate original body from exact source'});
 };
 while(stack.length){
  const [n,parents,depth]=stack.pop();if(++visited>3000000||depth>512)throw Error('Code facts AST budget');
  if(n.type==='AssignmentExpression'&&n.operator==='='&&n.left.type==='MemberExpression'){
   const name=prop(n.left),owner=n.left.object;
   if(name&&['FunctionExpression','ArrowFunctionExpression'].includes(n.right.type)){
    if(prop(owner)==='prototype'&&owner.object.type==='Identifier')add(n.right,name,owner.object.name,false,'prototype-assignment');
    else if(owner.type==='Identifier')add(n.right,name,owner.name,true,'literal-member-assignment');
   }
   if(name&&owner.type==='ThisExpression')fields.push({name,ownerAlias:'this',sourceType:'unknown',initialExpression:text(n.right).slice(0,200),...span(n)});
  }
  if(n.type==='MethodDefinition'&&!n.computed&&key(n.key))add(n.value,key(n.key),parents.findLast(p=>p.type==='ClassDeclaration'||p.type==='ClassExpression')?.id?.name||null,Boolean(n.static),n.kind);
  if(n.type==='Property'&&!n.computed&&['FunctionExpression','ArrowFunctionExpression'].includes(n.value?.type)&&key(n.key))add(n.value,key(n.key),null,false,'object-literal');
  if(n.type==='FunctionDeclaration'&&n.id)functions.push({name:n.id.name,parameters:parameters(n),...span(n),implementation:'TODO: original function body retained'});
  if(n.type==='CallExpression'&&n.arguments.length>=3&&prop(n.arguments[1])==='prototype'&&n.arguments[1].object.type==='Identifier'&&n.arguments[2].type==='Literal'&&typeof n.arguments[2].value==='string'){
   fields.push({name:n.arguments[2].value,ownerAlias:n.arguments[1].object.name,sourceType:'unknown',declarationKind:'literal-prototype-decorator',...span(n)});
  }
  for(const [k,v]of Object.entries(n)){
   if(k==='start'||k==='end')continue;
   if(Array.isArray(v)){for(let i=v.length-1;i>=0;i--)if(v[i]&&typeof v[i].type==='string')stack.push([v[i],[...parents,n],depth+1]);}
   else if(v&&typeof v.type==='string')stack.push([v,[...parents,n],depth+1]);
  }
 }
 methods.sort((a,b)=>a.sourceBytes.start-b.sourceBytes.start);fields.sort((a,b)=>a.sourceBytes.start-b.sourceBytes.start);
 return {methods,fields,functions,sourceExecuted:false,ownership:'literal owner aliases; unresolved alias/class equivalence is not inferred'};
};
