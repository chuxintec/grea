'use strict';
// The input is parsed as data. No vm/eval, imports from input, factory calls or rewriting.
const fs = require('node:fs');
const crypto = require('node:crypto');
const acorn = require('acorn');
const {TextDecoder} = require('node:util');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fail = (code, location, message) => {throw Object.assign(new Error(message), {code, location});};
const literal = n => n && n.type === 'Literal' && ((typeof n.value === 'string' && Buffer.from(n.value,'utf8').toString('utf8')===n.value) || (typeof n.value === 'number' && Number.isFinite(n.value)));
const property = n => n && n.type === 'MemberExpression' && (!n.computed && n.property.type === 'Identifier' ? n.property.name : literal(n.property) ? String(n.property.value) : null);
function walk(root, visit) {
  const pending = [[root, [], 0]]; let count = 0;
  while (pending.length) {
    const [node, parents, depth] = pending.pop();
    if (++count > 500000 || depth > 512) fail('BUDGET_EXCEEDED', '$.ast', 'AST budget exceeded');
    visit(node, parents);
    const next = [...parents, node];
    for (const [key, value] of Object.entries(node)) {
      if (key === 'start' || key === 'end') continue;
      if (Array.isArray(value)) { for (let i = value.length - 1; i >= 0; i--) if (value[i] && typeof value[i].type === 'string') pending.push([value[i], next, depth + 1]); }
      else if (value && typeof value.type === 'string') pending.push([value, next, depth + 1]);
    }
  }
}
function index(raw, adapter) {
  if (require('acorn/package.json').version !== '8.15.0') fail('DEPENDENCY_VERSION', '$', 'Pinned acorn 8.15.0 required');
  let source;
  try {source = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(raw);} catch {fail('INVALID_UTF8', '$', 'Source must be valid UTF-8');}
  if (!['browserify-table-v1','define-browserify-v1','define-factory-candidates-v1'].includes(adapter)) fail('UNSUPPORTED_ADAPTER', '$', 'Select an explicit wrapper adapter');
  let ast;
  try {ast = acorn.parse(source, {ecmaVersion:2020, sourceType:'script'});} catch (e) {fail('INVALID_JAVASCRIPT', '$.ast', e.message);}
  const isDefine = n => n.type === 'CallExpression' && n.callee.type === 'Identifier' && n.callee.name === 'define' && n.arguments.length >= 2 && literal(n.arguments[0]) && n.arguments[1].type === 'FunctionExpression';
  const tables = []; const candidateMode=adapter==='define-factory-candidates-v1';
  walk(ast, (node, parents) => {
    if (node.type !== 'CallExpression' || node.callee.type !== 'FunctionExpression' || node.callee.params.length !== 3 || node.arguments.length !== 3 || node.arguments[0].type !== (candidateMode ? 'CallExpression' : 'ObjectExpression')) return;
    const defined = parents.some(isDefine);
    if (defined === (adapter !== 'browserify-table-v1')) tables.push(node.arguments[0]);
  });
  if (tables.length !== 1) fail(tables.length ? 'AMBIGUOUS_WRAPPER' : 'UNSUPPORTED_WRAPPER', '$.ast', 'Exactly one supported three-argument loader table is required');
  const modules = [], names = new Set(), identities = new Map(), issues = [];
  const byteRange = node => ({start:Buffer.byteLength(source.slice(0,node.start),'utf8'), end:Buffer.byteLength(source.slice(0,node.end),'utf8')});
  const entries=[];
  if(candidateMode) {
    const table=tables[0];
    // Obfuscated call/bind chains remain unresolved; inspect literal factory assignments only.
    walk(table,(node,parents)=>{
      if(node.type!=='ArrayExpression' || node.elements.length!==2 || node.elements[0]?.type!=='FunctionExpression') return;
      if(parents.some((n,i)=>n.type==='FunctionExpression' && parents[i-1]?.type==='ArrayExpression' && parents[i-1].elements[0]===n)) return;
      const parent=parents[parents.length-1];
      if(parent?.type!=='AssignmentExpression' || parent.operator!=='=' || parent.right!==node || parent.left.type!=='MemberExpression') return;
      entries.push({type:'Property',computed:false,kind:'init',method:false,key:{type:'Literal',value:'candidate@'+node.start},value:node,candidate:true,keyExpression:parent.left.property});
    });
  } else entries.push(...tables[0].properties);
  for (const entry of entries) {
    if (entry.type !== 'Property' || entry.computed || entry.kind !== 'init' || entry.method) fail('UNSUPPORTED_MODULE', '$.table', 'Only literal module entries are supported');
    const name = entry.key.type === 'Identifier' ? entry.key.name : literal(entry.key) ? String(entry.key.value) : null;
    if (name === null) fail('UNSUPPORTED_MODULE', '$.table', 'Module name is unresolved');
    if (names.has(name)) fail('DUPLICATE_MODULE', '$.table', 'Duplicate module name');
    names.add(name);
    const values = entry.value.type === 'ArrayExpression' ? entry.value.elements : [];
    if (values.length !== 2 || !values[0] || values[0].type !== 'FunctionExpression' || !values[1] || (!candidateMode && values[1].type !== 'ObjectExpression')) fail('UNSUPPORTED_MODULE', '$.table.'+name, 'Expected [function, dependency object]');
    const factory = values[0], dependencies = [], rf = [], unresolved = [];
    if(candidateMode) unresolved.push({kind:'module_name_and_table_membership',source_bytes:byteRange(entry.keyExpression)});
    if(values[1].type!=='ObjectExpression') unresolved.push({kind:'dependency_expression',source_bytes:byteRange(values[1])});
    const dependencyKeys = new Set();
    for (const dep of values[1].properties || []) {
      if (dep.type !== 'Property' || dep.computed || dep.kind !== 'init' || dep.method) {unresolved.push({kind:'dependency',source_bytes:byteRange(dep)}); continue;}
      const key = dep.key.type === 'Identifier' ? dep.key.name : literal(dep.key) ? String(dep.key.value) : null;
      if (key === null || dependencyKeys.has(key)) fail('DUPLICATE_DEPENDENCY', '$.table.'+name, 'Duplicate or unresolved dependency key');
      dependencyKeys.add(key);
      if (literal(dep.value)) dependencies.push({key, module:dep.value.value});
      else unresolved.push({kind:'dependency',key, source_bytes:byteRange(dep.value)});
    }
    walk(factory, node => {
      if (node.type !== 'CallExpression' || property(node.callee) !== 'push') return;
      const member = node.callee.object;
      if (property(member) !== '_RF' || member.object.type !== 'Identifier' || member.object.name !== 'cc') return;
      const args = node.arguments, resolved = args.length === 3 && literal(args[1]) && typeof args[1].value === 'string' && literal(args[2]) && typeof args[2].value === 'string';
      const record = {status:resolved?'literal_syntax':'unresolved',source_bytes:byteRange(node)};
      if (resolved) {
        record.identity=args[1].value; record.class_name=args[2].value;
        const previous=identities.get(record.identity);
        if (previous !== undefined) issues.push({code:'DUPLICATE_RF_IDENTITY',identity:record.identity,modules:[previous,name]});
        else identities.set(record.identity,name);
      } else unresolved.push({kind:'rf',source_bytes:byteRange(node)});
      rf.push(record);
    });
    const range=byteRange(factory), bytes=raw.subarray(range.start,range.end);
    modules.push({name:candidateMode?null:name,confidence:candidateMode?'syntax_candidate':'literal_table_syntax',candidate_id:candidateMode?name:null,filename:'module-'+sha(Buffer.from(name,'utf8'))+'.js',source_bytes:range,sha256:sha(bytes),dependencies,rf,unresolved,source:bytes.toString('utf8')});
  }
  if (!modules.length) fail('EMPTY_INPUT', '$.table', 'No modules found');
  return {schema_version:1,tool:'cocos_modules',implementation_version:'0.1.0',source_format:adapter,selection:{adapter},status:candidateMode || issues.length || modules.some(x=>x.unresolved.length)?'partial':'complete',source:{sha256:sha(raw),bytes:raw.length},modules,issues,errors:[],unsupported:[],scope:'AST syntax evidence only; no identifier folding, deobfuscation, module execution or RF runtime registration proof',effects:['filesystem_read','create_only_candidate']};
}
try {
  const raw=fs.readFileSync(0);
  if (raw.length > 32*1024*1024) fail('BUDGET_EXCEEDED', '$', 'Source exceeds 32 MiB');
  process.stdout.write(JSON.stringify(index(raw,process.argv[2])));
} catch (error) {
  process.stdout.write(JSON.stringify({error:{code:error.code || 'PARSE_ERROR',location:error.location || '$',message:error.message}}));
  process.exitCode=1;
}
