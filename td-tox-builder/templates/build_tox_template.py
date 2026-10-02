"""
build_<NAME>_tox.py - generate a TouchDesigner .tox component by code.

GENERATED FROM: td-tox-builder/templates/build_tox_template.py
WORKED EXAMPLE: the FluxRT bridge component, built in a DIFFERENT project - its
files are not in this repository. The patterns it taught are inlined below and in
reference.md, so nothing here depends on reading them.

A .tox can only be produced *by* TouchDesigner. So this script is the source of
truth: run it INSIDE TD and it assembles the COMP and saves <NAME>.tox.

This template bakes in the proven patterns:
  * Self-contained + portable: embed artifacts as Text DATs, write them to disk on
    Setup (reference.md G7).
  * From-zero bootstrap under a chosen Install Dir (reference.md G8).
  * Robust control surface: parexec self-instantiates the extension (no promotion,
    G3); Spout/OSC bound with candidate par names (G4); idempotent rebuild.

HOW TO RUN IT (cache-proof - reference.md G2; encoding - G25):
    Textport (Alt+T):  exec(open('<ABS PATH TO THIS FILE>', encoding='utf-8').read())
    Expect:            [build] ... saved -> <path>.tox

Every place you must customise is marked  # >>> EDIT

When adding menu setters or loading another builder into an isolated exec scope,
copy/inline the required helpers from the sibling td_preflight.py (G29/G30).
Do not import the author's skill directory from a deployed component. Validate
the actual isolated namespace before creating nodes; resolve menus against the
parameter's runtime IDs/labels. Run check_td_preflight.py from the skill and
the project's own integration checks before handing this builder to an operator.
"""
import os

# TD's open() decodes as cp1252 unless told otherwise; a mis-decoded script can
# run to completion with mojibake in its Text DATs (reference.md G25). This
# literal probe is one character when decoded right and two when not.
_ENCODING_PROBE = "é"
if len(_ENCODING_PROBE) != 1:
    raise RuntimeError("this file was decoded with the wrong codec - run it as "
                       "exec(open(path, encoding='utf-8').read())")

# >>> EDIT 1 - identity & location (forward slashes)
PROJECT_ROOT = "C:/path/to/your/project"     # where the .tox is saved + artifacts live
COMP_NAME = "MyComp"

# >>> EDIT 2 - artifacts embedded into the .tox (file on disk -> Text DAT name).
# These get baked in at build time and written to <Installdir>/bridge on Setup.
# Drop this whole feature if your component launches nothing external.
ARTIFACTS = {
    "bridge_py": "execution/my_bridge.py",
    "setup_ps1": "execution/setup_myapp.ps1",
    "req_lock": "execution/requirements.lock.txt",
}

# ───────────────────────────────────────────────────────────────────────────
# >>> EDIT 3 - the embedded extension class. Rename it (keep in sync with the
# Text DAT name). Implement the methods your component needs.
# ───────────────────────────────────────────────────────────────────────────
EXTENSION_CODE = r'''"""<NAME> component extension - install + run control."""
import os
import subprocess

CREATE_NEW_CONSOLE = 0x00000010


class MyCompExt:                       # >>> EDIT class name (== Text DAT name)
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.proc = None
        self._status('idle')

    def _log(self, m):
        print("[<NAME>] %s" % m)

    def _status(self, s):
        try:
            self.ownerComp.par.Status.val = s
        except Exception:
            pass

    def _installdir(self):
        return self.ownerComp.par.Installdir.eval()

    def _osc(self):
        return self.ownerComp.op('oscout')

    def _conda(self, installdir):
        bat = os.path.join(installdir, 'miniconda', 'condabin', 'conda.bat')
        return bat if os.path.isfile(bat) else 'conda'

    def _write_artifacts(self, installdir):
        bdir = os.path.join(installdir, 'bridge')
        os.makedirs(bdir, exist_ok=True)
        # file on disk -> embedded Text DAT name  (>>> EDIT to match ARTIFACTS)
        mapping = {
            'my_bridge.py': 'bridge_py',
            'setup_myapp.ps1': 'setup_ps1',
            'requirements.lock.txt': 'req_lock',
        }
        for fname, datname in mapping.items():
            dat = self.ownerComp.op(datname)
            if dat is None:
                continue
            with open(os.path.join(bdir, fname), 'w',
                      encoding='utf-8', newline='\n') as f:
                f.write(dat.text)
        return bdir

    # ── buttons ─────────────────────────────────────────────────────────────
    def Setup(self):
        installdir = self._installdir()
        if not installdir:
            self._status('set Install Dir first'); return
        bdir = self._write_artifacts(installdir)
        ps1 = os.path.join(bdir, 'setup_myapp.ps1')        # >>> EDIT script name
        cmd = ('powershell -NoExit -ExecutionPolicy Bypass -File "%s" '
               '-InstallDir "%s"' % (ps1, installdir))
        self._status('installing (see console)')
        subprocess.Popen(cmd, cwd=installdir, creationflags=CREATE_NEW_CONSOLE)

    def Start(self):
        if self.proc is not None and self.proc.poll() is None:
            self._log("already running"); return
        installdir = self._installdir()
        if not installdir:
            self._status('set Install Dir first'); return
        bridge = os.path.join(installdir, 'bridge', 'my_bridge.py')   # >>> EDIT
        env = os.path.join(installdir, 'env')
        if not os.path.isfile(bridge):
            self._status('not installed - run Setup'); return
        conda = self._conda(installdir)
        # Launcher .bat so quoting survives spaced paths (reference.md G8).
        launcher = os.path.join(installdir, 'bridge', '_start.bat')
        with open(launcher, 'w') as f:
            f.write('@echo off\r\n')
            f.write('cd /d "%s"\r\n' % installdir)
            f.write('"%s" run --no-capture-output -p "%s" python -u "%s"\r\n'  # >>> EDIT args
                    % (conda, env, bridge))
        self._status('running')
        self.proc = subprocess.Popen('cmd /k "%s"' % launcher,
                                     creationflags=CREATE_NEW_CONSOLE)

    def Stop(self):
        try:
            self._osc().sendOSC('/myapp/quit', [])           # >>> EDIT if no OSC
        except Exception:
            pass
        if self.proc is not None and self.proc.poll() is None:
            subprocess.Popen('taskkill /F /T /PID %d' % self.proc.pid)
        self.proc = None
        self._status('stopped')

    # ── live OSC (delete if none) ───────────────────────────────────────────
    def SendParam(self):
        self._osc().sendOSC('/myapp/param', [self.ownerComp.par.Param1.eval()])
'''

# ───────────────────────────────────────────────────────────────────────────
# >>> EDIT 4 - parexec routing (self-instantiating, no promotion - G3).
# ───────────────────────────────────────────────────────────────────────────
PAREXEC_CODE = r'''# Routes <NAME>'s custom parameters to its extension.
_INSTANCES = {}


def _ext(comp):
    inst = _INSTANCES.get(comp.id)
    if inst is None:
        inst = op('MyCompExt').module.MyCompExt(comp)        # >>> EDIT DAT/class
        _INSTANCES[comp.id] = inst
    return inst


def onValueChange(par, prev):
    e = _ext(par.owner)
    if par.name == 'Param1':
        e.SendParam()
    return


def onPulse(par):
    e = _ext(par.owner)
    actions = {'Setup': e.Setup, 'Start': e.Start, 'Stop': e.Stop,
               'Sendparam': e.SendParam}
    fn = actions.get(par.name)
    if fn:
        fn()
    return


def onValuesChanged(changes):
    for ch in changes:
        onValueChange(ch.par, ch.prev)
    return
'''


def _read_artifact(rel):
    try:
        with open(os.path.join(PROJECT_ROOT, rel), 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as exc:
        print("[build] WARN could not read %s: %s" % (rel, exc))
        return "# MISSING ARTIFACT: %s\n" % rel


def build():
    root = op('/')
    existing = root.op(COMP_NAME)
    if existing:
        existing.destroy()                       # idempotent rebuild

    comp = root.create(baseCOMP, COMP_NAME)
    comp.nodeX, comp.nodeY = 0, 0

    # ── >>> EDIT 5 - inputs / outputs ───────────────────────────────────────
    in1 = comp.create(inTOP, 'in1')
    out1 = comp.create(outTOP, 'out1')
    sp_out = comp.create(spoutoutTOP, 'spout_out')   # delete if no Spout
    sp_in = comp.create(spoutinTOP, 'spout_in')
    oscout = comp.create(oscoutDAT, 'oscout')        # delete if no OSC

    ext_dat = comp.create(textDAT, 'MyCompExt')      # >>> EDIT name == class name
    parexec = comp.create(parameterexecuteDAT, 'parexec')

    # embedded artifacts (baked into the .tox) - delete block if none
    for datname, rel in ARTIFACTS.items():
        d = comp.create(textDAT, datname)
        d.text = _read_artifact(rel)

    sp_out.inputConnectors[0].connect(in1)
    out1.inputConnectors[0].connect(sp_in)

    # ── par helpers ─────────────────────────────────────────────────────────
    def _set(pg, **kw):
        par = pg[0]
        for k, v in kw.items():
            try:
                setattr(par, k, v)
            except Exception as exc:
                print("[build] WARN set %s.%s: %s" % (par.name, k, exc))
        return par

    def _setval(node, names, value):
        if isinstance(names, str):
            names = [names]
        for n in names:
            p = getattr(node.par, n, None)
            if p is not None:
                p.val = value
                return
        print("[build] WARN %s has none of %s" % (node.name, names))

    # ── >>> EDIT 6 - parameters (names MUST be valid identifiers, G1) ────────
    page = comp.appendCustomPage(COMP_NAME)
    _set(page.appendStr('Param1'), default='hello', val='hello',
         help='Live control, sent over OSC on change.')
    page.appendPulse('Sendparam')

    page2 = comp.appendCustomPage('Setup')
    _set(page2.appendFolder('Installdir'), default='C:/MyApp', val='C:/MyApp',
         help='Folder for the self-contained install (env, repos, artifacts).')
    _set(page2.appendStr('Status'), default='idle', val='idle', readOnly=True,
         help='Component state (set by the extension).')
    page2.appendPulse('Setup')
    page2.appendPulse('Start')
    page2.appendPulse('Stop')

    # ── fixed Spout/OSC names (internalized, tolerating par-name variance G4) ─
    _setval(sp_out, ['sendername', 'sender'], 'TDtoApp')
    _setval(sp_in, ['sendername', 'sender', 'activesender'], 'AppOutput')
    _setval(oscout, ['netaddress', 'address'], '127.0.0.1')
    _setval(oscout, 'port', 9000)

    # ── extension + callbacks ───────────────────────────────────────────────
    ext_dat.text = EXTENSION_CODE
    parexec.text = PAREXEC_CODE
    try:
        parexec.par.op.val = '..'
        parexec.par.pars = '*'
        parexec.par.valuechange = True
        parexec.par.onpulse = True
    except Exception as exc:
        print("[build] WARN parexec config: %s" % exc)

    out_path = "%s/%s.tox" % (PROJECT_ROOT, COMP_NAME)
    comp.save(out_path)
    print("[build] %s built and saved -> %s" % (COMP_NAME, out_path))
    return comp


build()
