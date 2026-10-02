# Reference — Building `.tox` components in TouchDesigner from Python

> Companion to `SKILL.md`. The TD Python API cheatsheet plus the catalog of
> non-obvious failures hit while building the FluxRT `.tox`.
> Read the gotcha that matches your error; copy the cheatsheet patterns verbatim.
>
> ⚠️ **FluxRT lived in a different project. Its files are not in this repository** —
> every `execution/*fluxrt*` path below names the origin of a lesson, not a file you
> can open. The patterns are reproduced inline precisely so the missing files never
> need to be read.

---

## Why a build script (and not a hand-built .tox)

A `.tox` is a TouchDesigner COMP serialized to disk in TD's own format. It can
only be produced **by TouchDesigner**, never written by an external editor. So the
reproducible, version-controllable way to make one is a **Python build script**
that you run *inside* TD: it creates the COMP by code (operators, wiring, custom
parameters, embedded DAT scripts) and calls `comp.save('Name.tox')`. The script
is the source of truth; the `.tox` is a build artifact.

---

## TD Python API cheatsheet (TouchDesigner 2022+/2023+)

### Create the COMP and operators
```python
root = op('/')                       # or any parent COMP path
existing = root.op('MyComp')
if existing:
    existing.destroy()               # idempotent rebuild — always do this first
comp = root.create(baseCOMP, 'MyComp')

# Operator type constants are injected globals inside TD (no import needed):
in1   = comp.create(inTOP,  'in1')           # COMP input  1 (image)
out1  = comp.create(outTOP, 'out1')          # COMP output 1 (image)
sout  = comp.create(spoutoutTOP, 'spout_out')  # Windows only
sin   = comp.create(spoutinTOP,  'spout_in')   # Windows only
oscout = comp.create(oscoutDAT, 'oscout')
txt   = comp.create(textDAT, 'MyExt')
pexec = comp.create(parameterexecuteDAT, 'parexec')
```
Common type constants: `baseCOMP`, `containerCOMP`, `inTOP`, `outTOP`, `nullTOP`,
`moviefileinTOP`, `spoutinTOP`, `spoutoutTOP`, `oscoutDAT`, `oscinDAT`, `textDAT`,
`executeDAT`, `parameterexecuteDAT`, `chopexecuteDAT`.

### Layout (optional, cosmetic)
```python
node.nodeX, node.nodeY = -300, 200
```

### Wire TOPs
```python
# connect(input_index)  <- source operator (uses the source's first output)
spout_out.inputConnectors[0].connect(in1)
out1.inputConnectors[0].connect(spout_in)
```

### Custom parameters
```python
page = comp.appendCustomPage('Controls')      # page name: free text
pg = page.appendStr('Prompt')                 # returns a ParGroup
par = pg[0]
par.default = 'hello'; par.val = 'hello'

page.appendInt('Seed')
page.appendFloat('Gain')
page.appendToggle('Enabled')
page.appendFile('Imagepath')                  # file picker
page.appendFolder('Projectroot')              # folder picker
page.appendPulse('Start')                     # momentary button -> onPulse
page.appendMenu('Mode')                       # then set par.menuNames/menuLabels
page.appendHeader('Sectionname', label='Section')  # name must be a valid id
```

### Bind a built-in par to a custom par (expression)
```python
par.mode = ParMode.EXPRESSION
par.expr = "parent().par.Spoutin.eval()"
```

### Save the .tox
```python
comp.save('C:/path/with/forward/slashes/MyComp.tox')
```

---

## The gotcha catalog

### G1 — Parameter / header names must be valid identifiers
**Error:** `First argument must be parameter name, and begin with uppercase letter
followed by lowercase letters and numbers only. Furthermore sequence parameters
cannot end with digits.`

**Cause:** every `append*` call's **first argument is the internal parameter name**
and must be a valid identifier: start with an uppercase letter, then only lowercase
letters and digits, and not end in a digit. `appendHeader('Spout / OSC')` fails —
spaces, slash, and the caps `OSC` are illegal in a *name*.

**Fix:** put display text in `label=`, keep the name clean — or drop headers (they
are purely cosmetic dividers):
```python
page.appendHeader('Spouthdr', label='Spout / OSC')   # name valid, label pretty
# or just omit headers entirely
```
Same rule applies to `appendStr`, `appendInt`, etc. Good: `Prompt`, `Spoutin`,
`Referencepath`. Bad: `spoutIn`, `Spout In`, `Step2`.

### G2 — A Text DAT caches its own copy of the script
**Symptom:** you edit the `.py` on disk, re-run the DAT, and the **exact same old
error** reappears (same line, same message) even though you fixed it.

**Cause:** when you drag a `.py` into TD as a Text DAT, the DAT stores its **own
copy** of the text. Editing the source file does not update it.

**Fix (cache-proof):** run from the Textport (Alt+T) so it reads the file fresh
every time:
```python
exec(open('C:/abs/path/to/build_script.py', encoding='utf-8').read())
```
(`encoding='utf-8'` is not optional — G25.) Alternative: on the Text DAT's **Common** page set `File` = the script path and
press **Reload** (or delete and re-drag) before each run.

### G3 — Extension promotion is fragile and fails silently
**Error (at runtime, pressing a button):** `'td.baseCOMP' object has no attribute
'Setup'` (or `'Start'`, etc.).

**Cause:** the standard way to attach an extension —
```python
comp.par.extname1 = 'MyExt'
comp.par.extobject1 = "op('MyExt').module.MyExt(me)"
comp.par.promoteextension1 = True
comp.initializeExtensions()
```
uses internal parameter names (`extname1`/`extobject1`/`promoteextension1`) that
**vary between TD builds** and can fail without raising — leaving the COMP with no
promoted methods, so `comp.Setup()` doesn't exist.

**Fix (robust):** don't depend on promotion. Have the Parameter Execute DAT
**instantiate the class from the sibling Text DAT itself** and cache one instance
per component:
```python
_INSTANCES = {}                      # comp.id -> instance, persists across pulses

def _ext(comp):
    inst = _INSTANCES.get(comp.id)
    if inst is None:
        inst = op('MyExt').module.MyExt(comp)   # sibling Text DAT named 'MyExt'
        _INSTANCES[comp.id] = inst
    return inst

def onPulse(par):
    _ext(par.owner).Setup()          # par.owner is the COMP that owns the param
```
Keep the promotion lines too if you like — but wrap each in `try/except: pass` so
they are best-effort, and never the thing the buttons rely on.

### G4 — Spout / OSC operator parameter names vary by build
**Symptom:** `[build] WARN <node> has no par 'sendername'` (or the binding just
doesn't take).

**Cause:** the internal par name for "Sender Name" / network target differs across
TD versions: Spout senders use `sendername`, Spout In may use `sender` or
`activesender`; OSC Out uses `netaddress` or `address`.

**Fix:** bind by trying a list of candidate names; warn instead of aborting the
whole build:
```python
def _try(node, parnames, expr):
    if isinstance(parnames, str):
        parnames = [parnames]
    for name in parnames:
        par = getattr(node.par, name, None)
        if par is not None:
            par.mode = ParMode.EXPRESSION
            par.expr = expr
            return
    print("[build] WARN %s has none of %s — set it by hand" % (node.name, parnames))

_try(spout_out, ['sendername', 'sender'], "parent().par.Spoutin.eval()")
_try(spout_in,  ['sendername', 'sender', 'activesender'], "parent().par.Spoutout.eval()")
_try(oscout,    ['netaddress', 'address'], "'127.0.0.1'")
_try(oscout,    'port', "int(parent().par.Oscport)")
```

### G5 — PowerShell launched from a Setup button must be ASCII-only
**Error:** `Falta el paréntesis de cierre ')' en la expresión` /
`MissingEndParenthesisInExpression`, pointing at a line that looks fine, often with
mojibake like `â€"` in the message.

**Cause:** Windows PowerShell 5.1 reads a `.ps1` with **no BOM** using the ANSI
codepage. Non-ASCII characters — em dashes `—`, box-drawing `──`, smart quotes —
get corrupted and break the parser.

**Fix:** keep `.ps1` files **ASCII-only**. Use `-` not `—`, plain `#` comment
banners not `── ──`, straight quotes. (Or save as UTF-8 **with BOM**, but
ASCII-only is simpler and bulletproof.)

### G6 — `conda` (or any tool) not on PATH for TD's subprocess
**Symptom:** the Setup/Start console flashes `'conda' is not recognized` or the
process never starts.

**Cause:** TouchDesigner launched from the Start menu may not inherit the PATH that
your interactive shell has (where conda init lives).

**Fix:**
- Expose a `Condacmd` (or `Condabat`) custom parameter; default `'conda'`, and let
  the user point it at the full path, e.g. `C:/Users/me/miniconda3/condabin/conda.bat`.
- Launch through `cmd /k` in a new console so the window **stays open** and you can
  read the error:
```python
import subprocess
CREATE_NEW_CONSOLE = 0x00000010
subprocess.Popen('cmd /k ' + command_string, cwd=root,
                 creationflags=CREATE_NEW_CONSOLE)
```
- For a clean shutdown of a launched process tree:
  `subprocess.Popen('taskkill /F /T /PID %d' % proc.pid)`.

### G7 — Make the `.tox` self-contained and portable
**Goal:** a `.tox` that works on another machine with nothing but the file itself.

**Problem:** the build script lives in your repo (`execution/...`); a dragged-in
`.tox` on a fresh machine has no access to your bridge script, installer, or lock.

**Fix:** **embed the artifacts as Text DATs** inside the COMP at build time, and on
Setup **write them to disk** under the user's chosen folder:
```python
# build time: read files from disk into Text DATs (baked into the .tox)
bridge_py = comp.create(textDAT, 'bridge_py')
bridge_py.text = open(os.path.join(PROJECT_ROOT, 'execution/td_app_bridge.py')).read()
# ... same for setup_xxx.ps1 and requirements.lock.txt

# extension Setup(): write them out, then run the installer
def _write_artifacts(self, installdir):
    bdir = os.path.join(installdir, 'bridge')
    os.makedirs(bdir, exist_ok=True)
    for fname, datname in {'td_app_bridge.py': 'bridge_py',
                           'setup_xxx.ps1': 'setup_ps1',
                           'requirements.lock.txt': 'req_lock'}.items():
        with open(os.path.join(bdir, fname), 'w', encoding='utf-8', newline='\n') as f:
            f.write(self.ownerComp.op(datname).text)
    return bdir
```
Text DAT contents are saved into the `.tox`, so the file carries everything.

### G8 — Bootstrap a fresh machine (ask for a path, install everything there)
**Goal:** pressing Setup on a clean Windows box installs git/conda/deps/models and
leaves the component runnable — reproducing the reference machine.

**Pattern (see `templates/setup_template.ps1`, in this skill's directory):**
- Expose an **`Installdir`** Folder param; install EVERYTHING under it (a conda
  **prefix env** at `<Installdir>/env`, repos/models, the written artifacts). Prefix
  envs (`conda create -p <dir>/env`) keep the stack self-contained and deletable.
- Auto-install missing tools:
  - **git / git-lfs** via `winget install --id Git.Git` / `GitHub.GitLFS`
    (Windows 11 ships winget); fall back to a manual-download message.
  - **Miniconda** silently into `<Installdir>/miniconda` if no `conda` on PATH:
    `Start-Process Miniconda3-latest.exe -ArgumentList "/InstallationType=JustMe","/AddToPath=0","/S","/D=<dir>"`.
- Things you **cannot** auto-install (GPU + driver): check (`nvidia-smi`) and warn.
- **Docker is usually the wrong tool** when the transport is **Spout** — Spout shares
  GPU textures within one Windows session; a container (GPU via WSL2) can't bridge
  Spout back to the host TouchDesigner. Prefer a native install.
- Start resolves conda as `<Installdir>/miniconda/condabin/conda.bat` (or PATH) and
  runs `conda run -p <Installdir>/env ...`. Write a small `_start.bat` and launch
  `cmd /k "<bat>"` so quoting survives paths with spaces (better than inlining
  quotes into `cmd /k`).

### G9 — conda Terms-of-Service gate blocks env creation on fresh installs
**Error:** `CondaToSNonInteractiveError: Terms of Service have not been accepted for
the following channels … repo.anaconda.com/pkgs/main …` → `prefix env creation failed`.

**Cause:** recent conda/Miniconda refuses to create an env from the **default
Anaconda channels** until their ToS is accepted. A machine where you accepted it
interactively long ago won't show this; a freshly bootstrapped one will.

**Fix (both, belt-and-suspenders):**
```powershell
# 1) accept ToS non-interactively (best-effort; older conda lacks `tos`)
foreach ($ch in @("https://repo.anaconda.com/pkgs/main",
                  "https://repo.anaconda.com/pkgs/r",
                  "https://repo.anaconda.com/pkgs/msys2")) {
    try { & $Conda tos accept --override-channels --channel $ch 2>$null | Out-Null } catch {}
}
# 2) create from conda-forge so the default channels (and their gate) are skipped
& $Conda create -p $EnvDir python=3.12 pip -y -c conda-forge --override-channels
```
Manual unblock on an already-stuck machine: run the three `tos accept` commands
with the installed conda (e.g. `<Installdir>\miniconda\condabin\conda.bat tos accept
--override-channels --channel …`), then press Setup again (idempotent).

### G10 — PowerShell wrapper functions eat short flags (`-e`, `-r`)
**Error:** `No se puede procesar el parametro porque el nombre de parametro 'e' es
ambiguo. Las posibles coincidencias son: -ErrorAction -ErrorVariable.` (when a wrapper
runs `pip install -e ...`).

**Cause:** a wrapper function that **declares a parameter**
(`param([Parameter(ValueFromRemainingArguments)]$A)`) becomes an *advanced* function
and gains the common parameters. A passed-through `-e` then prefix-matches
`-ErrorAction` / `-ErrorVariable` and binds ambiguously instead of reaching the wrapped
exe.

**Fix:** don't declare a parameter — use the automatic `$args`, which is **not** subject
to parameter binding:
```powershell
function CondaRun {
    & $Conda run --no-capture-output -p $EnvDir @args   # -e / -r pass through verbatim
    if ($LASTEXITCODE -ne 0) { throw "failed: $($args -join ' ')" }
}
```
Manual unblock for a stuck install (run the failed step yourself):
`& "<Installdir>\miniconda\condabin\conda.bat" run -p "<Installdir>\env" pip install -e "<Installdir>\FluxRT"`.

### G11 — Spout fails across two GPUs (monitor on the motherboard / iGPU)
**Error (TD side):** `Unable to open shared Spout Texture. Spout may not be Vulkan
compatible on this GPU.` — appears on a Spout In TOP even though the sender process
is confirmed publishing.

**Cause:** Spout's shared-texture handle is **adapter-specific**. If TouchDesigner
renders on one GPU and the sender process (e.g. a CUDA/PyTorch bridge) on another,
neither can open the other's texture. The classic desktop trigger: the **monitor is
plugged into the motherboard** (CPU integrated graphics), so Windows renders TD on the
**iGPU** while the bridge runs on the discrete NVIDIA card. Tell-tale: TD can *send*
Spout (its own texture) but cannot *receive* the bridge's texture; the same build works
on a machine whose monitor is on the discrete GPU.

**Fix:**
1. Plug the monitor into the **discrete GPU's** outputs (not the motherboard), reboot —
   the discrete GPU becomes primary so TD and the bridge land on the same adapter.
2. Or force both processes onto the NVIDIA GPU: Windows Settings -> Display -> Graphics ->
   add `TouchDesigner.exe` AND `<Installdir>\env\python.exe` -> High performance.

This is a **deployment** gotcha (per-machine), not a code bug. Worth a line in any
Spout-based `.tox` README. If a machine genuinely can't co-locate both processes on one
GPU, switch the return transport to **NDI** (TD's NDI In doesn't use DX shared textures).

### G12 — TouchDesigner auto-creates the callbacks DAT and yours gets ignored

**Symptom:** the operator answers with TouchDesigner's own built-in response - for
a Web Server DAT, a body reading `<b>TouchDesigner: </b>` plus the operator's name -
while your handler appears to be perfectly in place.

**Cause:** creating an operator that uses callbacks (Web Server DAT, Script TOP,
and others) makes TD auto-create a companion Text DAT named `<operator>_callbacks`,
pre-filled with its example code. Your own `create(textDAT, '<operator>_callbacks')`
then hits a name collision, and **TD silently renames yours** to `..._callbacks1`.
The callbacks parameter still points at the original - TD's template - so the
operator runs the example while your code sits in a DAT nobody references.

**Why it is vicious:** every check passes. The reference resolves (to a real DAT).
The module imports (TD's). The handler exists (TD's). Calling it returns a valid
response (with TD's body). Nothing is broken except which file is in charge.

**Fix, three parts:**
1. **Purge before creating** - destroy any operator whose name starts with
   `<operator>_callbacks`, then create yours, so the name is free when you claim it.
2. **Verify by content, not by reference** - marker in the first line, asserted
   after the build (see `debugging.md`).
3. **Flag leftovers** - a `..._callbacks1` in the component proves the purge failed.

Alternatively, sidestep it entirely: name your DAT something TD would never
auto-generate (`qr_cook` instead of `qr_callbacks`) and point the parameter there.
A collision that cannot happen needs no defence.

### G13 — Never sleep on TouchDesigner's main thread

**Symptom:** you switch something on, wait, and observe a contradiction - the
parameter reads `True` while the thing it enables plainly did not happen. Easy to
misread as a firewall or permissions problem.

**Cause:** scripts run from the Textport execute on TD's **main thread**, the same
one that cooks operators and applies parameter changes. Setting a parameter only
*queues* the change. A `time.sleep()` meant to "give it a moment" freezes
TouchDesigner itself, including the cook that would have applied it.

**Fix:** move the wait to a daemon thread (which may sleep freely but must not
touch operators), or schedule a callback with `run(func, *args, delayFrames=N)`.

**Corollary:** an HTTP request from the main thread to your own in-TD server can
deadlock, since the thread that must produce the response is the one waiting for
it. Fire it from a daemon thread with a timeout, and treat a timeout as evidence.

### G14 — The `.tox` is a build artifact; loading it duplicates the component

**Symptom:** duplicated log lines, a port occupied before you enable anything, or
a component that "works sometimes". Frequently mistaken for flaky code.

**Cause:** the build script is the source of truth and the `.tox` is its output.
Drag the `.tox` into the network and a **second copy** of the component exists.
Two copies fight over anything exclusive - a port, a log file - and the loser fails
silently. Worse, a `.tox` saved before a fix keeps the defect forever while looking
identical from the outside.

**Fix:**
- Rebuild from the script; never drag the `.tox` in to work with it.
- Make the build idempotent **across the whole project**, not just the root:
  destroy every copy of the component wherever it lives. Being idempotent about
  one location is being blind about every other.
- Git-ignore the `.tox`. Versioning it means versioning a binary that drifts from
  its script.

### G15 — `cmd` deletes the outermost quote pair

**Symptom:** launching an external program fails with an error naming a path
fragment you never wrote, e.g. `"C:/Program" is not recognized as an internal or
external command`.

**Cause:** `cmd /c` and `cmd /k` remove the **first and last** quote character of
the whole command line. With one quoted argument that is harmless; with **two** -
typically an executable and a file, both in paths containing spaces - the
executable's closing quote disappears and the shell splits it at the space.
Measured:

```
cmd /c "<exe with spaces>" --version                 -> works
cmd /c "<exe with spaces>" --logfile "x y.log"       -> fails as above
cmd /c ""<exe with spaces>" --logfile "x y.log""     -> works
```

**Fix:** write the command to a `.bat` and launch that (the same remedy as G8 for
spaced paths). It bypasses cmd's quote parsing entirely and keeps the command
readable, unlike the double-wrapping form which breaks the next time someone edits
it.

### G16 — A scheduled delay is measured against the root timeline

**Symptom:** a status parameter freezes on an in-progress value forever, with no
error anywhere — and a pulse button that does the same work by hand fixes it
instantly. More generally: the server answers, buttons work, parameters read
correctly, and **nothing deferred ever happens**. Uploads arrive and never load.

**Cause:** `run()`'s docstring in the install: *"`delayRef` — ... If no `delayRef`
is provided, uses `root`"*. So `run(f, delayFrames=30)` waits for thirty frames of
the **root timeline**. Stop that timeline and those frames never arrive; the call
does not raise and is not dropped — it stays queued forever. `delayMilliSeconds`
is no escape: the docs say it is "rounded to the nearest frame". The same stopped
timeline kills every `onFrameStart` executor at once, so two independent deferral
mechanisms fail together and look like two separate bugs. A pulse button keeps
working throughout, because a pulse needs no frames — which is the tell.

**Fix:** anchor the delay to a clock the timeline cannot stop — `op.TDResources`
(the built-in independent time component the `run()` docs name for this) plus
`wallTime=True`, which measures real elapsed time instead of frames.

**Check the resolved clock for `None` before passing it.** `delayRef=None` is
run()'s own default, so a missing operator does not raise — it silently reverts to
the root timeline, reproducing the bug with no fallback triggered.

**And say it on the panel.** "No frames are advancing" is otherwise
indistinguishable from "still working on it". Cheapest detector: `onFrameStart`
increments a counter in component storage; snapshot it when the deferred work
starts and compare later. If the counter cannot be read, report nothing — a false
alarm on a panel during a show is its own kind of damage. See `debugging.md` § G16.

### G17 — Resizing a Script CHOP destroys its channel names

**Symptom:** a Geometry COMP that reads instancing channels by name draws
nothing, with no error anywhere. The CHOP's data is correct in shape and
values — but its channels are called `chan1`…`chanN`.

**Cause:** `copyNumpyArray()` RESIZES the operator, and resizing recreates the
channels with default names, discarding what `appendChan()` set moments
earlier. Wiring parameters by channel name (done precisely so a rename would
fail loudly) does not help: the rename comes from inside the CHOP, after the
names were set, and nothing reports it.

**Fix:** `appendChan` + `numSamples` + per-channel `scriptOp[name].vals =
array`. Bulk-assigning a few hundred floats per channel per frame is noise.
Verify the seam from both sides: read which channel names the Geometry COMP
asks for and confirm the CHOP publishes exactly those.

### G18 — Texture 3D TOP records every frame by default, and sizing depends on it

**Symptom (Active on, the default):** the array fills with copies of whatever
the input shows — 200 slices of the same image within seconds. Any careful
slice-at-a-time admission is drowned out.

**Symptom (Active off):** the cache keeps the resolution it was BORN with
(observed: 128×128 against a 1280×1280 input) — the recorder was also the only
thing that adopted the input's resolution.

**Cause:** the stub: while Active is 1 the TOP "replaces a slice of its 3d
data with its input every frame", wrapping when full. It is a continuous
recorder, not passive storage.

**Fix:** `active=0` for explicit-write designs (Replace Single + Replace
Index), AND set an explicit custom output resolution so the cache allocates
correctly regardless of when the input connects. Verify delivered size.

### G19 — Viewer-only parameters: `fillmode` does not touch the pixels

**Symptom:** photos normalised into a square resolution arrive stretched even
though `fillmode` is set to Fit Best.

**Cause:** the stub is explicit: fillmode "determine[s] how the TOP image is
displayed in the viewer". It is cosmetic. Forcing a custom resolution on a
Movie File In stretches the pixels; no viewer setting undoes that.

**Fix:** normalise with a Fit TOP (its `fit` parameter operates on the data;
menu names: fill/fithorz/fitvert/fitbest/fitoutside/nativeres), background
alpha 0 for the letterbox bands. Keep the loader at native resolution.

### G20 — "paths" parameters silently reject OP objects

**Symptom:** a parameter that references another operator stays empty after
the build sets it, with no warning; the only symptom is downstream (instances
without textures).

**Cause:** parameters documented as taking "the paths of one or more TOPs"
(e.g. `instancetexs`, wildcards supported) are STRING parameters. Assigning an
OP object — which works on true OP-reference parameters like `material` — is
rejected without error.

**Fix:** assign `node.path` (or a relative path string). Read the parameter
back in the build's verify step: non-empty or fail by name.

### G21 — The Projection TOP's fisheye is centred on the camera's VIEW axis

**Symptom:** in a dome build, everything piles into the **top arc** of the
domemaster with the lower half empty; content "behind" the audience is
missing entirely; and rotating the camera to fix it slides the image
sideways instead of turning it around the centre.

**Cause:** the scene was authored with the dome's zenith along **+Y** (the
intuitive "sky"), but the Projection TOP converts a cube map into a fisheye
centred on the direction the camera **looks** — TouchDesigner's -Z. The
scene's zenith therefore lands on the disc's RIM, not its centre. Two
consequences follow arithmetically and match the symptom exactly: every
object at positive elevation has a positive image-Y, so all of them sit in
the upper half; and anything more than 90° off the view axis is outside a
180° fisheye and is simply not drawn.

**Fix:** make the dome's axis BE the view direction, in your own maths:

```python
# elevation 90 -> disc centre, elevation 0 -> disc rim, azimuth -> a circle
rim = radius * cos(elevation)
tx  = rim * sin(azimuth)
ty  = rim * cos(azimuth)
tz  = -radius * sin(elevation)
```

Do the calibration rotation the same way — add degrees to every azimuth —
rather than rotating the camera. A rotation you compute is a rotation you
can verify; `rx/ry/rz` exist on the Projection TOP too ("rotate the map on
any axis") but they rotate the RESULT, which is a different operation.

**How it was caught, and the transferable part:** by having the component
save its own outputs as PNGs and READING them, instead of reasoning about
what it should look like. A render bug that is invisible to every static
check is visible in one frame of output.

### G22 — Aspect ratio is not resolution, and a size check that ignores it proves nothing

**Symptom:** a 16:9 output behaves square everywhere downstream — the user
reports "it's still 1:1" while the build log insists the resolution is
1280x720, so the report and the screen disagree and the report is believed.

**Cause:** the stub says it outright: *"You can define images with
non-square pixels using xres, yres, aspectx, aspecty where xres/yres !=
aspectx/aspecty"*. A TOP's declared **aspect** can contradict its pixel
count, and it is inherited from inputs — so compositing a 16:9 render with
a SQUARE input (a QR, a dome plate) can hand the square aspect onward while
every resolution reads correctly.

**Fix:** state `outputaspect` (menu: use the resolution) on every node of
the chain rather than letting it be inherited, and **verify `.aspect`, not
just `.width`/`.height`** — TOPs expose `aspect`, `aspectWidth`,
`aspectHeight`. The general lesson: a verification that measures the wrong
property is worse than none, because it converts "unknown" into "confirmed".

### G23 — Look At overrides rotation parameters, and never sets which edge is up

**Symptom:** an object aimed with Look At comes out **tilted**, by roughly
whatever angle you moved it around the scene — and writing `rz` to
straighten it changes nothing.

**Cause:** Look At orients the object's FACE toward a target and derives
the remaining freedom itself, so the "up" edge drifts as the object's
bearing changes. It also *takes over* the rotation channel: the parameters
you write are silently discarded.

**Fix:** for anything whose angle must be exact (a QR code, text, a logo),
drop Look At and compute the Euler angles. TouchDesigner applies X, then Y,
then Z, so for an object at (azimuth, elevation) on an axis-centred dome:

```python
geo.par.lookat = ''            # or the computed angles are thrown away
geo.par.rx = 90 - elevation    # tilt its face back down the dome axis
geo.par.ry = 0
geo.par.rz = -azimuth + tilt   # carry the up-edge round with the bearing
```

Assert the emptiness of `lookat` in the build's verify step: if anything
restores it, the object goes back to leaning with nothing to explain why.
Objects whose rotation is *meant* to be arbitrary (drifting photos) can keep
Look At happily — this is about the ones that carry information.

### G24 — Standard SOP attributes reject a default, loudly, and only at cook time

**Error (in the Script SOP's own cook, not at build time):**
`td.tdError: Cannot specify default for standard attributes.`

**Symptom if you only read the build log:** the component builds and saves,
one output is full and the other is EMPTY. A Script CHOP beside it can
produce hundreds of samples while the SOP cooks to zero points, because the
exception happens inside `onCook` and is reported there, not by the build.

**Cause:** the stub is explicit. Standard attributes — **N (normal), uv
(texture), T (tangent), v (velocity), Cd (diffuse colour)** — have implied
defaults and `create()` raises if you pass one. Custom attributes are the
opposite: they need a default to define their size and type.

**Fix:**

```python
_STANDARD = ('N', 'uv', 'T', 'v', 'Cd')
if name in _STANDARD:
    scriptOp.pointAttribs.create(name)          # no default
else:
    scriptOp.pointAttribs.create(name, (0.0, 0.0, 0.0))
```

**The transferable part is the detection, not the rule.** A build script that
only checks "did the operators get created" would have shipped this. What
caught it was the build's verify step COOKING both outputs and comparing
them: two operators fed by one shared maths module must agree on how many
points they made, and 241 vs 0 is a contradiction no amount of green
operator-exists checks would surface. When a component has two outputs that
should agree, make the build assert it.

### G25 — `open()` in TouchDesigner decodes as cp1252, and a wrong decode can run silently
**Error:** running the canonical line, before a single `[build]` print:
`UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 64:
character maps to <undefined>` from `encodings/cp1252.py`.

**Cause:** TD's embedded Python on Windows opens text files with the system
code page (cp1252) when `open()` gets no `encoding`. A build script saved as
UTF-8 that carries ANY non-ASCII character — an `Á` in the docstring, `Sesión`
in a default string — hands cp1252 the bytes `C3 81`, and `0x81` is undefined
there. Whether it crashes is luck: `é` is `C3 A9`, both defined, so a script
with only `é`s **runs to completion with mojibake** (`SesiÃ³n`) baked into its
Text DATs and painted on screen, and nothing in the build log says so. Two
sibling scripts in the same project were ASCII-only and never hit it; the
first one written in Spanish did, on its first run.

**Fix, both halves:**
1. The canonical run line names the encoding — always, not only for scripts
   known to carry accents:
   ```python
   exec(open('C:/abs/path/to/build_script.py', encoding='utf-8').read())
   ```
2. The script refuses to run mis-decoded. A literal non-ASCII probe at the top
   is two characters long after a wrong decode and one after a right one:
   ```python
   _ENCODING_PROBE = "é"      # a literal non-ASCII character, on purpose
   if len(_ENCODING_PROBE) != 1:
       raise RuntimeError("this file was decoded with the wrong codec - run it as "
                          "exec(open(path, encoding='utf-8').read())")
   ```
   The probe cannot catch the undefined-byte crash (that happens before any
   line runs), but it turns the silent case — the dangerous one — into a loud
   one. Keep the probe a LITERAL: the escape `\u00e9` is ASCII in source and
   always decodes to one character, so it probes nothing.

### G26 — Injected TD names are not guaranteed to be in globals()

**Symptom:** a builder reaches a split helper and raises `KeyError: 'textDAT'`
at `comp.create(types[kind], name)`. A related entrypoint bug silently skips
building when it checks `'op' in globals()`.

**Cause:** Python resolves bare names in both module globals and builtins.
TouchDesigner can expose its operator classes and `op` through builtins, so
`textDAT` works but `globals()['textDAT']` fails. Passing `globals()` as a
factory registry silently drops dependencies that the helper then needs.

**Fix:** resolve a bounded, explicit map at the call site:
```python
factories = dict(textDAT=textDAT, constantTOP=constantTOP, pbrMAT=pbrMAT)
build_materials(comp, factories)
```
Detect `op` with ordinary name lookup (`try: op` / `except NameError`) when
guarding a script entrypoint. Do not infer availability from globals membership.

**Regression:** execute the actual caller's map construction AND helper call,
first with factories in globals, then with them only in `__builtins__`.
The old test handed the helper a perfect synthetic dictionary; it verified
the helper but missed the production boundary. Require the original caller
to fail first, then pass with the fix. `check_td_namespace.py` travels with
this skill and checks the static pattern plus a builtins-only reproduction.
Native operator names/menus/GPU behaviour remain separate checks.

### G27 — Menu labels are not enum IDs; permissive mocks conceal the mismatch

**Observed error:** `slotlit0.srcblend: expected ('srcalpha',); got [...]`,
where the real menu contained `sa` and `omsa` rather than the guessed names.
The helper's strict validation stopped the build; older permissive setters
could merely warn and leave a default blend value in place.

**Fix:** source alpha is `sa`; one-minus-source-alpha is `omsa`. Use actual
`par.menuNames`, not display labels or plausible names borrowed from another
API. Compatibility candidates may follow the native values:
```python
menu(mat, 'srcblend', ('sa', 'srcalpha'))
menu(mat, 'destblend', ('omsa', 'oneminussrcalpha', 'invsrcalpha'))
```
Source and destination menus differ. Keep independently observed/documented
fixtures for EACH parameter. A fake menu containing all the implementation's
requested strings cannot detect enum mistakes; TDI parameter annotations prove
that a parameter exists, not that its requested menu item exists.

**Regression:** first reproduce the exact captured menu failure, then assert
the selected values for every affected material. Sweep focus, QR, fallback
and sibling components. Run the skill's `check_td_menu_ids.py`; it guards
this known literal mistake, not every possible TouchDesigner enum.

Source: [Derivative MAT blend parameters](https://docs.derivative.ca/Select_MAT).

### G28 — Correct node type and live pixels do not prove source identity

**Symptom:** the displayed scene changes, but a photo reflection or other
consumer keeps showing a different visual. No shader errors; the map may even
animate normally.

**Observed class:** two instances of the same background component existed at
different hierarchy levels. The consumer resolved the root copy while the user
operated the nested copy. Both were valid, with different scene selections.
Advancing cook counters and changing map pixels ruled out a frozen map but did
not establish that the source was the intended one.

**Fix:** inspect evaluated references and full operator paths; bind the consumer
to the exact instance the user controls. Do not guess how a relative reference
resolved from its text alone, and do not automatically rebind intentional copies.
Use `debugging.md`'s G28 workflow to distinguish identity, cooking and pixel motion.

**Live configuration versus generation:** changing an existing source parameter
is effective in the running project and does **not** require regenerating a
`.tox`. Save the `.toe` to retain the scene's wiring. Rebuilding is for changes
to generated operators or embedded code, not the default response to a wrong
reference. If a standalone component must carry the changed configuration,
exporting its `.tox` is a separate action; references to external components
still depend on their presence and paths in the receiving project.

**Verification boundary:** check the resolved path after assignment and exercise
the intended scene menu, including its crossfade. Native pixel movement at one
map does not prove final material appearance. A simulation cannot identify which
copy is active in the user's project; a literal static checker cannot establish
the user's intended instance. Diagnose live rather than inventing that evidence.

### G29 — Unit menu IDs, labels and abbreviations are different contracts

**Observed failure:** a note renderer build stopped at
`Unsupported note parameter fontsizexunit: Pixels`. The submitted traceback
did not include its native menu lists. The helper compared the requested
string to case-sensitive IDs, then to full display labels. That cannot resolve
a lowercase ID with an abbreviated label. The exact native list was NOT
captured; do not turn a plausible synthetic example into a claimed observation.

**Fix:** read `par.menuNames` and `par.menuLabels` from the actual parameter.
Prefer the exact ID, then case-insensitive ID/label equality. For parameters
ending in `unit`, allow the bounded pixel vocabulary `pixels/pixel/pix/px`.
Return the matching native ID, not the candidate label. Refuse ambiguous or
unavailable values. Do not choose index zero, use arbitrary substring matching,
or continue with a default that could silently change the text's scale.

Sweep siblings: font X/Y units, border/position/spacing units WHEN exposed by
that operator version, alignment, auto-fit and shader-version menus. Do not
invent optional parameters or infer their units from another operator. A
missing optional parameter is different from an incompatible required menu.

Use `templates/td_preflight.py::set_menu` for a direct setter, or `menu_value`
inside a project's adapter. The setter includes operator path, parameter,
requested value, names and labels if resolution fails; missing required
parameters fail distinctly, while explicitly optional ones can be skipped.
For literal text, preserve `.val` assignment and disabled legacy parsing;
never switch user text to expression mode as a workaround.

**Regression:** `check_td_preflight.py` loads the shipped helper and exercises
lowercase IDs, abbreviated labels, missing labels, valid IDs, unrelated units
and ambiguity. Those menus are SYNTHETIC robustness cases. Add captured native
lists to the consuming project's test when available, and test the actual
call-site values against them. Offline success does not verify glyph coverage,
circle clipping or native rendering. The operator-run build should compile
one representative note/shader before saving the completed component.

Source: [Derivative Text TOP](https://docs.derivative.ca/Text_TOP) documents the
unit choices and text parameters; it does not establish the enum list exposed
by every installed version.

### G30 — Reusing source does not transfer its imported globals

**Observed failure:** an AST-loaded base builder reached `build()` and raised
`NameError: name 'os' is not defined`. Separately, a startup could do nothing
when TD's `op` was present only in builtins (G26). Syntax compilation and
mocking only the final helper did not exercise these namespace boundaries.

**Fix:** each source/embedded DAT owns its imports. Resolve TD factories in the
calling TD context and pass an explicit map. Load reusable definitions without
their auto-build entrypoint; do not execute the older build as a side effect.
After definitions load, inspect global dependencies against that ACTUAL scope,
including either a builtins dictionary or module, before mutating the network.
The portable `validate_globals` helper uses Python's symbol table for this.
Its docstring names the limits: dynamic exec/import, embedded strings, optional
branches and globals created later require separate treatment. Never call the
check against the caller's richer namespace to make it pass.

**Recovery:** a failure can leave an incomplete component without its final
runtime DAT. Identify it by embedded version markers, not only its name or
late-created nodes. Refuse ambiguous targets and active services; preserve
other versions/data. Export only after all adapters and native preflights
succeed. A failed export/build is not a verified working artifact.

**Regression:** the shipped checker executes definitions in a fresh namespace,
proves a missing `os` is rejected before construction, then passes with the
explicit import. It also tests TD names in globals and builtins and function-
local imports. The consuming project must exercise its actual final entrypoint
and dependency handoff, plus partial-build selection, without running the show.

### G31 — A GLSL TOP takes at most 3 inputs; wiring from the source's output replaces input 0

**Observed (TD 2025, a component whose mark shader had 6 inputs):** first
`IndexError: list index out of range` at `glsl.inputConnectors[3].connect(src)`;
then, with a "fallback" that connected from the other side, the build's own
check printed `cardimg (3 connectors) ... inputs are now ['mark_inside',
'mark_lockupline', 'mark_partners']` — the fourth input had REPLACED the first.
A Composite TOP offers its next connector immediately (six Text TOPs wired by
index without trouble); a plain GLSL TOP stops at three. A builder that only
ever wired two inputs to a GLSL TOP never sees the limit.

**Fix:** a shader with more than 3 inputs is a **GLSL Multi TOP**
(`glslmultiTOP`: same pixel DAT, `vec` uniform sequence and input filtering as
the GLSL TOP). Wire with `dst.inputConnectors[i].connect(src)` in order and
assert `dst.inputs[i] == src` afterwards; on `IndexError`, fail naming the
operator type and its connector count. **Never** use
`src.outputConnectors[0].connect(dst)` as a fallback: it targets input 0, so it
silently rewires an input the shader already depends on — the shader then
compiles and draws the wrong texture in that slot.

### G32 — A Composite TOP with one input is an error, and per-state errors hide from a single check

**Observed:** `Error: Not enough sources specified` on a Composite TOP whose
inputs are rewired per state (the glowing text lines of the current cue plus a
transparent base). The one state with no glowing line left it with a single
input. The build had verified every *shader* and saved; the error was found by
the operator inside the saved component.

**Fix:** keep two transparent bases (two Constant TOPs, alpha 0) so the
Composite never drops below two inputs. **And verify the whole network in every
state it can be put in:** after the build, step the component through each
state (menu entry, mode) with the extension's own refresh, cook EVERY TOP of the
component and collect `errors()` with the state name; skip only inputs that are
legitimately empty (an unconnected In TOP and its first consumer). A check on a
hand-picked list of operators, in the one state the build leaves selected, is
the shape this bug survived.

### G33 — Text TOP antialias and Movie File In alpha: read the menu, measure the convention

**Observed:** the Text TOP's `antialias` menu is `menuNames` `aa1, aa2, aa4,
aa8, aa16, aa32` with `menuLabels` `1x (Off), 2x, 4x, 8x, 16x, 32x`. Candidates
such as `('on', 'high', 'yes', 'true')` match nothing, and an optional setter
leaves TD's default with only a warning line — two components built that way
before anyone read the warning. Movie File In exposes **no** premultiply
parameter (`premultiply` / `premultrgb` both absent); measured on a PNG with an
antialiased edge, it hands the image over **premultiplied** in that build.

**Fix:** pass the real ids (`('aa4', '4x')`) and make the setter required, so a
mismatch stops the build (G27/G29). For image alpha, do not assume: sample an
asset whose ink colour is known on its antialiased edge (0.15 < a < 0.85) and
compare `max(rgb)` with `ink * a` — about 1 means premultiplied, about `1/a`
straight — then let the consuming shader premultiply only when the measurement
says straight. Report the measured convention in the build's verify output.

### G34 — Probe geometry inside large solid areas, and say what the probe can prove

**Observed:** a dome-mapping probe that took the first opaque card pixel on a
coarse grid landed on a thin stroke (1–2 px once the 3200 px card is minified
about 2x onto the 4096 master). TD read 0.733 where the card held 0.929 — the
same hue, partial coverage — and the build refused to save; the browser preview
of the same shader read 0.922 at the same point. A probe that sensitive to half
a pixel produces false failures and, worse, invites "tuning the tolerance".

**Fix:** probe only points whose whole neighbourhood is solid (alpha > 0.97 at
the point and at ±k of the card around it, k several master pixels), take
several points far apart, and compare colour. Run the probe offline first on
the preview's own card and master to prove the probe code and the inverse
mapping (difference 0.000 there), then trust it in TD. State its limit: it
confirms placement to the neighbourhood's size, not to the pixel — a visual
look at the output stays part of the verification.

### Reproducibility with a lockfile
`requirements.txt` is often loosely pinned. To reproduce a machine **exactly**,
capture the working env and ship the result:
```
conda run -n <env> pip freeze > requirements.lock.txt
```
Then **filter** before shipping:
- Remove GPU `torch`/`torchvision` (the `+cuXXX` local version needs a special
  index) and install them separately with `--index-url`.
- Remove editable installs (`-e ...`) and re-create them from the clone.
Everything else stays pinned. Embed the lock in the `.tox` (G7) so Setup installs
from it.

---

## Parameter Execute DAT wiring (the control surface)

A Parameter Execute DAT watches a COMP's parameters and fires callbacks. Configure
it to watch the **parent** COMP:
```python
pexec.text = PAREXEC_CODE
try:
    pexec.par.op.val = '..'          # watch the parent COMP
    pexec.par.pars = '*'             # all parameters
    pexec.par.valuechange = True
    pexec.par.onpulse = True
except Exception as exc:
    print("[build] WARN parexec config: %s" % exc)
```
Callback signatures: `onValueChange(par, prev)`, `onPulse(par)`,
`onValuesChanged(changes)`. Inside, `par.owner` is the COMP that owns the parameter.

---

## Embedded-extension pattern (process control + OSC/Spout dispatch)

Put a Python class in a Text DAT inside the COMP. It holds state (e.g. a launched
`subprocess.Popen` handle) and exposes methods the parexec calls. The reference
implementation was FluxRT's `EXTENSION_CODE` block and its bridge script — both in
another project, so the key points are spelled out here rather than linked:
- `__init__(self, ownerComp)` — store `self.ownerComp`; read params via
  `self.ownerComp.par.Xxx.eval()`.
- Send OSC via the internal DAT: `self.ownerComp.op('oscout').sendOSC(addr, [args])`.
- Launch external processes with `cmd /k` + `CREATE_NEW_CONSOLE` (G6).
- Don't store non-serializable handles in `comp.store()` (TD will warn on save);
  keep them in the cached instance (G3) instead.
