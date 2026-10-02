"""Read-only regression for the skill's portable dependency/menu preflights.

Usage: python <skill>/check_td_preflight.py
Loads the real shipped helper and runs synthetic failure/pass cases. Pure
stdlib; no native TD, files written, project dependencies or network calls.
Blind spots: synthetic menu lists test resolution, NOT the user's native enums;
no guarantee of operator availability, visual output, GPU cost or dynamic code.
"""
import builtins
import importlib.util
from pathlib import Path
from types import SimpleNamespace


def must_fail(action,kind,contains):
    try:action()
    except kind as exc:
        assert all(word in str(exc) for word in contains),str(exc)
    else:raise AssertionError('Expected failure was not detected')


def check():
    path=Path(__file__).resolve().parent/'templates/td_preflight.py'
    spec=importlib.util.spec_from_file_location('skill_td_preflight',path)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    # Reproduce the missing-import class with the actual isolated exec scope.
    source='def build():\n    return os.path.join("root", "output.tox")\n'
    scope={};exec(compile(source,'<isolated definitions>','exec'),scope)
    must_fail(lambda:helper.validate_globals(source,scope),RuntimeError,['os','before TD mutation'])
    fixed='import os\n'+source
    scope={};exec(compile(fixed,'<self-contained definitions>','exec'),scope)
    helper.validate_globals(fixed,scope)
    for location in ('globals','builtins'):
        source='def build():\n    return op("/").create(textDAT, "code")\n'
        scope={'__builtins__':dict(vars(builtins))}
        target=scope if location=='globals' else scope['__builtins__']
        target.update(op=object(),textDAT=object())
        exec(compile(source,'<TD scope>','exec'),scope)
        helper.validate_globals(source,scope)
        del target['textDAT']
        must_fail(lambda:helper.validate_globals(source,scope),RuntimeError,['textDAT'])
    local='def build():\n    import os\n    return os.path.sep\n'
    scope={'__builtins__':builtins};exec(local,scope);helper.validate_globals(local,scope)
    # Previous case-sensitive-ID/full-label matcher fails this shape.
    names=['fraction','pixels','points'];labels=['Fraction','px','pt']
    assert 'Pixels' not in names and 'pixels' not in [label.lower() for label in labels]
    for name in ('fontsizexunit','fontsizeyunit','borderspaceunit'):
        assert helper.menu_value(name,'Pixels',names,labels)=='pixels'
        assert helper.menu_value(name,'pixels',['frac','px'],['Fraction','px'])=='px'
        assert helper.menu_value(name,'pixels',['opaque'],['Pixel'])=='opaque'
        assert helper.menu_value(name,'pixels',['PIXELS'],[])=='PIXELS'
        must_fail(lambda:helper.menu_value(name,'pixels',['pt','fraction'],['Points','Fraction']),
                  ValueError,['names=','labels='])
    assert helper.menu_value('srcblend','sa',['one','sa'],['One','Src Alpha'])=='sa'
    assert helper.menu_value('font','Segoe Print',['segoeprint'],['Segoe Print'])=='segoeprint'
    assert helper.menu_value('alignx','center',['center','left'],['Center','Left'])=='center'
    must_fail(lambda:helper.menu_value('format','pixels',['px'],['Pixels format']),ValueError,['format'])
    must_fail(lambda:helper.menu_value('fontsizexunit','pixels',['pixelaspect'],['Pixel Aspect']),ValueError,['names='])
    must_fail(lambda:helper.menu_value('unit','Pixel',['a','b'],['Pixel','Pixel']),ValueError,['ambiguous'])
    par=SimpleNamespace(menuNames=['pixels','fraction'],menuLabels=['px','Fraction'],val='fraction')
    node=SimpleNamespace(path='/test/note',par=SimpleNamespace(fontsizexunit=par))
    assert helper.set_menu(node,'fontsizexunit','Pixels')=='pixels' and par.val=='pixels'
    must_fail(lambda:helper.set_menu(node,'fontsizexunit','points'),ValueError,
              ['/test/note','fontsizexunit','names=','labels='])
    assert par.val=='pixels','Failed resolution changed the parameter'
    assert helper.set_menu(node,'missing','pixels',required=False) is None
    must_fail(lambda:helper.set_menu(node,'missing','pixels'),ValueError,['/test/note','missing required menu'])
    print('PASS TD preflight: missing import caught before mutation; actual globals/builtins scopes; unit IDs/labels; no guessed fallback; complete diagnostics')


if __name__=='__main__':check()
