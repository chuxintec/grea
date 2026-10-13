/** Copy selected static assets; no bundling or gameplay validation. */
import fs from 'node:fs';
import path from 'node:path';
import {parseArgs} from 'node:util';
const help=`Usage: node static_build.mjs --source DIR --output DIR --map FROM=TO [--map FROM=TO ...]
Example: --map index.html=index.html --map src=src --map public/assets=assets
Requires Node 18.3+. Output must be new or empty and outside source.
Rejects traversal, symlinks and overlapping destinations. Files are not transformed.`;
const inside=(root,file)=>{const r=path.relative(root,file);return r===''||(!r.startsWith('..'+path.sep)&&r!=='..'&&!path.isAbsolute(r))};
function relative(value){if(!value||path.isAbsolute(value)||value.split(/[\\/]/).includes('..')||path.normalize(value)==='.')throw Error(`Expected relative path: ${value}`);return value}
function checkTree(file){const s=fs.lstatSync(file);if(s.isSymbolicLink())throw Error(`Symlink: ${file}`);if(s.isDirectory())for(const child of fs.readdirSync(file))checkTree(path.join(file,child));else if(!s.isFile())throw Error(`Not a regular file: ${file}`)}
try{
 const {values:v}=parseArgs({options:{source:{type:'string'},output:{type:'string'},map:{type:'string',multiple:true},help:{type:'boolean'}}});
 if(v.help){console.log(help);process.exit(0)}
 if(!v.source||!v.output||!v.map?.length)throw Error(help);
 const source=fs.realpathSync(v.source),output=path.resolve(v.output);
 if(!fs.statSync(source).isDirectory())throw Error('Source must be a directory');
 let ancestor=output;while(!fs.existsSync(ancestor))ancestor=path.dirname(ancestor);
 const realOutput=path.resolve(fs.realpathSync(ancestor),path.relative(ancestor,output));
 if(inside(source,realOutput)||inside(realOutput,source))throw Error('Source and output must be disjoint');
 if(fs.existsSync(output)&&(!fs.statSync(output).isDirectory()||fs.readdirSync(output).length))throw Error('Output must be new or empty');
 const mappings=v.map.map(value=>{
  const split=value.indexOf('=');if(split<0)throw Error(`Expected FROM=TO: ${value}`);
  const from=relative(value.slice(0,split)),to=relative(value.slice(split+1));
  const input=path.resolve(source,from),dest=path.resolve(realOutput,to);
  let current=source;for(const part of path.relative(source,input).split(path.sep)){current=path.join(current,part);if(fs.lstatSync(current).isSymbolicLink())throw Error(`Symlink in source path: ${current}`)}
  checkTree(input);return {input,dest,from,to};
 });
 for(let i=0;i<mappings.length;i++)for(let j=0;j<i;j++)if(inside(mappings[i].dest,mappings[j].dest)||inside(mappings[j].dest,mappings[i].dest))throw Error('Overlapping destination mappings');
 fs.mkdirSync(realOutput,{recursive:true});
 for(const {input,dest} of mappings){fs.mkdirSync(path.dirname(dest),{recursive:true});fs.cpSync(input,dest,{recursive:true,force:false,errorOnExist:true})}
 console.log(JSON.stringify({output:realOutput,mappings:mappings.map(({from,to})=>({from,to})),validation:'copy-only; browser and original-game acceptance still required'},null,2));
}catch(error){console.error(error.message);process.exitCode=1}
