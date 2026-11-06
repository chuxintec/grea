'use strict';

// Static-only declaration extraction. Source is parsed as data; never eval/vm.
const fs = require('node:fs');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const acorn = require('./sources/acorn.cjs');

const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fail = (code, message) => { throw Object.assign(new Error(message), { code }); };
const isNode = x => x && typeof x.type === 'string';
const children = node => Object.entries(node).flatMap(([key, value]) => {
  if (key === 'start' || key === 'end' || key === 'loc') return [];
  return Array.isArray(value) ? value.filter(isNode) : isNode(value) ? [value] : [];
});
function walk(node, visit, parents = []) {
  visit(node, parents);
  const next = [...parents, node];
  for (const child of children(node)) walk(child, visit, next);
}
const memberName = node => {
  if (!node || node.type !== 'MemberExpression') return null;
  if (!node.computed && node.property.type === 'Identifier') return node.property.name;
  if (node.computed && node.property.type === 'Literal' && ['string', 'number'].includes(typeof node.property.value)) return String(node.property.value);
  return null;
};
const hasThis = node => {
  let found = false;
  walk(node, n => { if (n.type === 'ThisExpression') found = true; });
  return found;
};

function constant(node, resolveMember = null) {
  if (!node) return { ok: false, reason: 'missing_expression' };
  if (node.type === 'MemberExpression' && resolveMember) {
    const resolved = resolveMember(node);
    if (resolved?.ok) return resolved;
  }
  if (node.type === 'Literal' && (node.value === null || ['boolean', 'string'].includes(typeof node.value) || (typeof node.value === 'number' && Number.isFinite(node.value))))
    return { ok: true, kind: node.value === null ? 'null' : typeof node.value, value: node.value };
  if (node.type === 'UnaryExpression' && node.operator === '!' && node.argument.type === 'Literal' && ['boolean', 'number'].includes(typeof node.argument.value))
    return { ok: true, kind: 'boolean', value: !node.argument.value };
  if (node.type === 'UnaryExpression' && ['+', '-'].includes(node.operator) && node.argument.type === 'Literal' && typeof node.argument.value === 'number' && Number.isFinite(node.argument.value)) {
    const value = node.operator === '-' ? -node.argument.value : node.argument.value;
    return Number.isFinite(value) ? { ok: true, kind: 'number', value } : { ok: false, reason: 'non_finite_number' };
  }
  if (node.type === 'ArrayExpression') {
    const values = [];
    for (const element of node.elements) {
      if (!element || element.type === 'SpreadElement') return { ok: false, reason: 'array_hole_or_spread' };
      const item = constant(element, resolveMember);
      if (!item.ok) return item;
      values.push(item.value);
    }
    return { ok: true, kind: 'array', value: values };
  }
  if (node.type === 'ObjectExpression') {
    const value = Object.create(null);
    for (const property of node.properties) {
      if (property.type !== 'Property' || property.computed || property.kind !== 'init' || property.method || property.shorthand)
        return { ok: false, reason: 'non_literal_object_property' };
      const key = property.key.type === 'Identifier' ? property.key.name : property.key.type === 'Literal' && ['string', 'number'].includes(typeof property.key.value) ? String(property.key.value) : null;
      if (key === null || Object.hasOwn(value, key)) return { ok: false, reason: 'unresolved_or_duplicate_object_key' };
      const item = constant(property.value, resolveMember);
      if (!item.ok) return item;
      value[key] = item.value;
    }
    return { ok: true, kind: 'object', value };
  }
  return { ok: false, reason: 'not_a_supported_constant' };
}

function enumIndex(ast) {
  const exact = new Map(), byLeaf = new Map();
  const add = (key, table) => {
    if (!key) return;
    const previous = exact.get(key);
    if (!previous) exact.set(key, table);
    else if (JSON.stringify([...previous]) !== JSON.stringify([...table])) exact.set(key, null);
    const leaf = key.split('.').pop();
    const rows = byLeaf.get(leaf) || [];
    rows.push(table); byLeaf.set(leaf, rows);
  };
  const path = node => {
    if (node?.type === 'Identifier') return node.name;
    if (node?.type === 'MemberExpression' && !node.computed && node.property.type === 'Identifier') {
      const parent = path(node.object); return parent ? parent + '.' + node.property.name : null;
    }
    return null;
  };
  const enumSeed = node => {
    let current = node;
    if (current?.type === 'AssignmentExpression' && current.operator === '=') current = current.right;
    if (current?.type === 'LogicalExpression' && current.operator === '||') current = current.left;
    return path(current);
  };
  walk(ast, node => {
    if (node.type !== 'CallExpression' || !node.callee || !['FunctionExpression', 'ArrowFunctionExpression'].includes(node.callee.type)) return;
    const parameter = node.callee.params?.[0];
    if (!parameter || parameter.type !== 'Identifier') return;
    const table = new Map(); let invalid = false, matched = 0;
    const statements = node.callee.body?.body || [];
    for (const statement of statements) {
      if (statement.type !== 'ExpressionStatement') { invalid = true; break; }
      const expressions = statement.expression.type === 'SequenceExpression' ? statement.expression.expressions : [statement.expression];
      for (const candidate of expressions) {
      if (candidate.type !== 'AssignmentExpression' || candidate.operator !== '=') { invalid = true; continue; }
      const outer = candidate.left, inner = outer?.type === 'MemberExpression' && outer.computed ? outer.property : null;
      if (!inner || inner.type !== 'AssignmentExpression' || inner.operator !== '=') { invalid = true; continue; }
      const enumObject = inner.left;
      if (enumObject?.type !== 'MemberExpression' || enumObject.computed || enumObject.object.type !== 'Identifier'
          || enumObject.object.name !== parameter.name || enumObject.property.type !== 'Identifier'
          || outer.object.type !== 'Identifier' || outer.object.name !== parameter.name) { invalid = true; continue; }
      const name = enumObject.property.name, numeric = inner.right, string = candidate.right;
      if (numeric?.type !== 'Literal' || typeof numeric.value !== 'number' || !Number.isFinite(numeric.value)
          || string?.type !== 'Literal' || string.value !== name || table.has(name)) { invalid = true; return; }
      table.set(name, numeric.value); matched++;
      }
    }
    if (!matched || invalid || !node.arguments?.length) return;
    const key = enumSeed(node.arguments[0]);
    add(key, table);
  });
  const leaf = new Map();
  for (const [name, tables] of byLeaf) {
    const first = tables[0];
    if (tables.every(table => JSON.stringify([...table]) === JSON.stringify([...first]))) leaf.set(name, first);
  }
  return { exact, leaf };
}

function enumMemberResolver(tables) {
  const path = node => {
    if (node?.type === 'Identifier') return node.name;
    if (node?.type === 'MemberExpression' && !node.computed && node.property.type === 'Identifier') {
      const parent = path(node.object); return parent ? parent + '.' + node.property.name : null;
    }
    return null;
  };
  return node => {
    const full = path(node); if (!full) return null;
    // Cocos Creator 2.4 documents this immutable engine constant as RGBA bytes.
    // Keep the resolution deliberately narrow; arbitrary cc.* members are not constants.
    if (full === 'cc.Color.WHITE') return { ok: true, kind: 'object',
      value: { r: 255, g: 255, b: 255, a: 255 }, sourceConstant: full,
      resolution: 'cocos_creator_2_4_documented_color_white' };
    const tablePath = full.slice(0, full.lastIndexOf('.'));
    const member = full.slice(full.lastIndexOf('.') + 1);
    const table = tables.exact.has(tablePath) ? tables.exact.get(tablePath) : tables.leaf.get(tablePath.split('.').pop());
    if (!table || !table.has(member)) return null;
    return { ok: true, kind: 'number', value: table.get(member) };
  };
}

function constructorAlias(fn) {
  const body = fn.body?.body || [];
  for (const statement of body) {
    if (statement.type !== 'VariableDeclaration') continue;
    for (const declarator of statement.declarations) {
      if (declarator.id.type === 'Identifier' && declarator.init && hasThis(declarator.init)) return declarator.id.name;
    }
  }
  // A simple base class can use `var self = this` or direct `this` writes.
  if (body.some(statement => statement.type === 'ExpressionStatement'
      && (statement.expression.type === 'AssignmentExpression' ? [statement.expression] : statement.expression.type === 'SequenceExpression' ? statement.expression.expressions : [])
        .some(expression => expression.type === 'AssignmentExpression' && expression.left.object?.type === 'ThisExpression'))) return 'this';
  return null;
}

function directAssignments(fn, alias, source, absoluteStart, byteOffset) {
  const candidates = [];
  const add = expression => {
    if (!expression || expression.type !== 'AssignmentExpression') return;
    const left = expression.left, name = memberName(left);
    const ownerMatches = name && (left.object.type === 'ThisExpression' || (alias !== 'this' && left.object.type === 'Identifier' && left.object.name === alias));
    if (ownerMatches) candidates.push({ name, expression, rhs: expression.right });
  };
  for (const statement of fn.body.body || []) {
    if (statement.type === 'ExpressionStatement') {
      const expressions = statement.expression.type === 'SequenceExpression' ? statement.expression.expressions : [statement.expression];
      for (const expression of expressions) add(expression);
    }
    if (statement.type === 'ReturnStatement' && statement.argument) {
      const expressions = statement.argument.type === 'SequenceExpression' ? statement.argument.expressions : [statement.argument];
      for (const expression of expressions) add(expression);
    }
  }
  return candidates.map(item => ({
    ...item,
    sourceBytes: { start: absoluteStart + byteOffset(item.expression.start), end: absoluteStart + byteOffset(item.expression.end) },
    rhsBytes: { start: absoluteStart + byteOffset(item.rhs.start), end: absoluteStart + byteOffset(item.rhs.end) },
  }));
}

function nestedAssignments(fn, alias, accepted) {
  const found = [];
  const visit = node => {
    if (!isNode(node)) return;
    if (node !== fn && ['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'].includes(node.type)) return;
    if (node.type === 'AssignmentExpression' && node.left.type === 'MemberExpression') {
      const name = memberName(node.left);
      const ownerMatches = name && (node.left.object.type === 'ThisExpression' || (alias !== 'this' && node.left.object.type === 'Identifier' && node.left.object.name === alias));
      if (ownerMatches && !accepted.has(node)) found.push({ name, node });
    }
    for (const child of children(node)) visit(child);
  };
  visit(fn.body);
  return found;
}

const isFunction = node => ['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'].includes(node.type);
const KNOWN_ENGINE_BASES = new Set([
  'cc.Component', 'cc.Node', 'cc.EventTarget', 'cc.Object', 'cc.Asset', 'cc.RenderComponent', 'cc.UIComponent',
  'cc.Sprite', 'cc.Label', 'cc.Button', 'cc.ScrollView', 'cc.Layout', 'cc.Mask', 'cc.Canvas', 'cc.Widget',
  'cc.BlockInputEvents', 'cc.Animation', 'cc.ProgressBar', 'cc.Slider', 'cc.Toggle', 'cc.EditBox', 'cc.RichText', 'cc.Graphics',
]);

function buildScopeIndex(source) {
  const ast = acorn.parse(source, { ecmaVersion: 2020, sourceType: 'script' });
  const offsets = require('./sources/source-offsets.cjs')(source);
  const parents = new WeakMap(), nodeScopes = new WeakMap(), scopes = [];
  const root = { node: ast, kind: 'program', parent: null, bindings: new Map(), start: 0, end: offsets[ast.end] };
  scopes.push(root);
  const makeScope = (node, kind, parent) => {
    const scope = { node, kind, parent, bindings: new Map(), start: offsets[node.start], end: offsets[node.end] };
    scopes.push(scope); return scope;
  };
  const visit = (node, parent, scope) => {
    if (!isNode(node)) return;
    if (parent) parents.set(node, parent);
    let current = scope;
    if (node === ast) current = root;
    else if (isFunction(node)) current = makeScope(node, 'function', scope);
    else if (node.type === 'BlockStatement' && !(parent && isFunction(parent) && parent.body === node)) current = makeScope(node, 'block', scope);
    else if (node.type === 'CatchClause') current = makeScope(node, 'block', scope);
    nodeScopes.set(node, current);
    for (const child of children(node)) visit(child, node, current);
  };
  visit(ast, null, null);

  const nearestFunctionScope = scope => {
    while (scope && !['program', 'function'].includes(scope.kind)) scope = scope.parent;
    return scope;
  };
  const bindingAt = (scope, name) => {
    while (scope) {
      const binding = scope.bindings.get(name);
      if (binding) return binding;
      scope = scope.parent;
    }
    return null;
  };
  const addEvent = (scope, name, event) => {
    if (!scope || !name) return;
    let binding = scope.bindings.get(name);
    if (!binding) { binding = { name, scope, events: [] }; scope.bindings.set(name, binding); }
    binding.events.push(event);
  };
  const unconditionalBody = body => {
    if (!body) return false;
    if (body.type === 'Program') return true;
    if (isFunction(parents.get(body)) && parents.get(body).body === body) return true;
    if (body.type !== 'BlockStatement') return false;
    const outer = parents.get(body);
    if (outer?.type === 'Program') return true;
    if (outer?.type === 'BlockStatement' && (outer.body || []).includes(body)) return unconditionalBody(outer);
    return false;
  };
  const directStatement = node => {
    let expression = node, parent = parents.get(expression);
    while (parent?.type === 'SequenceExpression') { expression = parent; parent = parents.get(expression); }
    const statement = parent?.type === 'ExpressionStatement' && parent.expression === expression ? parent : null;
    if (!statement) return false;
    const body = parents.get(statement);
    return (body?.type === 'Program' || body?.type === 'BlockStatement') && (body.body || []).includes(statement) && unconditionalBody(body);
  };
  walk(ast, (node, ancestors) => {
    if (node.type === 'VariableDeclarator' && node.id.type === 'Identifier') {
      const declaration = parents.get(node);
      if (declaration?.type !== 'VariableDeclaration') return;
      const lexical = nodeScopes.get(node);
      const target = declaration.kind === 'var' ? nearestFunctionScope(lexical) : lexical;
      const initStart = node.init ? offsets[node.init.start] : offsets[node.start];
      const statement = parents.get(declaration);
      addEvent(target, node.id.name, { position: initStart, kind: node.init ? 'initializer' : 'uninitialized_declaration', value: node.init || null, safe: !node.init || unconditionalBody(statement?.type === 'Program' || statement?.type === 'BlockStatement' ? statement : null), node });
    } else if (node.type === 'FunctionDeclaration' && node.id) {
      const lexical = nodeScopes.get(parents.get(node)) || root;
      addEvent(lexical, node.id.name, { position: 0, kind: 'function_declaration', value: node, safe: true, node });
    } else if (node.type === 'ClassDeclaration' && node.id) {
      const lexical = nodeScopes.get(parents.get(node)) || root;
      addEvent(lexical, node.id.name, { position: offsets[node.start], kind: 'class_declaration', value: node, safe: directStatement(node) || parents.get(node)?.type === 'Program', node });
    }
  });
  // Parameters are lexical bindings with unknown runtime values.
  walk(ast, node => {
    if (!isFunction(node)) return;
    const scope = nodeScopes.get(node);
    for (const param of node.params || []) if (param.type === 'Identifier') addEvent(scope, param.name, { position: offsets[node.start], kind: 'parameter', value: null, safe: false, node: param });
  });
  walk(ast, node => {
    if (node.type === 'AssignmentExpression' && node.left.type === 'Identifier') {
      const scope = nodeScopes.get(node);
      const binding = bindingAt(scope, node.left.name);
      if (binding) addEvent(binding.scope, binding.name, { position: offsets[node.start], kind: node.operator === '=' ? 'assignment' : 'compound_assignment', value: node.operator === '=' ? node.right : null, safe: node.operator === '=' && directStatement(node), node });
    } else if (node.type === 'UpdateExpression' && node.argument.type === 'Identifier') {
      const binding = bindingAt(nodeScopes.get(node), node.argument.name);
      if (binding) addEvent(binding.scope, binding.name, { position: offsets[node.start], kind: 'update_assignment', value: null, safe: false, node });
    }
  });
  for (const scope of scopes) for (const binding of scope.bindings.values()) binding.events.sort((a, b) => a.position - b.position);

  return {
    ast, source, offsets, parents, nodeScopes, scopes,
    scopeAt(offset) { return scopes.filter(scope => scope.start <= offset && offset <= scope.end).sort((a, b) => (a.end - a.start) - (b.end - b.start))[0] || root; },
    resolve(name, offset) {
      const binding = bindingAt(this.scopeAt(offset), name);
      if (!binding) return { status: 'unbound', name };
      const prior = binding.events.filter(event => event.position < offset && event.kind !== 'uninitialized_declaration');
      if (!prior.length) return { status: 'not_initialized_before_use', name, bindingKind: binding.events[0]?.kind || 'declaration' };
      const unsafe = prior.filter(event => !event.safe);
      if (unsafe.length) return { status: 'dynamic_or_conditional_write', name, writes: unsafe.map(event => ({ kind: event.kind, position: event.position })) };
      const event = prior[prior.length - 1];
      if (!event.value) return { status: 'uninitialized_before_use', name, bindingKind: event.kind };
      return { status: 'resolved', name, bindingKind: event.kind, value: event.value, initializerBytes: { start: event.position, end: offsets[event.value.end] }, initializerSha256: digest(Buffer.from(source.slice(event.value.start, event.value.end), 'utf8')), eventPosition: event.position };
    },
    moduleAt(offset, modules) {
      const matches = modules.filter(module => module.source_bytes.start <= offset && offset < module.source_bytes.end);
      return matches.length === 1 ? { status: 'resolved', module: matches[0] } : { status: matches.length ? 'ambiguous_module_region' : 'no_rf_module_region', matchCount: matches.length };
    },
  };
}

function resolveDeclaredType(node, module, sourceScope, index, raw, resolveMember, visited = new Set()) {
  if (!node) return null;
  const sourceText = expression => sourceScope.source.slice(expression.start, expression.end).replace(/\s+/g, '');
  if (node.type === 'MemberExpression') {
    const expression = sourceText(node);
    return KNOWN_ENGINE_BASES.has(expression) || expression.startsWith('cc.') || expression.startsWith('sp.') ? expression : null;
  }
  if (node.type === 'ArrayExpression' && node.elements.length === 1 && node.elements[0]) {
    const element = resolveDeclaredType(node.elements[0], module, sourceScope, index, raw, resolveMember, visited);
    if (element?.startsWith('__monkey_static_type_v1__:')) {
      try {
        const descriptor = JSON.parse(element.slice('__monkey_static_type_v1__:'.length));
        if (descriptor.kind === 'record') return serializedType({ kind: 'array', element: descriptor,
          sourceTypeExpression: module.source.slice(node.start, node.end).replace(/\s+/g, ''),
          sourceTypeBytes: { start: module.source_bytes.start + Buffer.byteLength(module.source.slice(0, node.start), 'utf8'),
            end: module.source_bytes.start + Buffer.byteLength(module.source.slice(0, node.end), 'utf8') } });
      } catch (_) { return null; }
    }
    return element ? `[${element}]` : null;
  }
  if (node.type !== 'Identifier') return null;
  const useOffset = module.source_bytes.start + Buffer.byteLength(module.source.slice(0, node.start), 'utf8');
  const key = `${node.name}:${useOffset}`;
  if (visited.has(key) || visited.size >= 16) return null;
  const next = new Set(visited); next.add(key);
  const binding = sourceScope.resolve(node.name, useOffset);
  if (binding.status !== 'resolved') return null;
  const value = binding.value;
  if (value?.type === 'Identifier') {
    const aliasModule = { ...module, source: sourceScope.source, source_bytes: { start: 0 } };
    return resolveDeclaredType(value, aliasModule, sourceScope, index, raw, resolveMember, next);
  }
  if (value?.type !== 'FunctionExpression' && value?.type !== 'ClassExpression' && value?.type !== 'CallExpression') return null;
  const located = sourceScope.moduleAt(binding.initializerBytes.start, index.modules);
  if (located.status !== 'resolved' || binding.initializerBytes.end > located.module.source_bytes.end) return null;
  const sourceType = sourceTypeOf(located.module);
  if (!sourceType) return null;
  const wrappedClass = value.type === 'CallExpression' ? value.callee : value;
  const localConstructors = new Set();
  if (wrappedClass?.type === 'FunctionExpression')
    for (const statement of wrappedClass.body?.body || [])
      if (statement.type === 'FunctionDeclaration' && statement.id?.type === 'Identifier') localConstructors.add(statement.id.name);
  else if (value.id?.type === 'Identifier') localConstructors.add(value.id.name);
  if (!localConstructors.size) return null;
  const moduleAst = acorn.parse(located.module.source, { ecmaVersion: 2020, sourceType: 'script' });
  let bareClassDecorator = false;
  walk(moduleAst, candidate => {
    if (candidate.type !== 'CallExpression' || candidate.arguments.length < 2
        || candidate.arguments[0]?.type !== 'ArrayExpression' || candidate.arguments[1]?.type !== 'Identifier'
        || !localConstructors.has(candidate.arguments[1].name)) return;
    if (candidate.arguments[0].elements.some(decorator => decorator?.type === 'Identifier')) bareClassDecorator = true;
  });
  if (!bareClassDecorator) {
    const record = inlineRecordSchema(value, binding, sourceScope, enumIndex(sourceScope.ast), resolveMember, next);
    return record ? serializedType(record) : null;
  }
  const siblings = index.modules.filter(candidate => sourceTypeOf(candidate) === sourceType);
  if (siblings.length !== 1) return null;
  const declaration = extractRecursive(siblings[0], sourceType, sourceScope, index, raw, new Set(), resolveMember);
  const chain = declaration.baseChain || [];
  const derivesComponent = chain.some(item => item.kind === 'engine_managed' && item.expression === 'cc.Component');
  return derivesComponent ? 'cc.Component' : null;
}

function propertyTypes(ast, constructorName, resolveType = null, source = null) {
  const output = new Map();
  walk(ast, node => {
    if (node.type !== 'CallExpression' || node.arguments.length < 3) return;
    const target = node.arguments[1], nameNode = node.arguments[2];
    if (target?.type !== 'MemberExpression' || target.computed || target.property.name !== 'prototype' || target.object.type !== 'Identifier' || target.object.name !== constructorName) return;
    if (nameNode.type !== 'Literal' || typeof nameNode.value !== 'string') return;
    const decorators = node.arguments[0];
    const expressions = decorators?.type === 'ArrayExpression' ? decorators.elements : [decorators];
    const types = [];
    for (const decorator of expressions) {
      if (!decorator) continue;
      const options = decorator.type === 'CallExpression' ? decorator.arguments[0] : null;
      if (!options) continue;
      if (options.type === 'ObjectExpression') {
        const typeProperty = options.properties.find(property => {
          const key = property.key?.type === 'Identifier' ? property.key.name : property.key?.type === 'Literal' ? property.key.value : null;
          return key === 'type' && property.type === 'Property' && property.kind === 'init' && !property.computed;
        });
        if (typeProperty) types.push(typeProperty.value);
      } else types.push(options);
    }
    if (types.length) output.set(nameNode.value, types.map(type => ({
      start: type.start, end: type.end, node: type,
      sourceExpression: source ? source.slice(type.start, type.end).replace(/\s+/g, '') : null,
      resolved: resolveType ? resolveType(type) : null,
    })));
  });
  return output;
}

function decoratedProperties(ast, constructorName) {
  const output = new Set();
  walk(ast, node => {
    if (node.type !== 'CallExpression' || node.arguments.length < 3) return;
    const target = node.arguments[1], nameNode = node.arguments[2];
    if (target?.type !== 'MemberExpression' || target.computed || target.property.name !== 'prototype'
        || target.object.type !== 'Identifier' || target.object.name !== constructorName) return;
    if (nameNode.type === 'Literal' && typeof nameNode.value === 'string') output.add(nameNode.value);
  });
  return output;
}

function accessorBackingFields(ast, constructorName, absoluteStart, byteOffset, resolveMember = null) {
  const output = new Map();
  const member = node => node?.type === 'MemberExpression' && !node.computed
    && node.object?.type === 'ThisExpression' && node.property?.type === 'Identifier'
    ? node.property.name : null;
  const descriptorValue = (descriptor, name) => descriptor?.type === 'ObjectExpression'
    ? descriptor.properties.find(property => property.type === 'Property' && !property.computed
      && (property.key.type === 'Identifier' ? property.key.name : property.key.type === 'Literal' ? property.key.value : null) === name)?.value
    : null;
  const accessorField = (fn, kind) => {
    if (!fn || !['FunctionExpression', 'ArrowFunctionExpression'].includes(fn.type)) return null;
    const body = fn.body;
    if (kind === 'get') {
      const statements = body.type === 'BlockStatement' ? body.body : [];
      if (statements.length !== 1 || statements[0].type !== 'ReturnStatement') return null;
      return member(statements[0].argument);
    }
    const statements = body.type === 'BlockStatement' ? body.body : [];
    if (fn.params?.length !== 1 || fn.params[0].type !== 'Identifier' || !statements.length
        || statements.some(statement => statement.type !== 'ExpressionStatement')) return null;
    const expressions = statements.flatMap(statement => statement.expression.type === 'SequenceExpression'
      ? statement.expression.expressions : [statement.expression]);
    const assignments = expressions.filter(expression => expression.type === 'AssignmentExpression');
    if (assignments.length !== 1) return null;
    const expression = assignments[0];
    return expression.operator === '=' && expression.right.type === 'Identifier'
      && expression.right.name === fn.params[0].name ? member(expression.left) : null;
  };
  walk(ast, node => {
    if (node.type !== 'CallExpression' || node.callee?.type !== 'MemberExpression'
        || node.callee.object?.type !== 'Identifier' || node.callee.object.name !== 'Object'
        || node.callee.property?.name !== 'defineProperty' || node.arguments.length < 3) return;
    const target = node.arguments[0], nameNode = node.arguments[1], descriptor = node.arguments[2];
    if (target?.type !== 'MemberExpression' || target.computed || target.property.name !== 'prototype'
        || target.object?.type !== 'Identifier' || target.object.name !== constructorName
        || nameNode?.type !== 'Literal' || typeof nameNode.value !== 'string') return;
    const getter = descriptorValue(descriptor, 'get'), setter = descriptorValue(descriptor, 'set');
    const getField = accessorField(getter, 'get'), setField = accessorField(setter, 'set');
    // A decorated accessor is a source property backed by one private field only
    // when both direct accessors agree exactly; computed/compound behavior stays unsupported.
    if (!getField || getField !== setField) return;
    output.set(getField, { propertyName: nameNode.value, backingFieldName: getField,
      sourceBytes: { start: absoluteStart + byteOffset(node.start), end: absoluteStart + byteOffset(node.end) } });
  });
  return output;
}

function constantAccessorDefaults(ast, constructorName, source, absoluteStart, byteOffset, resolveMember = null) {
  const output = new Map();
  const descriptorValue = (descriptor, name) => descriptor?.type === 'ObjectExpression'
    ? descriptor.properties.find(property => property.type === 'Property' && !property.computed
      && (property.key.type === 'Identifier' ? property.key.name : property.key.type === 'Literal' ? property.key.value : null) === name)?.value
    : null;
  walk(ast, node => {
    if (node.type !== 'CallExpression' || node.callee?.type !== 'MemberExpression'
        || node.callee.object?.type !== 'Identifier' || node.callee.object.name !== 'Object'
        || node.callee.property?.name !== 'defineProperty' || node.arguments.length < 3) return;
    const target = node.arguments[0], nameNode = node.arguments[1], descriptor = node.arguments[2];
    if (target?.type !== 'MemberExpression' || target.computed || target.property.name !== 'prototype'
        || target.object?.type !== 'Identifier' || target.object.name !== constructorName
        || nameNode?.type !== 'Literal' || typeof nameNode.value !== 'string') return;
    const getter = descriptorValue(descriptor, 'get'), setter = descriptorValue(descriptor, 'set');
    if (!getter || !setter || !['FunctionExpression', 'ArrowFunctionExpression'].includes(getter.type)
        || !['FunctionExpression', 'ArrowFunctionExpression'].includes(setter.type)) return;
    const statements = getter.body.type === 'BlockStatement' ? getter.body.body : [];
    if (statements.length !== 1 || statements[0].type !== 'ReturnStatement'
        || setter.body.type !== 'BlockStatement' || setter.body.body.length !== 0) return;
    const expression = statements[0].argument, evaluated = constant(expression, resolveMember);
    if (!evaluated.ok) return;
    output.set(nameNode.value, {
      name: nameNode.value, kind: evaluated.kind, value: evaluated.value,
      sourceBytes: { start: absoluteStart + byteOffset(node.start), end: absoluteStart + byteOffset(node.end) },
      rhsBytes: { start: absoluteStart + byteOffset(expression.start), end: absoluteStart + byteOffset(expression.end) },
      expressionSha256: digest(Buffer.from(source.slice(expression.start, expression.end), 'utf8')),
      ...(evaluated.resolution ? { constantResolution: evaluated.resolution } : {}),
      ...(evaluated.sourceConstant ? { sourceConstant: evaluated.sourceConstant } : {}),
    });
  });
  return output;
}

function enumValuesFor(node, tables) {
  let target = node;
  if (target?.type === 'CallExpression' && target.callee?.type === 'MemberExpression'
      && target.callee.object.type === 'Identifier' && target.callee.object.name === 'cc'
      && target.callee.property.name === 'Enum') target = target.arguments[0];
  const key = target?.type === 'Identifier' ? target.name
    : target?.type === 'MemberExpression' && !target.computed
      ? `${target.object.name || ''}.${target.property.name}` : null;
  if (!key) return [];
  const table = tables.exact.get(key) || tables.leaf.get(key.split('.').pop());
  return table ? [...table.entries()].map(([name, value]) => ({ name, value })) : [];
}

function inlineRecordSchema(value, binding, sourceScope, tables, resolveMember, visited) {
  if (value?.type !== 'CallExpression' || value.callee?.type !== 'FunctionExpression') return null;
  const constructors = (value.callee.body?.body || []).filter(item => item.type === 'FunctionDeclaration' && item.id?.type === 'Identifier');
  if (constructors.length !== 1) return null;
  const constructor = constructors[0], constructorName = constructor.id.name;
  let className = null, markerCount = 0;
  walk(value, node => {
    if (node.type !== 'CallExpression' || node.arguments.length < 2
        || node.arguments[1]?.type !== 'Identifier' || node.arguments[1].name !== constructorName
        || node.arguments[0]?.type !== 'ArrayExpression') return;
    for (const decorator of node.arguments[0].elements || []) {
      if (decorator?.type === 'CallExpression' && decorator.arguments[0]?.type === 'Literal'
          && typeof decorator.arguments[0].value === 'string') {
        className = decorator.arguments[0].value; markerCount++;
      }
    }
  });
  if (markerCount !== 1 || !className) return null;
  const fullSource = sourceScope.source;
  const byteOffset = offset => Buffer.byteLength(fullSource.slice(0, offset), 'utf8');
  const assignments = directAssignments(constructor, 'this', fullSource, 0, byteOffset);
  const defaults = new Map();
  for (const assignment of assignments) {
    if (assignment.expression.operator !== '=') return null;
    const constantValue = constant(assignment.rhs, resolveMember);
    if (!constantValue.ok) return null;
    defaults.set(assignment.name, { kind: constantValue.kind, value: constantValue.value,
      sourceBytes: assignment.sourceBytes, rhsBytes: assignment.rhsBytes,
      expressionSha256: digest(Buffer.from(fullSource.slice(assignment.rhs.start, assignment.rhs.end), 'utf8')) });
  }
  const baseContext = { ...sourceScope, source: fullSource, source_bytes: { start: 0 } };
  const declarations = propertyTypes(value, constructorName, node =>
    resolveDeclaredType(node, baseContext, sourceScope, { modules: [] }, Buffer.alloc(0), resolveMember, visited), fullSource);
  const fields = [];
  for (const [name, ranges] of declarations) {
    if (ranges.length !== 1) return null;
    const range = ranges[0], typeNode = range.node;
    const expression = fullSource.slice(range.start, range.end).replace(/\s+/g, '');
    const declared = range.resolved || expression;
    const defaultValue = defaults.get(name);
    if (!defaultValue) return null;
    let kind = null;
    if (expression.startsWith('cc.Enum(')) kind = 'enum';
    else if (['cc.Boolean','Boolean','boolean'].includes(declared)) kind = 'bool';
    else if (['cc.Float','Float','Number','number','cc.Integer','Integer'].includes(declared)) kind = 'float';
    else if (['cc.String','String','string'].includes(declared)) kind = 'string';
    else if (declared === 'cc.Node') kind = 'node_ref';
    else if (declared === 'cc.SpriteFrame' || declared === 'cc.Asset' || _isDeclaredAsset(declared)) kind = 'asset_ref';
    else if (declared === 'cc.Component' || declared.startsWith('cc.') || declared.startsWith('sp.')) kind = 'component_ref';
    if (!kind) return null;
    if (kind === 'enum' && defaultValue.kind !== 'number') return null;
    const fieldKind = defaultValue.kind === 'null' ? 'null' : kind === 'enum' ? 'float' : kind;
    if (fieldKind === 'null' && !['node_ref','asset_ref','component_ref'].includes(kind)) return null;
    fields.push({ name, kind: fieldKind, value: defaultValue.value, sourceDeclaredType: declared,
      defaultEvidence: defaultValue, enumValues: kind === 'enum' ? enumValuesFor(typeNode, tables) : [] });
  }
  if (!fields.length) return null;
  return { kind: 'record', name: className, fields,
    sourceModuleBytes: binding.initializerBytes, sourceInitializerSha256: binding.initializerSha256 };
}

function _isDeclaredAsset(type) {
  return new Set(['cc.SpriteFrame','cc.Texture2D','cc.AudioClip','cc.Prefab','cc.SpriteAtlas','cc.Font','cc.Material','cc.AnimationClip','cc.JsonAsset','cc.TextAsset']).has(type);
}

function serializedType(descriptor) {
  return '__monkey_static_type_v1__:' + JSON.stringify(descriptor);
}

function analyzeModule(module, raw, sourceScope, index, resolveMember = null) {
  if (acorn.version !== '8.15.0') fail('DEPENDENCY_VERSION', 'Pinned Acorn 8.15.0 required');
  const ast = acorn.parse(module.source, { ecmaVersion: 2020, sourceType: 'script' });
  const byteOffset = offset => Buffer.byteLength(module.source.slice(0, offset), 'utf8');
  const absoluteStart = module.source_bytes.start;
  const constructors = [];
  walk(ast, (node, parents) => {
    if (!['FunctionDeclaration', 'FunctionExpression'].includes(node.type)) return;
    const enclosingFunction = [...parents].reverse().find(parent => ['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'].includes(parent.type));
    // A Cocos RF class constructor is a direct declaration in the RF factory.
    // Excluding nested functions prevents closure/setter assignments from
    // being mistaken for constructor defaults.
    if (!enclosingFunction || enclosingFunction.body?.body?.includes(node) !== true) return;
    const alias = constructorAlias(node);
    if (!alias) return;
    const assignments = directAssignments(node, alias, module.source, absoluteStart, byteOffset);
    if (assignments.length) {
      let inheritsFrom = false;
      const constructorName = node.id?.name;
      if (constructorName) walk(enclosingFunction.body, candidate => {
        if (candidate.type === 'CallExpression' && candidate.arguments.length >= 2
            && candidate.arguments[0]?.type === 'Identifier' && candidate.arguments[0].name === constructorName)
          inheritsFrom = true;
      });
      constructors.push({ node, alias, assignments, enclosingFunction, inheritsFrom });
    }
  });
  const inheriting = constructors.filter(item => item.inheritsFrom);
  if (inheriting.length) constructors.splice(0, constructors.length, ...inheriting);
  if (constructors.length !== 1) return {
    fields: [], propertyTypes: [], gaps: [{ kind: constructors.length ? 'ambiguous_constructor' : 'constructor_not_identified', candidateCount: constructors.length }],
  };
  const selected = constructors[0];
  const name = selected.node.id?.name || null;
  const declaredTypes = name ? propertyTypes(ast, name, typeNode =>
    resolveDeclaredType(typeNode, module, sourceScope, index, raw, resolveMember), module.source) : new Map();
  const decoratedNames = name ? decoratedProperties(ast, name) : new Set();
  const accessorFields = name ? accessorBackingFields(ast, name, absoluteStart, byteOffset, resolveMember) : new Map();
  const accessorDefaults = name ? constantAccessorDefaults(ast, name, module.source, absoluteStart, byteOffset, resolveMember) : new Map();
  const sourceFieldName = fieldName => accessorFields.get(fieldName)?.propertyName || fieldName;
  const isDeclaredField = fieldName => decoratedNames.has(sourceFieldName(fieldName));
  const ordered = new Map();
  const runtimeFields = [];
  const gaps = [];
  const acceptedAssignments = new Set(selected.assignments.map(item => item.expression));
  for (const assignment of selected.assignments) {
    if (!isDeclaredField(assignment.name)) {
      runtimeFields.push({ name: assignment.name, reason: 'undecorated_constructor_assignment',
        sourceBytes: assignment.sourceBytes, rhsBytes: assignment.rhsBytes,
        expressionSha256: digest(Buffer.from(module.source.slice(assignment.rhs.start, assignment.rhs.end), 'utf8')) });
      continue;
    }
    if (assignment.expression.operator !== '=') {
      gaps.push({ kind: 'non_simple_assignment', name: assignment.name, sourceBytes: assignment.sourceBytes });
      ordered.delete(assignment.name);
      continue;
    }
    const evaluated = constant(assignment.rhs, resolveMember);
    if (!evaluated.ok) {
      gaps.push({ kind: 'non_constant_constructor_assignment', name: assignment.name, reason: evaluated.reason, sourceBytes: assignment.sourceBytes });
      ordered.delete(assignment.name);
      continue;
    }
    const rhs = Buffer.from(module.source.slice(assignment.rhs.start, assignment.rhs.end), 'utf8');
    const accessor = accessorFields.get(assignment.name);
    ordered.set(sourceFieldName(assignment.name), {
      name: sourceFieldName(assignment.name),
      kind: evaluated.kind,
      value: evaluated.value,
      owner: name || 'constructor',
      sourceBytes: assignment.sourceBytes,
      rhsBytes: assignment.rhsBytes,
      expressionSha256: digest(rhs),
      ...(evaluated.resolution ? { constantResolution: evaluated.resolution } : {}),
      ...(evaluated.sourceConstant ? { sourceConstant: evaluated.sourceConstant } : {}),
      ...(accessor ? { accessorBacking: { propertyName: accessor.propertyName,
        backingFieldName: accessor.backingFieldName, sourceBytes: accessor.sourceBytes } } : {}),
    });
  }
  for (const [propertyName, value] of accessorDefaults) {
    if (!decoratedNames.has(propertyName) || ordered.has(propertyName)) continue;
    const { name: _name, ...evidence } = value;
    ordered.set(propertyName, { ...evidence, name: propertyName, owner: name || 'constructor',
      accessorDefault: 'pure_constant_getter_and_noop_setter' });
  }
  for (const item of nestedAssignments(selected.node, selected.alias, acceptedAssignments)) {
    if (!isDeclaredField(item.name)) {
      runtimeFields.push({ name: item.name, reason: 'undecorated_non_direct_constructor_assignment',
        sourceBytes: { start: absoluteStart + byteOffset(item.node.start), end: absoluteStart + byteOffset(item.node.end) },
        expressionSha256: digest(Buffer.from(module.source.slice(item.node.start, item.node.end), 'utf8')) });
      continue;
    }
    gaps.push({ kind: 'non_direct_constructor_assignment', name: item.name });
    ordered.delete(sourceFieldName(item.name));
  }
  const baseCalls = [];
  walk(ast, node => {
    if (node.type !== 'CallExpression') return;
    let containsFactory = false;
    walk(node.callee, candidate => { if (candidate === selected.enclosingFunction) containsFactory = true; });
    if (containsFactory) baseCalls.push(node);
  });
  const baseCall = baseCalls.length === 1 ? baseCalls[0] : null;
  const baseExpression = baseCall?.arguments?.[0] || null;
  if (baseCalls.length !== 1) gaps.push({ kind: baseCalls.length ? 'ambiguous_class_factory_call' : 'class_factory_call_not_found', matchCount: baseCalls.length });
  const fields = [...ordered.values()];
  const runtimeEvidence = runtimeFields.map(field => ({ ...field, sourceType: sourceTypeOf(module),
    sourceModule: name || null, sourceSha256: module.sha256 }));
  const propertyTypeRows = [];
  for (const [propertyName, ranges] of declaredTypes) {
    const types = ranges.map(range => range.resolved || module.source.slice(range.start, range.end));
    const row = { name: propertyName, types: [...new Set(types)] };
    const aliasEvidence = ranges.filter(range => range.resolved && range.sourceExpression && range.resolved !== range.sourceExpression)
      .map(range => ({ sourceExpression: range.sourceExpression, resolvedType: range.resolved,
        sourceBytes: { start: absoluteStart + byteOffset(range.start), end: absoluteStart + byteOffset(range.end) },
        resolution: range.resolved === 'cc.Component' ? 'unique_source_class_with_verified_cc_Component_base' : 'static_alias_resolution' }));
    if (aliasEvidence.length) row.typeAliasEvidence = aliasEvidence;
    propertyTypeRows.push(row);
  }
  return {
    fields,
    propertyTypes: propertyTypeRows,
    decoratedProperties: [...decoratedNames].sort().map(propertyName => ({ name: propertyName,
      types: (declaredTypes.get(propertyName) || []).map(range => range.resolved || module.source.slice(range.start, range.end)) })),
    runtimeFields: runtimeEvidence,
    gaps,
    constructorName: name,
    baseExpression: baseExpression ? module.source.slice(baseExpression.start, baseExpression.end) : null,
    baseExpressionBytes: baseExpression ? { start: absoluteStart + byteOffset(baseExpression.start), end: absoluteStart + byteOffset(baseExpression.end) } : null,
    baseExpressionType: baseExpression?.type || null,
    baseExpressionName: baseExpression?.type === 'Identifier' ? baseExpression.name : null,
    _baseExpressionNode: baseExpression,
  };
}

function sourceTypeOf(module) {
  const identities = (module.rf || []).filter(row => row.status === 'literal_syntax' && typeof row.identity === 'string');
  return identities.length === 1 ? identities[0].identity : null;
}

function resolveBaseExpression(node, module, sourceType, sourceScope, index, raw, visitedAliases, resolveMember) {
  const localByteOffset = offset => Buffer.byteLength(module.source.slice(0, offset), 'utf8');
  if (node.type === 'MemberExpression') {
    const expression = module.source.slice(node.start, node.end).replace(/\s+/g, '');
    if (KNOWN_ENGINE_BASES.has(expression)) return { status: 'engine_managed', expression, baseChain: [{ kind: 'engine_managed', expression }] };
    return { status: 'unresolved', reason: 'non_identifier_base_expression', expression };
  }
  if (node.type !== 'Identifier') return { status: 'unresolved', reason: 'dynamic_base_expression', expression: module.source.slice(node.start, node.end) };
  const absoluteUse = module.source_bytes.start + localByteOffset(node.start);
  const key = `${sourceType}:${node.name}:${absoluteUse}`;
  if (visitedAliases.has(key)) return { status: 'unresolved', reason: 'base_alias_cycle', alias: node.name };
  if (visitedAliases.size >= 16) return { status: 'unresolved', reason: 'base_alias_depth_limit', alias: node.name };
  const nextAliases = new Set(visitedAliases); nextAliases.add(key);
  const binding = sourceScope.resolve(node.name, absoluteUse);
  if (binding.status !== 'resolved') return { status: 'unresolved', reason: binding.status, alias: node.name, binding };
  const value = binding.value;
  if (value.type === 'MemberExpression') {
    const expression = sourceScope.source.slice(value.start, value.end).replace(/\s+/g, '');
    if (KNOWN_ENGINE_BASES.has(expression)) return { status: 'engine_managed', expression, alias: node.name, bindingBytes: binding.initializerBytes, baseChain: [{ kind: 'engine_managed', expression }] };
    return { status: 'unresolved', reason: 'unrecognized_member_base', alias: node.name, expression };
  }
  if (value.type === 'Identifier') {
    const aliasContext = { ...module, source: sourceScope.source, source_bytes: { start: 0 } };
    const nested = resolveBaseExpression(value, aliasContext, sourceType, sourceScope, index, raw, nextAliases, resolveMember);
    return { ...nested, alias: node.name, bindingBytes: binding.initializerBytes, aliasChain: [node.name, ...(nested.aliasChain || [])] };
  }
  const initializerStart = binding.initializerBytes.start;
  const initializerEnd = binding.initializerBytes.end;
  const located = sourceScope.moduleAt(initializerStart, index.modules);
  if (located.status !== 'resolved') return { status: 'unresolved', reason: located.status, alias: node.name, bindingBytes: binding.initializerBytes, matchCount: located.matchCount };
  const parentModule = located.module;
  if (initializerEnd > parentModule.source_bytes.end) return { status: 'unresolved', reason: 'initializer_crosses_rf_region', alias: node.name, bindingBytes: binding.initializerBytes };
  const parentType = sourceTypeOf(parentModule);
  if (!parentType) return { status: 'unresolved', reason: 'parent_rf_identity_not_unique', alias: node.name, bindingBytes: binding.initializerBytes };
  const sameRfModules = index.modules.filter(candidate => sourceTypeOf(candidate) === parentType);
  if (sameRfModules.length !== 1) return { status: 'unresolved', reason: 'parent_rf_identity_ambiguous', alias: node.name, parentSourceType: parentType, matchCount: sameRfModules.length };
  const parent = extractRecursive(parentModule, parentType, sourceScope, index, raw, nextAliases, resolveMember);
  const route = {
    kind: 'source_rf', alias: node.name, sourceType: parentType, moduleName: parentModule.rf.find(row => row.identity === parentType).class_name,
    moduleSha256: parentModule.sha256, moduleSourceBytes: parentModule.source_bytes,
    bindingBytes: binding.initializerBytes, bindingSha256: binding.initializerSha256,
  };
  return {
    status: parent.gaps.length ? 'partial_source_rf' : 'resolved_source_rf',
    alias: node.name,
    bindingBytes: binding.initializerBytes,
    parentSourceType: parentType,
    parent,
    baseChain: [route, ...(parent.baseChain || [])],
  };
}

function extractRecursive(module, sourceType, sourceScope, index, raw, visitedTypes, resolveMember) {
  if (visitedTypes.size >= 16) return { fields: [], propertyTypes: [], gaps: [{ kind: 'base_depth_limit', maxDepth: 16 }], baseChain: [] };
  if (visitedTypes.has(sourceType)) return { fields: [], propertyTypes: [], gaps: [{ kind: 'base_cycle_detected', sourceType }], baseChain: [] };
  const nextTypes = new Set(visitedTypes); nextTypes.add(sourceType);
  const own = analyzeModule(module, raw, sourceScope, index, resolveMember);
  const ownGaps = [...own.gaps];
  let base = null;
  let baseResolution = { kind: 'root', expression: null };
  if (own._baseExpressionNode) {
    base = resolveBaseExpression(own._baseExpressionNode, module, sourceType, sourceScope, index, raw, new Set(), resolveMember);
    baseResolution = { kind: base.status, expression: own.baseExpression, sourceBytes: own.baseExpressionBytes, alias: base.alias, reason: base.reason, parentSourceType: base.parentSourceType, baseChain: base.baseChain || [] };
    if (base.status === 'unresolved') ownGaps.push({ kind: 'base_class_unresolved', expression: own.baseExpression, sourceBytes: own.baseExpressionBytes, reason: base.reason, alias: base.alias });
  } else if (own.gaps.some(gap => gap.kind === 'class_factory_call_not_found' || gap.kind === 'ambiguous_class_factory_call')) {
    baseResolution = { kind: 'unresolved', expression: null };
  }
  const parent = base?.parent || null;
  const fields = new Map((parent?.fields || []).map(field => [field.name, field]));
  for (const field of own.fields) fields.set(field.name, { ...field, sourceType, sourceModule: own.moduleName || module.rf.find(row => row.identity === sourceType)?.class_name || null, sourceSha256: module.sha256 });
  const types = new Map((parent?.propertyTypes || []).map(row => [row.name, row]));
  for (const row of own.propertyTypes) types.set(row.name, row);
  const decorated = new Map((parent?.decoratedProperties || []).map(row => [row.name, row]));
  for (const row of own.decoratedProperties || []) decorated.set(row.name, row);
  const { _baseExpressionNode, ...publicOwn } = own;
  return {
    ...publicOwn,
    fields: [...fields.values()],
    propertyTypes: [...types.values()],
    decoratedProperties: [...decorated.values()],
    runtimeFields: [...(parent?.runtimeFields || []), ...(own.runtimeFields || [])],
    gaps: [...(parent?.gaps || []), ...ownGaps],
    baseResolution,
    baseChain: base?.baseChain || [],
  };
}

function main() {
  const [sourcePath, expectedSha256, sourceTypesJson] = process.argv.slice(2);
  if (!sourcePath || !expectedSha256 || !sourceTypesJson) fail('INVALID_ARGUMENTS', 'Expected source path, expected SHA-256, and JSON source type list');
  const sourceTypes = JSON.parse(sourceTypesJson);
  if (!Array.isArray(sourceTypes) || sourceTypes.some(type => typeof type !== 'string' || !type.trim())) fail('INVALID_SOURCE_TYPES', 'source types must be non-empty strings');
  const uniqueTypes = [...new Set(sourceTypes)];
  const raw = fs.readFileSync(sourcePath);
  const sourceSha256 = digest(raw);
  if (!/^[a-f0-9]{64}$/.test(expectedSha256) || sourceSha256 !== expectedSha256) fail('SOURCE_SHA256_MISMATCH', 'Source SHA-256 does not match expected value');
  const indexer = require.resolve('./sources/index-modules.cjs');
  const indexed = spawnSync(process.execPath, [indexer, 'rf-regions-v1'], { input: raw, maxBuffer: 128 * 1024 * 1024, encoding: 'utf8' });
  if (indexed.error || indexed.status !== 0) fail('MODULE_INDEX_FAILED', indexed.error?.message || indexed.stderr || 'RF source indexing failed');
  const index = JSON.parse(indexed.stdout);
  if (index.error) fail(index.error.code || 'MODULE_INDEX_FAILED', index.error.message || 'RF source indexing failed');
  if (index.source?.sha256 !== sourceSha256) fail('MODULE_INDEX_SOURCE_HASH_MISMATCH', 'RF indexer did not report the exact verified input source hash');
  const source = raw.toString('utf8');
  let sourceScope;
  try { sourceScope = buildScopeIndex(source); }
  catch (error) { fail('SCOPE_INDEX_FAILED', error.message); }
  const resolveMember = enumMemberResolver(enumIndex(sourceScope.ast));
  const components = Object.create(null), diagnostics = [];
  for (const sourceType of uniqueTypes) {
    const matches = index.modules.filter(module => (module.rf || []).some(item => item.status === 'literal_syntax' && item.identity === sourceType));
    if (matches.length !== 1) {
      components[sourceType] = { fields: [], propertyTypes: [], gaps: [{ kind: matches.length ? 'ambiguous_rf_module' : 'rf_module_not_found', matchCount: matches.length }], sourceBytes: null, sourceSha256: null };
      diagnostics.push({ code: matches.length ? 'AMBIGUOUS_RF_MODULE' : 'RF_MODULE_NOT_FOUND', sourceType, matchCount: matches.length });
      continue;
    }
    const module = matches[0];
    try {
      const result = extractRecursive(module, sourceType, sourceScope, index, raw, new Set(), resolveMember);
      components[sourceType] = {
        ...result,
        sourceBytes: module.source_bytes,
        sourceSha256: module.sha256,
        moduleName: module.rf.find(item => item.identity === sourceType).class_name,
      };
      if (result.gaps.length) diagnostics.push({ code: 'PARTIAL_DECLARATIONS', sourceType, gapCount: result.gaps.length });
    } catch (error) {
      components[sourceType] = { fields: [], propertyTypes: [], gaps: [{ kind: 'module_parse_failed', message: error.message }], sourceBytes: module.source_bytes, sourceSha256: module.sha256 };
      diagnostics.push({ code: error.code || 'MODULE_PARSE_FAILED', sourceType, message: error.message });
    }
  }
  return { components, diagnostics };
}

try { process.stdout.write(JSON.stringify(main())); }
catch (error) { process.stdout.write(JSON.stringify({ components: {}, diagnostics: [{ code: error.code || 'STATIC_DECLARATION_ERROR', message: error.message }] })); process.exitCode = 1; }
