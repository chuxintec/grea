"""Typed, fail-closed lowering of selected source ASTs to ordinary C#.

Types are explicit call-domain evidence, not an assertion that dynamic JS has
these types for every possible caller. No source text or supplied C# is emitted.
"""
from dataclasses import dataclass
import json
import re

from .sources.compiled import fail
from .code_emit import name


@dataclass(frozen=True)
class Type:
    kind: str
    args: tuple = ()

    def cs(self):
        builtins = {'Number': 'double', 'Index': 'int', 'Boolean': 'bool', 'String': 'string', 'Void': 'void'}
        containers = {'List': 'List', 'Map': 'OrderedMap', 'Set': 'OrderedSet', 'Optional': 'Optional', 'Action': 'Action'}
        if self.kind in builtins:
            return builtins[self.kind]
        if self.kind in containers:
            return containers[self.kind] + '<' + ', '.join(t.cs() for t in self.args) + '>'
        if self.kind == 'Function':
            return ('Action<' + ', '.join(t.cs() for t in self.args[:-1]) + '>') if self.args[-1] == VOID else 'Func<' + ', '.join(t.cs() for t in self.args) + '>'
        return name(self.kind)


NUMBER, INDEX, BOOL, STRING, VOID = (Type(s) for s in ('Number', 'Index', 'Boolean', 'String', 'Void'))
NULL, UNDEFINED = Type('Null'), Type('Undefined')


def parse_type(text, records):
    if not isinstance(text, str) or len(text) > 256:
        fail('CODE_TYPE', str(text), 'Expected bounded explicit type')
    tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*|[<>,]', text)
    if ''.join(tokens) != text:
        fail('CODE_TYPE', text, 'Unsupported type grammar')
    pos = 0

    def parse(depth=0):
        nonlocal pos
        if depth > 8 or pos >= len(tokens):
            fail('CODE_TYPE', text, 'Invalid nested type')
        kind = tokens[pos]; pos += 1
        args = []
        if pos < len(tokens) and tokens[pos] == '<':
            pos += 1; args.append(parse(depth + 1))
            while pos < len(tokens) and tokens[pos] == ',':
                pos += 1; args.append(parse(depth + 1))
            if pos >= len(tokens) or tokens[pos] != '>':
                fail('CODE_TYPE', text, 'Unclosed type')
            pos += 1
        arity = {'List': 1, 'Map': 2, 'Set': 1, 'Optional': 1, 'Action': 1}
        if kind in arity:
            if len(args) != arity[kind]: fail('CODE_TYPE', text, 'Wrong type arity')
            if any(a.kind=='Void' for a in args): fail('CODE_TYPE', text, 'Void is not a data/parameter type')
        elif kind == 'Function':
            if not args: fail('CODE_TYPE', text, 'Function needs a return type')
        elif kind not in {'Number', 'Index', 'Boolean', 'String', 'Void', *records} or args:
            fail('CODE_TYPE', text, 'Unknown type or unsupported generic')
        return Type(kind, tuple(args))
    result = parse()
    if pos != len(tokens): fail('CODE_TYPE', text, 'Trailing type syntax')
    return result


def property_name(node):
    if node.get('type') != 'MemberExpression' or node.get('computed'):
        return None
    return node['property'].get('name')


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


class Lowerer:
    def __init__(self, module, method, ast, context):
        self.module, self.method, self.ast, self.context = module, method, ast, context
        self.types = {}; self.names = {}; self.used = set(); self.locals = {}; self.function_self = {}
        self.return_type = method['_return']; self.nullish_guard = False
        self.this_allowed = True
        for i, param in enumerate(ast['params']):
            self.bind(param, method['_params'][i])
        for node in walk(ast):
            if node.get('type') == 'VariableDeclarator':
                key = node['id'].get('bindingId')
                text = method.get('locals', {}).get(key, method.get('locals', {}).get(node['id'].get('name')))
                if text:
                    self.bind(node['id'], parse_type(text, context['record_types']))
        self.infer_locals(ast['body'])

    def error(self, node, message):
        fail('CODE_SEMANTIC_UNSUPPORTED', self.method['id'] + ':' + str(node.get('start', '?')), message)

    def bind(self, node, typ, preferred=None):
        key = node.get('bindingId')
        if node.get('bindingAmbiguous') or not key:
            self.error(node, 'Ambiguous/destructured binding requires exact lexical evidence')
        if key in self.types:
            if self.types[key] != typ: self.error(node, 'Conflicting types for lexical binding')
            return self.names[key]
        base = preferred or node.get('name', 'item')
        try: name(base)
        except Exception: base = 'item'
        target = base; counter = 2
        while target in self.used:
            target = base + str(counter); counter += 1
        self.types[key] = typ; self.names[key] = target; self.used.add(target)
        return target

    def infer_locals(self, block):
        # Function locals retain exact binding IDs; no name-based capture lookup.
        for statement in block.get('body', []):
            if statement['type'] != 'VariableDeclaration': continue
            for declaration in statement['declarations']:
                node, init = declaration['id'], declaration.get('init')
                if node.get('bindingId') in self.types: continue
                if init and init['type'] not in ('FunctionExpression', 'ArrowFunctionExpression', 'ArrayExpression', 'NewExpression'):
                    self.bind(node, self.expr(init)[1])
                elif init and init['type'] == 'NewExpression' and init['callee'].get('name') in ('Map', 'Set'):
                    self.error(node, 'Empty collection requires an explicit local type')
                elif not init:
                    assignments = [n for n in walk(block) if n.get('type') == 'AssignmentExpression' and n['left'].get('bindingId') == node.get('bindingId')]
                    if not assignments: self.error(node, 'Uninitialized variable type is unknown')
                    inferred = {self.expr(n['right'])[1] for n in assignments}
                    if len(inferred) != 1: self.error(node, 'Conflicting assigned types')
                    self.bind(node, next(iter(inferred)))
                else:
                    self.error(node, 'Collection/function locals require an explicit call-domain type')

    def coerce(self, value, actual, expected, node):
        if expected is None or actual == expected: return value
        if actual == INDEX and expected == NUMBER: return '(double)(' + value + ')'
        if expected.kind == 'Optional' and expected.args[0] == actual:
            return 'new ' + expected.cs() + '(' + value + ')'
        self.error(node, 'Cannot coerce ' + str(actual) + ' to ' + str(expected))

    def truth(self, value, typ, node):
        if typ == BOOL: return value
        if typ in (NUMBER, INDEX): return 'NumberMath.Truth(' + value + ')'
        if typ == STRING: return '!string.IsNullOrEmpty(' + value + ')'
        if typ.kind == 'Optional' and typ.args[0] == NUMBER: return 'NumberMath.Truth(NumberMath.NumberOrNaN(' + value + '))'
        if typ.kind == 'Optional': return '(' + value + ').HasValue'
        if typ.kind == 'Action': return '(' + value + ' != null)'
        self.error(node, 'Truthiness outside declared non-null typed call domain')

    def expr(self, node, expected=None):
        code, typ = self.expression(node, expected)
        return self.coerce(code, typ, expected, node), expected or typ

    def expression(self, node, expected=None):
        kind = node['type']
        if kind == 'Literal':
            value = node.get('value')
            if value is None: return 'null', NULL
            if type(value) is bool: return 'true' if value else 'false', BOOL
            if type(value) is int and expected == INDEX and -2147483648 <= value <= 2147483647: return str(value), INDEX
            if type(value) in (int, float): return repr(value) + 'd', NUMBER
            if isinstance(value, str): return json.dumps(value, ensure_ascii=True), STRING
            self.error(node, 'Regex/BigInt/nonliteral value unsupported')
        if kind == 'Identifier':
            key = node.get('bindingId')
            if key in self.types: return self.names[key], self.types[key]
            if key in self.context['aliases']:
                return self.context['aliases'][key]['targetClass'], Type('Class')
            self.error(node, 'Unresolved or untyped lexical reference: ' + node['name'])
        if kind == 'ThisExpression':
            if not self.this_allowed: self.error(node,'Dynamic this inside ordinary source callback is not lexical this')
            return (self.module['targetClass'], Type('Class')) if self.method['_static'] else ('this', Type(self.module['targetClass']))
        if kind == 'ArrayExpression':
            if expected is None or expected.kind != 'List': self.error(node, 'Array element type unknown')
            items = [self.expr(v, expected.args[0])[0] if v else self.error(node, 'Sparse arrays unsupported') for v in node['elements']]
            return 'new ' + expected.cs() + ' { ' + ', '.join(items) + ' }', expected
        if kind == 'ObjectExpression':
            if expected is None or expected.kind not in self.context['records']: self.error(node, 'Record shape unknown')
            fields = self.context['records'][expected.kind]; given = {}
            for p in node['properties']:
                if p.get('type') != 'Property' or p.get('computed') or p.get('kind') != 'init' or p.get('method'):
                    self.error(p, 'Dynamic record property unsupported')
                key = p['key'].get('name')
                if key not in fields or key in given: self.error(p, 'Duplicate/unknown record property')
                given[key] = self.expr(p['value'], fields[key])[0]
            if set(given) != set(fields): self.error(node, 'Incomplete record: default fields would alter source')
            return 'new ' + expected.cs() + ' { ' + ', '.join(k + ' = ' + v for k, v in given.items()) + ' }', expected
        if kind == 'NewExpression':
            if expected is None or expected.kind not in ('Map', 'Set', 'List') or node['arguments']:
                self.error(node, 'Only explicitly typed empty data collections are supported')
            if node['callee'].get('bindingId') or node['callee'].get('name') != {'Map': 'Map', 'Set': 'Set', 'List': 'Array'}[expected.kind]:
                self.error(node, 'Shadowed or mismatching collection constructor')
            return 'new ' + expected.cs() + '()', expected
        if kind == 'MemberExpression':
            base, typ = self.expr(node['object']); prop = property_name(node)
            if node.get('computed'):
                if typ.kind != 'List': self.error(node, 'Dynamic property access unsupported')
                index, it = self.expr(node['property'])
                if it != INDEX: self.error(node, 'Array index requires proven bounded integer type')
                return base + '[' + index + ']', typ.args[0]
            if typ.kind == 'Class':
                module = self.context['by_target'][base]
                if prop in module['_fields']: return base + '.' + name(prop), module['_fields'][prop]
                self.error(node, 'Unknown static field/method used as value')
            if typ.kind == 'Optional': base = '(' + base + ').RequireValue()'; typ = typ.args[0]
            if typ.kind == 'List' and prop == 'length': return base + '.Count', INDEX
            fields = self.module['_fields'] if typ.kind == self.module['targetClass'] else self.context['records'].get(typ.kind, {})
            if prop not in fields: self.error(node, 'Unknown typed field: ' + str(prop))
            return base + '.' + name(prop), fields[prop]
        if kind == 'AssignmentExpression':
            left, typ = self.expr(node['left']); op = node['operator']
            if op not in ('=', '+=', '-=', '*=', '/='): self.error(node, 'Unsupported assignment operator')
            right = self.expr(node['right'], typ)[0]
            return '(' + left + ' ' + op + ' ' + right + ')', typ
        if kind == 'UpdateExpression':
            arg, typ = self.expr(node['argument'])
            if typ not in (NUMBER, INDEX): self.error(node, 'Update requires numeric type')
            return (node['operator'] + arg if node['prefix'] else arg + node['operator']), typ
        if kind == 'UnaryExpression':
            if node['operator'] == 'void' and node['argument'].get('type') == 'Literal' and node['argument'].get('value') == 0:
                return 'null', UNDEFINED
            value, typ = self.expr(node['argument']); op = node['operator']
            if op == '!': return '!(' + self.truth(value, typ, node) + ')', BOOL
            if op in ('-', '+') and typ in (NUMBER, INDEX): return '(' + op + value + ')', typ
            self.error(node, 'Unary semantics unsupported')
        if kind == 'BinaryExpression':
            left, lt = self.expr(node['left']); right, rt = self.expr(node['right']); op = node['operator']
            if lt in (NULL, UNDEFINED) or rt in (NULL, UNDEFINED):
                nulltype = lt if lt in (NULL, UNDEFINED) else rt
                value, typ = (right, rt) if lt in (NULL, UNDEFINED) else (left, lt)
                equal = op in ('==', '===')
                if op not in ('==', '===', '!=', '!=='): self.error(node, 'Relational null conversion unsupported')
                if typ.kind == 'Optional':
                    flag = '(' + value + ').HasValue' if op in ('==', '!=') or nulltype == UNDEFINED else '(' + value + ').IsNotNull'
                    return ('!(' + flag + ')' if equal else flag), BOOL
                if typ.kind == 'Action' and self.nullish_guard:
                    return '(' + value + (' == null)' if equal else ' != null)'), BOOL
                self.error(node, 'null/undefined distinction requires a proven optional/guard contract')
            if lt.kind == 'Optional' and lt.args == (NUMBER,): left,lt = 'NumberMath.NumberOrNaN(' + left + ')',NUMBER
            if rt.kind == 'Optional' and rt.args == (NUMBER,): right,rt = 'NumberMath.NumberOrNaN(' + right + ')',NUMBER
            if lt in (NUMBER, INDEX) and rt in (NUMBER, INDEX):
                if op not in ('+', '-', '*', '/', '%', '<', '<=', '>', '>=', '==', '===', '!=', '!=='): self.error(node, 'Numeric operator unsupported')
                target = {'===': '==', '!==': '!='}.get(op, op)
                if op in ('+', '-', '*', '/', '%'):
                    if lt == INDEX: left = '(double)(' + left + ')'
                    if rt == INDEX: right = '(double)(' + right + ')'
                return '(' + left + ' ' + target + ' ' + right + ')', BOOL if op in ('<', '<=', '>', '>=', '==', '===', '!=', '!==') else NUMBER
            if lt == rt == STRING and op in ('+', '==', '===', '!=', '!=='):
                return '(' + left + ' ' + {'===':'==','!==':'!='}.get(op,op) + ' ' + right + ')', STRING if op == '+' else BOOL
            if lt == rt == BOOL and op in ('==', '===', '!=', '!=='):
                return '(' + left + ' ' + {'===':'==','!==':'!='}.get(op,op) + ' ' + right + ')', BOOL
            self.error(node, 'Mixed/coercing binary operation unsupported')
        if kind == 'LogicalExpression':
            left, lt = self.expr(node['left'])
            # A declared non-null data object is truthy even when its collection
            # is empty. The fallback is outside this explicit required-argument
            # domain; do not invent its unavailable service implementation.
            if lt.kind in ('Map', 'Set', 'List', *self.context['records']):
                if node['operator'] == '||': return left, lt
                self.error(node, 'Value-preserving object AND requires ordered temporary lowering')
            right, rt = self.expr(node['right'])
            if lt != BOOL or rt != BOOL: self.error(node, 'Value-producing short circuit requires statement lowering')
            return '(' + left + ' ' + node['operator'] + ' ' + right + ')', BOOL
        if kind == 'ConditionalExpression':
            condition, ct = self.expr(node['test']); yes, yt = self.expr(node['consequent'], expected)
            no, nt = self.expr(node['alternate'], expected or yt)
            if yt != nt: self.error(node, 'Conditional branch types conflict')
            return '(' + self.truth(condition, ct, node) + ' ? ' + yes + ' : ' + no + ')', yt
        if kind == 'CallExpression': return self.call(node)
        self.error(node, 'Unsupported expression: ' + kind)

    def call(self, node):
        callee, args = node['callee'], node['arguments']
        if callee['type'] == 'Identifier':
            target, typ = self.expr(callee)
            if typ.kind != 'Function': self.error(node, 'Unproven direct callable')
            if len(args) != len(typ.args) - 1: self.error(node, 'Function arity mismatch')
            return target + '(' + ', '.join(self.expr(a, t)[0] for a, t in zip(args, typ.args[:-1])) + ')', typ.args[-1]
        if callee['type'] != 'MemberExpression' or callee.get('computed'): self.error(node, 'Dynamic callee unsupported')
        prop, receiver = property_name(callee), callee['object']
        if receiver.get('type') == 'Identifier' and not receiver.get('bindingId'):
            if receiver['name'] == 'Math' and prop in ('min', 'max', 'floor', 'abs', 'sqrt'):
                if len(args) != (2 if prop in ('min', 'max') else 1): self.error(node, 'Math arity mismatch')
                return ('NumberMath.' if prop in ('min', 'max') else 'Math.') + prop.capitalize() + '(' + ', '.join(self.expr(a, NUMBER)[0] for a in args) + ')', NUMBER
            if receiver['name'] == 'Array' and prop == 'from' and len(args) == 1:
                value, typ = self.expr(args[0])
                if typ.kind != 'Set': self.error(node, 'Array.from supports ordered typed Set only')
                return value + '.ToList()', Type('List', typ.args)
        value, typ = self.expr(receiver)
        if typ.kind == 'Class' or (receiver['type'] == 'ThisExpression'):
            target = self.context['by_target'][value] if typ.kind == 'Class' else self.module
            methods = [m for m in target['methods'] if m['_sourceName'] == prop]
            if len(methods) != 1: self.error(node, 'Callee absent from selected dependency closure: ' + str(prop))
            method = methods[0]
            if len(args) != len(method['_params']): self.error(node, 'Source method arity mismatch')
            self.context['dependencies'][self.module['id']].add(target['id'])
            return value + '.' + method['name'] + '(' + ', '.join(self.expr(a, t)[0] for a, t in zip(args, method['_params'])) + ')', method['_return']
        if typ.kind == 'Map':
            key, elem = typ.args
            if prop == 'get' and len(args) == 1:
                return value + '.Get(' + self.expr(args[0], key)[0] + ')', Type('Optional', (elem,))
            if prop == 'set' and len(args) == 2:
                return value + '.Set(' + self.expr(args[0], key)[0] + ', ' + self.expr(args[1], elem)[0] + ')', typ
            if prop == 'has' and len(args) == 1:
                return value + '.ContainsKey(' + self.expr(args[0], key)[0] + ')', BOOL
            if prop == 'forEach' and len(args) == 1:
                return value + '.ForEach(' + self.callback(args[0], (elem, key), VOID) + ')', VOID
        if typ.kind == 'List':
            elem = typ.args[0]
            if prop == 'push' and len(args) == 1:
                return 'SequenceOrder.Append(' + value + ', ' + self.expr(args[0], elem)[0] + ')', INDEX
            if prop == 'forEach' and len(args) == 1:
                return value + '.ForEach(' + self.callback(args[0], (elem,), VOID) + ')', VOID
            if prop == 'sort' and len(args) == 1:
                if any(n.get('type') in ('AssignmentExpression', 'UpdateExpression', 'CallExpression', 'NewExpression') for n in walk(args[0])):
                    self.error(node, 'Comparator must be pure typed arithmetic/fields')
                return 'SequenceOrder.StableSort(' + value + ', ' + self.callback(args[0], (elem, elem), NUMBER) + ')', typ
        if typ.kind == 'Set' and prop == 'add' and len(args) == 1:
            return value + '.Add(' + self.expr(args[0], typ.args[0])[0] + ')', typ
        if typ.kind == 'Action' and prop == 'call' and len(args) == 2 and args[0]['type'] == 'ThisExpression' and args[1]['type'] == 'ThisExpression':
            return value + '(' + self.expr(args[1], typ.args[0])[0] + ')', VOID
        self.error(node, 'Unsupported typed collection/delegate call: ' + str(prop))

    def callback(self, node, params, result, local_name=None):
        if node['type'] not in ('FunctionExpression', 'ArrowFunctionExpression') or node.get('async') or node.get('generator') or len(node['params']) > len(params):
            self.error(node, 'Unsupported callback signature')
        names = [self.bind(p, t) for p, t in zip(node['params'], params)]
        for i in range(len(names), len(params)):
            extra = 'unused' + str(len(self.used)); self.used.add(extra); names.append(extra)
        if node.get('id'):
            if not local_name: self.error(node, 'Named lambda requires a proven local function binding')
            self.types[node['id']['bindingId']] = Type('Function', (*params, result))
            self.names[node['id']['bindingId']] = local_name
        old_return = self.return_type; self.return_type = result
        old_this = self.this_allowed
        if node['type']=='FunctionExpression': self.this_allowed=False
        if node['body']['type'] != 'BlockStatement': self.error(node, 'Expression lambda requires explicit return semantics')
        self.infer_locals(node['body']); body = self.block(node['body'])
        self.return_type = old_return
        self.this_allowed = old_this
        if local_name:
            return result.cs() + ' ' + local_name + '(' + ', '.join(t.cs() + ' ' + n for n, t in zip(names, params)) + ') {\n' + body + '\n}'
        return '(' + ', '.join(names) + ') => {\n' + body + '\n}'

    def block(self, node):
        return '\n'.join(self.statement(n) for n in node.get('body', []))

    def return_statement(self, node, value):
        if value is None:
            if self.return_type != VOID: self.error(node, 'Missing typed return value')
            return 'return;'
        if value['type'] == 'SequenceExpression':
            return '\n'.join(self.expression_statement(v) for v in value['expressions'][:-1]) + '\n' + self.return_statement(node, value['expressions'][-1])
        if value['type'] == 'ConditionalExpression':
            cond, ct = self.expr(value['test'])
            return 'if (' + self.truth(cond, ct, value) + ') {\n' + self.return_statement(node, value['consequent']) + '\n} else {\n' + self.return_statement(node, value['alternate']) + '\n}'
        if self.return_type == VOID:
            return self.expression_statement(value) + '\nreturn;'
        return 'return ' + self.expr(value, self.return_type)[0] + ';'

    def expression_statement(self, node):
        if node['type'] == 'SequenceExpression': return '\n'.join(self.expression_statement(v) for v in node['expressions'])
        if node['type'] == 'ConditionalExpression':
            condition, ct = self.expr(node['test'])
            return 'if (' + self.truth(condition, ct, node) + ') {\n' + self.expression_statement(node['consequent']) + '\n} else {\n' + self.expression_statement(node['alternate']) + '\n}'
        if node['type'] == 'LogicalExpression':
            # Canonical transpiler nullish callback guard. Collapse null and undefined
            # only in this discarded-value guard, never in general expressions.
            if self.is_delegate_guard(node):
                old = self.nullish_guard; self.nullish_guard = True
                left, lt = self.expr(node['left']); call = self.expression_statement(node['right'])
                self.nullish_guard = old
                return 'if (!(' + self.truth(left, lt, node) + ')) {\n' + call + '\n}'
            left, lt = self.expr(node['left'])
            condition = self.truth(left, lt, node)
            if node['operator'] == '||': condition = '!(' + condition + ')'
            return 'if (' + condition + ') {\n' + self.expression_statement(node['right']) + '\n}'
        value, typ = self.expr(node)
        if node['type'] not in ('AssignmentExpression', 'CallExpression', 'UpdateExpression'):
            self.error(node, 'Discarded expression with unsupported side effects')
        return (value[1:-1] if node['type'] == 'AssignmentExpression' else value) + ';'

    def is_delegate_guard(self, node):
        # null === (local = this.callback) || void 0 === local || local.call(this,this)
        if node.get('operator') != '||' or node['left'].get('operator') != '||': return False
        a, b = node['left']['left'], node['left']['right']; call = node['right']
        if a.get('operator') != '===' or b.get('operator') != '===' or a.get('left', {}).get('value', 'absent') is not None: return False
        assign = a.get('right', {})
        if assign.get('type') != 'AssignmentExpression' or assign.get('operator') != '=': return False
        binding = assign['left'].get('bindingId')
        if self.types.get(binding, Type('?')).kind != 'Action': return False
        return (b.get('left', {}).get('type') == 'UnaryExpression' and b['left'].get('operator') == 'void'
                and b['left']['argument'].get('value') == 0 and b.get('right', {}).get('bindingId') == binding
                and call.get('type') == 'CallExpression' and property_name(call['callee']) == 'call'
                and call['callee']['object'].get('bindingId') == binding)

    def statement(self, node):
        kind = node['type']
        if kind == 'BlockStatement': return '{\n' + self.block(node) + '\n}'
        if kind == 'ExpressionStatement': return self.expression_statement(node['expression'])
        if kind == 'ReturnStatement': return self.return_statement(node, node.get('argument'))
        if kind == 'EmptyStatement': return ';'
        if kind == 'VariableDeclaration':
            normal, functions = [], []
            for d in node['declarations']:
                key = d['id'].get('bindingId'); typ = self.types.get(key)
                if not typ: self.error(d, 'Local type unresolved')
                target = self.names[key]; init = d.get('init')
                if typ.kind == 'Function':
                    if not init or init['type'] != 'FunctionExpression': self.error(d, 'Function variable unsupported')
                    # Hoisting only a side-effect-free function literal within the same
                    # declaration. Other initializers may only be empty collections.
                    if any(x.get('init') and x['init']['type'] not in ('FunctionExpression', 'NewExpression') for x in node['declarations']):
                        self.error(d, 'Function initialization order not proven')
                    functions.append(self.callback(init, typ.args[:-1], typ.args[-1], target))
                elif init:
                    normal.append(typ.cs() + ' ' + target + ' = ' + self.expr(init, typ)[0] + ';')
                elif typ.kind == 'Optional': normal.append(typ.cs() + ' ' + target + ' = default(' + typ.cs() + ');')
                elif typ.kind == 'Action': normal.append(typ.cs() + ' ' + target + ' = null;')
                else: self.error(d, 'Uninitialized concrete local cannot receive an invented default')
            return '\n'.join(normal + functions)
        if kind == 'IfStatement':
            value, typ = self.expr(node['test']); result = 'if (' + self.truth(value, typ, node) + ') {\n' + self.statement(node['consequent']) + '\n}'
            if node.get('alternate'): result += ' else {\n' + self.statement(node['alternate']) + '\n}'
            return result
        if kind == 'ForStatement':
            init = node.get('init'); test = node.get('test'); update = node.get('update')
            if not init or init['type'] != 'VariableDeclaration' or not test or not update:
                self.error(node, 'Only explicit counted loops are supported')
            self.infer_locals({'body': [init]})
            header = self.statement(init).rstrip(';')
            value, typ = self.expr(test); step, _ = self.expr(update)
            return 'for (' + header + '; ' + self.truth(value, typ, node) + '; ' + step + ') {\n' + self.statement(node['body']) + '\n}'
        if kind == 'WhileStatement':
            value, typ = self.expr(node['test'])
            return 'while (' + self.truth(value, typ, node) + ') {\n' + self.statement(node['body']) + '\n}'
        if kind == 'SwitchStatement':
            value, typ = self.expr(node['discriminant'])
            if typ not in (NUMBER, INDEX, BOOL, STRING): self.error(node, 'Switch discriminant is not a strict primitive')
            lines=['switch (' + value + ') {']
            for case in node['cases']:
                test=case.get('test')
                if test is not None and test['type']!='Literal': self.error(case, 'Nonconstant switch cases require ordered lowering')
                lines.append('case ' + self.expr(test,typ)[0] + ':' if test is not None else 'default:')
                body=case['consequent']
                if body and body[-1]['type'] not in ('BreakStatement','ReturnStatement','ThrowStatement'):
                    self.error(case,'Implicit nonempty switch fallthrough is not supported')
                self.infer_locals({'body':body});lines.extend(self.statement(s) for s in body)
            return '\n'.join(lines+['}'])
        if kind == 'ThrowStatement':
            value, typ = self.expr(node['argument'])
            if typ != STRING: self.error(node, 'Only explicit string exceptions are currently supported')
            return 'throw new InvalidOperationException(' + value + ');'
        if kind in ('BreakStatement', 'ContinueStatement'):
            if node.get('label'): self.error(node, 'Labeled control flow unsupported')
            return 'break;' if kind == 'BreakStatement' else 'continue;'
        self.error(node, 'Unsupported statement: ' + kind)

    def render(self):
        if self.ast.get('async') or self.ast.get('generator'): self.error(self.ast, 'Async/generator state not recovered')
        params = ', '.join(t.cs() + ' ' + self.names[p['bindingId']] for p, t in zip(self.ast['params'], self.method['_params']))
        return 'public ' + ('static ' if self.method['_static'] else '') + self.method['_return'].cs() + ' ' + name(self.method['name']) + '(' + params + ') {\n' + self.block(self.ast['body']) + '\n}'
