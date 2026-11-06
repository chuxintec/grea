'use strict';
const fs=require('node:fs'),crypto=require('node:crypto'),acorn=require('./sources/acorn.cjs');
const job=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),records=[];let total=0;
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
if(!Array.isArray(job.files)||job.files.length>4000)throw Error('Explicit module budget');
for(const row of job.files){
 const raw=fs.readFileSync(row.path);total+=raw.length;if(raw.length>32*1024*1024||total>128*1024*1024||hash(raw)!==row.sha256)throw Error('Frozen module identity/budget changed');
 const source=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw);let ast;
 try{ast=acorn.parse(source,{ecmaVersion:2020,sourceType:'script',allowReturnOutsideFunction:true});}
 catch(e){ast=acorn.parseExpressionAt(source,0,{ecmaVersion:2020});if(ast.type!=='FunctionExpression'||!['',';'].includes(source.slice(ast.end).trim()))throw e;}
 const offsets=require('./sources/source-offsets.cjs')(source),range=n=>({start:offsets[n.start],end:offsets[n.end]});
 const members=require('./code-handoff-facts.cjs')(ast,source,range,hash);records.push({id:row.id,sha256:row.sha256,members});
}
fs.writeFileSync(process.argv[3],JSON.stringify({schemaVersion:1,records,sourceExecuted:false}));
