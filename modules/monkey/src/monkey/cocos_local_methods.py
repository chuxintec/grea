"""Lower complete local JS method bodies under an explicit Unity member contract."""
import re

from .code_graph import facts
from .io import finish, load, new_output, read, safe, sha, write_json


def member(node):
    if (node.get('type') == 'MemberExpression' and not node.get('computed')
            and not node.get('optional') and node['object']['type'] == 'ThisExpression'
            and node['property']['type'] == 'Identifier'):
        name = node['property']['name']
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            return name
    return None


def property_of(expr, name):
    return (expr.get('type') == 'MemberExpression' and not expr.get('computed')
            and not expr.get('optional') and expr['property'].get('name') == name)


def guarded_visual_write(expr, targets):
    """Only side-effect-free instance fields may be used as receiver guards."""
    if expr.get('type') != 'LogicalExpression' or expr['operator'] != '&&':
        return None
    field = member(expr['left'])
    kind = targets.get(field)
    if kind not in ('GameObject', 'CanvasGroup', 'Image'):
        return None
    right = expr['right']
    assignments = right['expressions'] if right['type'] == 'SequenceExpression' else [right]
    receiver = f'this.@{field}'
    lines = []
    for assignment in assignments:
        if assignment['type'] != 'AssignmentExpression' or assignment['operator'] != '=':
            return None
        left, value = assignment['left'], assignment['right']
        base = left.get('object', {})
        literal = value.get('value') if value['type'] == 'Literal' else None
        if property_of(left, 'active'):
            if kind == 'Image' and property_of(base, 'node'):
                base = base['object']
                target = receiver + '.gameObject'
            elif kind == 'GameObject':
                target = receiver
            else:
                return None
            if value['type'] == 'UnaryExpression' and value['operator'] == '!':
                argument = value['argument']
                if argument['type'] != 'Literal' or type(argument.get('value')) != int or argument['value'] not in (0,1):
                    return None
                literal = not argument['value']
            if type(literal) != bool:
                return None
            lines.append(f'{target}.SetActive({str(literal).lower()});')
        elif property_of(left, 'opacity') and kind == 'CanvasGroup' and type(literal) == int and 0 <= literal <= 255:
            lines.append(f'{receiver}.alpha = {literal}f / 255f;')
        elif (property_of(left, 'spriteFrame') and kind == 'Image' and value['type'] == 'Literal'
              and value.get('raw') == 'null'):
            lines.append(f'{receiver}.sprite = null;')
        else:
            return None
        if member(base) != field:
            return None
    return f'if ({receiver}) {{ ' + ' '.join(lines) + ' }'


def forward_return(fn, contract):
    """Forward one bound argument through a reviewed receiver and method."""
    route = contract.get('returnCall')
    statements = fn['body']['body']
    if not route or len(fn['params']) != 1 or len(statements) != 1 or statements[0]['type'] != 'ReturnStatement':
        return None
    call = statements[0]['argument']
    if not call or call['type'] != 'CallExpression' or call.get('optional') or len(call['arguments']) != 1:
        return None
    field, method = route['field'], route['method']
    callee, arg, param = call['callee'], call['arguments'][0], fn['params'][0]
    if not property_of(callee, method) or member(callee['object']) != field:
        return None
    if (arg['type'] != 'Identifier' or arg['name'] != param['name']
            or not arg.get('bindingId') or arg['bindingId'] != param.get('bindingId')
            or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',param['name'])):
        return None
    return f"return this.@{field}.@{method}(@{param['name']});"


def assignment(expr, contract):
    left = member(expr['left'])
    types = contract['members']
    if not left or left not in types:
        return None
    value = expr['right']
    right = member(value)
    if right and types.get(right) == types[left]:
        return f'this.@{left} = this.@{right};'
    if types[left] != 'double':
        return None
    for axis in contract.get('localPositionAxes', []):
        if property_of(value, axis) and member(value['object']) == 'node':
            return f'this.@{left} = this.transform.localPosition.{axis};'
    if value['type'] == 'BinaryExpression' and value['operator'] == '+':
        a, b = member(value['left']), member(value['right'])
        if types.get(a) == types.get(b) == 'double':
            return f'this.@{left} = this.@{a} + this.@{b};'
    return None


def lower(row, contract):
    """Unmatched statements reject the entire function, including its prefix."""
    fn = row['ast']
    if (row['method']['static'] or fn['type'] != 'FunctionExpression' or fn.get('async')
            or fn.get('generator') or any(p['type'] != 'Identifier' for p in fn['params'])):
        return None
    if contract['returns'] != 'void':
        return forward_return(fn, contract)
    statements = []
    for stmt in fn['body']['body']:
        expr = stmt.get('expression', {})
        if stmt['type'] != 'ExpressionStatement':
            return None
        parts = expr['expressions'] if expr.get('type') == 'SequenceExpression' else [expr]
        for part in parts:
            line = None
            if part.get('type') == 'LogicalExpression':
                line = guarded_visual_write(part, contract.get('visualFields', {}))
            elif part.get('type') == 'CallExpression' and not part.get('optional') and not part['arguments']:
                name = member(part['callee'])
                if name in contract['voidCalls']:
                    line = f'this.@{name}();'
            elif part.get('type') == 'AssignmentExpression' and part['operator'] == '=':
                line = assignment(part, contract)
            if line is None:
                return None
            statements.append(line)
    return '\n'.join(statements) or 'return;'


def render_scripts(directory, templates, methods):
    scripts = {}
    assigned = set()
    for template in templates:
        name = template['file']
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.cs', name) or name.casefold() in scripts:
            raise ValueError('Expected unique C# template filenames')
        raw = read(safe(directory / name))
        if sha(raw) != template['sha256']:
            raise ValueError(f'Template hash mismatch: {name}')
        text = raw.decode('utf-8')
        for method_id in template['ids']:
            token = f'/*monkey:{method_id}*/'
            body = methods.get(method_id)
            if body is None or method_id in assigned or text.count(token) != 1:
                raise ValueError(f'Missing or ambiguous generated body: {method_id}')
            text = text.replace(token, body)
            assigned.add(method_id)
        if '/*monkey:' in text:
            raise ValueError(f'Unresolved template token: {name}')
        scripts[name.casefold()] = (name, text.encode())
    return scripts.values()


def validate_contract(row):
    if not re.fullmatch(r'method@[0-9]+',row['id']) or not re.fullmatch(r'[0-9a-f]{64}',row['sha256']):
        raise ValueError('Expected a lexical method ID and SHA-256')
    if 'returnCall' in row:
        route = row['returnCall']
        if (not isinstance(route, dict) or set(route) != {'field','method'}
                or not all(isinstance(v,str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',v) for v in route.values())
                or row['returns'] in ('void','review')):
            raise ValueError('Expected typed forwarded return member contract')
    axes = row.get('localPositionAxes', [])
    if not isinstance(axes, list) or any(axis not in ('x','y') for axis in axes):
        raise ValueError('Expected a list of explicitly mapped local Cocos position axes')
    calls = row['voidCalls']
    if not isinstance(calls, list) or not all(isinstance(name, str) for name in calls):
        raise ValueError('voidCalls must be an array of member names')
    for members, supported in [(row['members'], {'string','bool','double'}),
                               (row.get('visualFields',{}), {'GameObject','CanvasGroup','Image'})]:
        if not isinstance(members, dict) or not all(kind in supported for kind in members.values()):
            raise ValueError('Invalid member type in local method contract')


def export(source, manifest, output):
    spec = load(read(safe(manifest)))
    rows = spec['methods']
    for row in rows:
        validate_contract(row)
    ids = [r['id'] for r in rows]
    if not 1 <= len(ids) <= 256 or len(set(ids)) != len(ids):
        raise ValueError('Expected 1–256 distinct selected methods')
    if not re.fullmatch(r'[0-9a-f]{64}', spec.get('sourceSha256') or ''):
        raise ValueError('Expected exact source SHA-256')
    graph = facts(source, spec['sourceSha256'], ids)
    selected = {r['method']['id']:r for r in graph['selected']}
    result = []
    for contract in rows:
        row = selected[contract['id']]
        m = row['method']
        if m['sourceSha256'] != contract['sha256']:
            raise ValueError('Method source hash mismatch')
        body = lower(row, contract)
        result.append(dict(id=m['id'], name=m['name'], sourceBytes=m['sourceBytes'],
                           sha256=m['sourceSha256'], body=body,
                           status='lowered' if body is not None else 'review'))
    templates = spec.get('templates', [])
    directory = safe(manifest).parent
    scripts = render_scripts(directory, templates, {r['id']: r['body'] for r in result})
    inputs = [safe(source), safe(manifest), *(directory / t['file'] for t in templates)]
    out = new_output(output, inputs)
    for name, content in scripts:
        (out / name).write_bytes(content)
    write_json(out/'local-methods.json',dict(source=graph['source'],methods=result,sourceExecuted=False))
    lowered = sum(r['body'] is not None for r in result)
    finish(out, dict(schemaVersion=1, scopeMode='cocos-local-methods', diagnostics=[]),
           blocking_diagnostics=lowered != len(result))
    return dict(methods=len(rows), lowered=lowered,
                report=str(out/'local-methods.json'))
