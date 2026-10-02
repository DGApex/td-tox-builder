"""Read-only guard for known TD alpha-blend menu ID mistakes (G27).

Usage: python check_td_menu_ids.py [builder.py ...]
Without arguments checks execution/build_*_tox.py and execution/*_builder.py.
Pure stdlib; no TD mutation. Exit 1 for incompatible literal candidate lists.
Blind spots: recognizes only menu/_setmenu(node, literal_name, literal_choices)
and direct literal assignments. Dynamic aliases and unrelated enums are not
validated. This does not prove native rendering or other versions' menus.
"""
import ast
import sys
from pathlib import Path

FACTORS = {'srcblend': ('sa', {'srcalpha'}),
           'destblend': ('omsa', {'oneminussrcalpha', 'invsrcalpha'})}


def problems(source):
    result = []
    for node in ast.walk(ast.parse(source)):
        name, choices = None, None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('menu', '_setmenu') and len(node.args) >= 3:
            try:
                name, choices = ast.literal_eval(node.args[1]), ast.literal_eval(node.args[2])
            except (ValueError, TypeError):
                continue
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            target = node.targets[0]
            if isinstance(target, ast.Attribute):
                name, choices = target.attr, [node.value.value]
        if not isinstance(name, str) or name not in FACTORS or not isinstance(choices, (list, tuple)):
            continue
        required, aliases = FACTORS[name]
        if any(value in aliases for value in choices if isinstance(value, str)) and required not in choices:
            result.append((node.lineno, '%s needs native ID %r, not just descriptive alpha aliases' % (name, required)))
    return result


def main():
    assert problems("menu(mat, 'srcblend', ('srcalpha',))")
    assert problems("menu(mat, 'destblend', ('invsrcalpha',))")
    assert not problems("menu(mat, 'srcblend', ('sa','srcalpha'))")
    assert not problems("menu(mat, 'destblend', ('omsa','invsrcalpha'))")
    assert not problems("menu(mat, 'destblend', ('one',))")
    paths = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else sorted(
        set(Path('execution').glob('build_*_tox.py')) | set(Path('execution').glob('*_builder.py')))
    failed = False
    for path in paths:
        for line, message in problems(path.read_text(encoding='utf-8')):
            print('FAIL %s:%s: %s' % (path, line, message))
            failed = True
    if not failed:
        print('PASS TD blend menu IDs: %d builders; native sa/omsa and compatibility cases' % len(paths))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
