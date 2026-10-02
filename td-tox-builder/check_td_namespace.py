"""Portable, read-only guard for TouchDesigner injected-name handoffs (G26).

Usage: python check_td_namespace.py [builder.py ...]
Without arguments checks execution/build_*_tox.py and execution/*_builder.py
under the current working directory, plus a pure-Python reproduction self-test.
Exit 1 for risky handoffs or invalid syntax. No TD imports, cooking or writes.

Blind spots: literal AST matching only; aliases/computed strings are missed.
Passing globals()/locals() wholesale to non-exec/eval calls is rejected even
when a caller may intentionally want module-local state: use an explicit map.
It cannot prove native operator availability, parameters, menus or rendering.
Project regression tests must additionally execute their actual handoff AST.
"""
import ast
import builtins
import re
import sys
from pathlib import Path


def namespace_call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ('globals', 'locals') and not node.args)


def td_name(node):
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and (node.value == 'op' or re.fullmatch(r'\w+(TOP|CHOP|SOP|POP|DAT|MAT|COMP)', node.value)))


def problems(source):
    tree = ast.parse(source)
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            is_exec = isinstance(node.func, ast.Name) and node.func.id in ('exec', 'eval')
            if not is_exec and any(namespace_call(arg) for arg in node.args + [kw.value for kw in node.keywords]):
                result.append((node.lineno, 'Pass explicit resolved dependencies, not globals()/locals().'))
            if isinstance(node.func, ast.Attribute) and namespace_call(node.func.value) and node.args and td_name(node.args[0]):
                result.append((node.lineno, 'TD names may live in builtins; namespace.get() misses them.'))
        elif isinstance(node, ast.Subscript) and namespace_call(node.value) and td_name(node.slice):
            result.append((node.lineno, 'TD factory lookup in globals()/locals() can raise KeyError.'))
        elif isinstance(node, ast.Compare) and td_name(node.left) and any(namespace_call(v) for v in node.comparators):
            result.append((node.lineno, 'Detect TD through normal name lookup, not namespace membership.'))
    return result


def self_test():
    bad = "handoff(globals())"
    good = "factories = dict(textDAT=textDAT, pbrMAT=pbrMAT)\nhandoff(factories)"
    assert problems(bad) and not problems(good)
    assert problems("if 'op' in globals(): build()")
    assert problems("factory = globals()['textDAT']")
    assert problems("factory = globals().get('pbrMAT')")
    assert not problems("exec(code, globals())")
    for location in ('globals', 'builtins'):
        received = []
        def handoff(mapping): received.append((mapping['textDAT'], mapping['pbrMAT']))
        scope = {'__builtins__': dict(vars(builtins)), 'handoff': handoff}
        (scope if location == 'globals' else scope['__builtins__']).update(textDAT='text', pbrMAT='pbr')
        exec(good, scope)
        assert received == [('text', 'pbr')]
        if location == 'builtins':
            try:
                exec(bad, scope)
            except KeyError as exc:
                assert exc.args == ('textDAT',)
            else:
                raise AssertionError('Broken handoff must reproduce KeyError')


def main():
    self_test()
    paths = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else sorted(
        set(Path('execution').glob('build_*_tox.py')) | set(Path('execution').glob('*_builder.py')))
    failed = False
    for path in paths:
        try:
            found = problems(path.read_text(encoding='utf-8'))
        except (SyntaxError, OSError) as exc:
            found = [(0, str(exc))]
        for line, message in found:
            print('FAIL %s:%s: %s' % (path, line, message))
            failed = True
    if not failed:
        print('PASS TD namespaces: %d builders; builtins/globals reproduction and explicit handoff' % len(paths))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
