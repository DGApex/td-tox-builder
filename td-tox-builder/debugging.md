# Debugging a `.tox` — the method

> Companion to `SKILL.md`. Load this when a component builds cleanly but does not
> behave, or when a symptom has survived one round of guessing.
>
> Self-contained by design: everything needed is here. It does not depend on any
> project's notes.

## The governing fact: TouchDesigner failures are usually silent

A `.tox` has almost no failure surface that raises. Operator-reference parameters
accept any string. Missing parameters vanish into `getattr(..., None)`. Callbacks
that die get replaced by a built-in default. A trigger parameter that was never
switched on simply never fires.

So the default symptom is **"everything reports success and nothing works"**, and
the default mistake is to trust that a check passing means the thing it checked is
correct. Every technique below exists to convert a silent failure into a loud one.

**The rule that generalises:** an existence check is not an identity check. A
reference resolving says nothing about *what* it resolved to.

## Order of diagnosis — cheapest first

1. **Count the copies.** Before suspecting code, ask how many instances of the
   component exist. Two copies of anything that binds a port or writes a file will
   fight, and the loser fails without a word.
2. **Check identity, not existence.** Does the operator reference point at *your*
   code, or at something that merely exists?
3. **Call the handler by hand.** Take TouchDesigner's dispatch out of the picture.
4. **Then, and only then**, suspect the network, the firewall, or the library.

Skipping to step 4 is how a session gets spent blaming a firewall for a quoting
bug.

## G28 — A moving image can come from the wrong component copy

When a reflection, preview or background disagrees with a scene selector,
first identify which selector the user means (the component's own menu or an
external Switch/Select TOP). Do not add another selector before resolving that
ambiguity. Two valid copies can render different scenes without any error.

1. Enumerate relevant component instances with **full paths and selected scene**.
2. Report the consumer's evaluated source parameter and the actual Select TOP /
   environment-map references. Compare those paths with the instance whose menu
   the user operates. Inspect upstream connections, locks and bypass flags.
3. Sample cook counters at spaced times without force-cooking. Increasing cooks
   prove evaluation, not visible motion. If needed, compare pixels of a small
   intermediate map at multiple times; do not download full photo/output frames
   unnecessarily. A pixel change proves that map changes, not that the correct
   source was selected or that the final material refreshes.
4. If the source is the wrong copy, correct **only the consumer reference** to the
   verified intended instance. Do not delete copies, alter their scene menus,
   force-cook every frame, rewrite shaders or rebuild as a routing workaround.
5. Recheck the resolved path and change the intended scene menu. Confirm its
   transition reaches the consumer. Save the `.toe` to retain the project-level
   connection; exporting a `.tox` is a separate packaging action if requested.

Schedule observations through `op.TDResources`, never `time.sleep` on TD's
thread. A stopped map may be correct for a paused/static visual or unused branch.
Do not report the inactive duplicate's counters as the active instance's state.
If native access is unavailable, provide a bounded read-only Textport diagnostic
and request its output. An offline preview cannot determine live source identity.

**Worked diagnosis:** `/show/Consumer` reads `/Background/outlight`, whose scene
is A, while the user controls `/show/Background`, whose scene is B. The consumer's
map pixels change over time. Conclusion: animated map, wrong source instance;
the fix is the consumer reference, not an animation or rebuild fix. Full rationale
and persistence distinction: `reference.md`, G28.

## Build stopped before export: units or isolated globals (G29/G30)

- For `Unsupported ... fontsizexunit`, inspect the failed node's actual
  `par.menuNames` and `par.menuLabels`; report both along with the full node
  path. Do not claim the user's enums are known if their traceback omitted
  them. Use the bounded resolver in `templates/td_preflight.py`, then check
  sibling units and other menus used by the same new rendering branch.
- For `NameError: os` inside an exec-loaded builder, inspect that builder's
  namespace/imports, not the Textport's globals. Run dependency preflight
  before any network mutation, and test the real factory handoff (G26).
- Reproduce with a strict test that fails under the old code. State whether
  fixture menus are native captures or synthetic cases. Keep the service off
  after failure and recognize the partial component by version markers for
  a safe retry. Do not rebuild another component or erase collections.
- After the code fix, give the fresh UTF-8 `exec(open(...).read())` command.
  An offline check passing means the regression is covered; native success
  remains pending until the operator actually retries and observes it.

## Technique: write a diagnosis script, do not debug by clicks

Put it in `execution/diagnose_<name>.py` and run it from the Textport the same way
as the build script. Debugging through the UI means asking someone to click things
and describe what they see, which is slow and loses precision.

A good diagnosis script:

- Interrogates the running component and prints its real state - every parameter
  that matters, resolved, not assumed.
- Fixes what it safely can (switching a server on) instead of only reporting.
- **Distinguishes failures that need different responses.** "No log file at all"
  and "log exists but is empty" call for opposite next steps.
- Ends by naming the single most likely cause, not by dumping data.

## Technique: verify by content with a marker

Put a unique marker in the first line of every embedded program:

```python
CALLBACK_MARKER = 'MYCOMP_CALLBACKS_V1'
CALLBACKS = r'''# MYCOMP_CALLBACKS_V1
...
'''
```

Then the build asserts the reference lands on *that* text:

```python
target = server.par.callbacks.eval()
if not hasattr(target, 'text'):
    target = comp.op(str(server.par.callbacks.val).strip() or '')
if target is None or CALLBACK_MARKER not in target.text:
    problems.append('callbacks does not point at our code')
```

**Why this earns its place.** TouchDesigner auto-creates its own callbacks DAT for
several operator types, claiming the name before you do; yours gets renamed with a
trailing digit and silently ignored. Everything then passes: the reference
resolves, the module imports, the handler exists, calling it returns 200 - all of
it TouchDesigner's template. Only the content check catches it.

A version suffix in the marker (`_V2`) also lets the diagnosis tell current code
from a stale rebuild, which is worth having the moment you edit an embedded
program twice.

## Technique: call the handler directly

For a split builder, test the caller as well as the helper. A helper given a
hand-crafted dependency dictionary can pass while the real call uses
`globals()` and loses TD factories exposed in builtins. Reproduce both Python
namespace layouts and run `check_td_namespace.py` (reference G26) before
investigating native parameters or shaders.

```python
module = comp.op('mycomp_callbacks').module
result = module.onHTTPRequest(server, {'method': 'GET', 'uri': '/'}, {})
```

This splits one ambiguous symptom into two precise ones:

- **Works when called directly** → your code is fine and TouchDesigner is not
  routing to it. Look at the reference, the trigger parameter, a stale copy.
- **Raises** → you get the traceback instead of a silent fallback to a default.

**Read the size of what comes back.** A response whose body is exactly the length
of a built-in default page is the built-in default page. That single number -
31 characters for `<b>TouchDesigner: </b>webserver` - is what identified a hijacked
callbacks DAT after an hour of looking elsewhere.

## Technique: never let the instrument answer the question

A synthetic call made from the Textport runs on the main thread **by
construction**. If your instrumentation reports "which thread am I on" during that
call, it measures the instrument.

Worse, one-shot reports get consumed: the synthetic call prints the block, and the
real event that follows prints nothing.

Mark synthetic input and refuse to count it:

```python
synthetic = bool(request.get('x-mycomp-synthetic'))
if synthetic:
    _log('(synthetic call - proves nothing about routing, not counted)')
    return
```

And re-arm one-shot reports before the real test, so the measurement you came for
is guaranteed to appear.

## Technique: never sleep on the main thread

Every script run from the Textport runs on TouchDesigner's main thread - the same
thread that cooks operators and applies parameter changes. `time.sleep()` there
does not wait, it **freezes TouchDesigner**, including the work being waited for.

Setting a parameter only queues the change; TD applies it on the next cook. So
this reports a contradiction:

```python
server.par.active = 1
time.sleep(0.5)                 # TD cannot cook - it is frozen inside this call
print(server.par.active.eval()) # True
print(port_is_listening())      # False  -> "must be the firewall"
```

Move waiting to a daemon thread, or to a scheduled callback via `run()`. A daemon
thread may sleep freely; it must not touch operators.

**Corollary:** an HTTP request made from the main thread to your own in-TD server
can deadlock, because the thread that must build the response is the one blocked
waiting for it. Fire such requests from a daemon thread with a timeout - and read a
timeout as a finding, not as an error.

## Technique: schedule with `run()` instead of depending on an executor

Work driven from `onFrameStart` depends on an Execute DAT being armed. When arming
fails silently you get two working halves and no connection between them.

`run()` schedules onto the main thread with no operator needing to be enabled:

```python
def poll(comp, attempts_left):
    if done(comp):
        return
    if attempts_left <= 0:
        report(comp, 'gave up: <specific reason>')
        return
    schedule(poll, comp, attempts_left - 1)     # see the clock rule below
```

Self-rescheduling bounds the retries for free and gives a natural place to report
a specific reason on giving up. Prefer the callable form `run(func, *args)` over a
code string - no operator path gets interpolated, so a rename or a space in a path
cannot break it.

### G16 - a scheduled delay is measured against the ROOT TIMELINE by default

**This technique's obvious form is a trap, and this document used to teach it.**
`run()`'s own docstring in the install states it:

> `delayRef` - Specifies an optional operator from which the delay time is
> derived... **If no `delayRef` is provided, uses `root`**

So `run(f, delayFrames=30)` waits for thirty frames *of the root timeline*. Stop
that timeline - pause it, or open a project that is not playing - and those frames
never arrive. **The call does not raise and is not dropped: it stays queued
forever.** Same for `delayMilliSeconds`, which the docs say is "rounded to the
nearest frame".

Anchor the delay to a clock the timeline cannot stop:

```python
clock = None
try:
    clock = op.TDResources          # built-in independent time component
except Exception:
    clock = None

if clock is not None:               # None is run()'s DEFAULT - see below
    run(poll, comp, n, delayMilliSeconds=500, wallTime=True, delayRef=clock)
else:
    report(comp, 'degraded: delay needs the timeline running')
    run(poll, comp, n, delayFrames=30)
```

**Check the clock for `None` before passing it.** `delayRef=None` is run()'s own
default, so handing it a missing operator does not raise - it silently reverts to
the root timeline and reproduces the exact bug, with no fallback triggered and
nothing on the panel.

**The wider rule, which matters more than the tunnel case that found it:**
*everything* a component defers - `run()` callbacks and every `onFrameStart`
executor alike - is dead while frames are not advancing, and dead in the most
misleading way available: the server still answers, buttons still work, parameters
still read correctly, and nothing deferred ever happens. Uploads arrive and are
never applied. If a component defers work, it must be able to say "no frames are
advancing" on its panel, because that state is otherwise indistinguishable from
"still working on it".

Cheapest detector: have `onFrameStart` increment a counter in component storage,
snapshot it when the deferred work starts, and compare later. If the counter has
not moved, frames are not advancing. If the counter cannot be read, say nothing -
a false alarm on a panel during a show is its own kind of damage.

## Technique: report failure loudly at the point of the skip

Any code shaped like "do it if it exists" needs an else branch that says something:

```python
armed = False
for name in ('framestart', 'onframestart'):
    par = getattr(frameexec.par, name, None)
    if par is not None:
        par.val = True
        armed = True
        print("[build] frame executor armed via '%s'" % name)
        break
if not armed:
    print('[build] ERROR could not arm the frame executor.')
    print('[build]       Deferred loading AND URL detection are both dead.')
```

Name the *features* that die, not just the parameter that is missing. The person
reading the log knows what a broken feature looks like; they do not know what
`framestart` does.

## Symptom → cause table

| Symptom | Look at | Ref |
|---|---|---|
| Server answers a built-in default page | callbacks DAT hijacked by TD's auto-created one; check by marker | this file, and G-catalog |
| Duplicated log lines | two copies of the component alive | destroy all copies, not just the one at the root |
| Port busy before you switch the server on | another copy, or another program | census; move the port |
| Status stuck on an in-progress value forever | the poller never runs, or never times out | `run()` + bounded retries |
| Status stuck AND a pulse button fixes it instantly | frames are not advancing: the scheduled delay is measured against a stopped timeline, while a pulse needs no frames | G16 |
| Uploads succeed but nothing ever appears | deferred work waiting on `onFrameStart` while the timeline is stopped | G16 |
| "Parameter says True but nothing happened" | you slept on the main thread, or TD has not cooked yet | never sleep; schedule instead |
| Same error after a fix | Text DAT cached the script | run via `exec(open(..., encoding='utf-8').read())` |
| `UnicodeDecodeError … charmap … 0x81` before the first print, or accents painted as `Ã³` | TD's `open()` decoded the UTF-8 script as cp1252 | `encoding='utf-8'` on the run line; a literal probe at the top of the script (G25) |
| `AttributeError` on a parameter when a button is pressed | parameter read but never declared | cross-check declares vs reads |
| Component works, then not after reload | a stale `.tox` was loaded alongside the built one | the script is the source; never drag the `.tox` in to work with it |

## Write the checker, not just the fix

When a bug crosses a boundary no analyzer sees whole, the deterministic check
belongs in the same change as the fix. Two that pay for themselves immediately in
any `.tox` project:

- **Embedded Python compiles.** A build script carries other programs as string
  constants. No linter reads them, so a syntax error there survives every local
  check and first appears inside TouchDesigner mid-rebuild. Walk the AST, find the
  string constants, `compile()` each one.
- **Declared parameters match read parameters.** The build declares them as string
  literals (`appendToggle('Decode')`) while embedded code reads them as attributes
  (`par.Decode`). A typo only surfaces as an `AttributeError` when a button is
  pressed. Regex both sides and diff, remembering that names are also reached as
  string literals through `setattr` and pulse-dispatch maps.

Have each checker state its own blind spots in its docstring, so nobody credits it
with coverage it lacks.
