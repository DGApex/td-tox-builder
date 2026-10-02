"""Portable preflight helpers for generated TD builders and embedded adapters.

Copy into the project or inline the required functions into the generated DAT.
Do not make a deployed TOX import its author's skill directory. Python stdlib.
"""
import builtins
import symtable


def menu_value(name, value, names, labels):
    """Return an ID actually exposed by this parameter, never a guessed index.

    Prefer exact IDs, then case-insensitive IDs/labels. Pixel abbreviations are
    considered only for unit parameters. No substring matches or first-item
    fallback: incompatible or ambiguous metadata must remain visible.
    """
    names=list(names or []);labels=list(labels or [])
    if value in names:return value
    wanted=str(value).strip().casefold()
    rows=[(key,labels[i] if i<len(labels) else '') for i,key in enumerate(names)]
    matches=[key for key,label in rows if wanted in
             (str(key).strip().casefold(),str(label).strip().casefold())]
    if not matches and name.endswith('unit') and wanted in ('pixel','pixels','pix','px'):
        pixels={'pixel','pixels','pix','px'}
        matches=[key for key,label in rows if str(key).strip().casefold() in pixels
                 or str(label).strip().casefold() in pixels]
    if len(matches)==1:return matches[0]
    raise ValueError('Unsupported or ambiguous menu %s: %r; names=%r; labels=%r' %
                     (name,value,names,labels))


def set_menu(node, name, value, required=True):
    """Assign a resolved native ID; include the node path in diagnostics."""
    path=getattr(node,'path',getattr(node,'name','<operator>'))
    par=getattr(node.par,name,None)
    if par is None:
        if not required:return None
        raise ValueError('%s: missing required menu %s' % (path,name))
    try:
        selected=menu_value(name,value,getattr(par,'menuNames',[]),getattr(par,'menuLabels',[]))
    except ValueError as exc:raise ValueError('%s: %s' % (path,exc)) from exc
    par.val=selected
    return selected


def validate_globals(source, namespace):
    """Fail before mutation if parsed code refers to unprovided global names.

    Call after loading definitions into the ACTUAL isolated namespace, before
    calling its builder. Imports local to functions are not global dependencies.
    Builtins may be a dict or module, including TD-injected operator factories.
    Blind spots: dynamic exec/import, embedded source strings, optional branches
    and names first created by later execution. Check each DAT's own scope and
    document intentionally deferred globals rather than trusting this blindly.
    """
    provided=namespace.get('__builtins__',builtins)
    available=set(namespace)|set(provided if isinstance(provided,dict) else vars(provided))
    pending=[symtable.symtable(source,'<TD dependency preflight>','exec')]
    missing=set()
    while pending:
        table=pending.pop();pending.extend(table.get_children())
        missing.update(symbol.get_name() for symbol in table.get_symbols()
                       if symbol.is_referenced() and symbol.is_global()
                       and symbol.get_name() not in available)
    if missing:raise RuntimeError('Missing globals before TD mutation: '+', '.join(sorted(missing)))
