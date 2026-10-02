# Designing a component someone else will operate

> Companion to `SKILL.md`. Load this before choosing parameters, statuses or
> buttons — the decisions here are hard to retrofit once a component is in use.
>
> Self-contained by design. It carries its own doctrine and depends on no
> project's notes.

## The rule everything else follows from

**The component is the interface. The Textport is the developer's console.**

The workflow of *building* a `.tox` is not the workflow of *using* one. Building
it, you run the build script from the Textport, watch its prints, read tracebacks
there. Using it, someone drops the `.tox` into a project, presses its buttons, and
looks at its parameters and its outputs — often the same person, weeks later,
during a rehearsal, with a projector running.

They are not watching a debug console. **Telling them to open one to find out what
their own component is doing is a design failure, not a support instruction.**

Read the parameter panel as the product's UI and design it as such. If diagnosing
the component requires the Textport, the component is not finished.

## Consequences for the component

### State lives on parameters, in plain language

A read-only Str parameter holding a status is the component speaking to its
operator. Print in addition, never instead.

```python
def _report(comp, message, quiet=False):
    try:
        comp.par.Status = message
    except Exception:
        pass
    if not quiet:
        print('[mycomp] %s' % message)
```

Route every outcome through one helper like this. The moment error reporting has
two paths — some to a parameter, some only to `print` — the panel starts lying by
omission.

### A status that never changes is indistinguishable from one that is stuck

If an operation takes seconds, show progress in the panel:

```
waiting for the address... 8s left
```

Not decoration. A component that sat on `starting...` indefinitely — while the
process it launched had *already* published a working address — was
indistinguishable from one still working, and sent its operator hunting in the
wrong place.

### Name the failure, not the fault

Failures that call for opposite responses must read differently:

- `FAILED: the program never started (no log file)` → check the executable path
- `FAILED: it ran but published no address` → read its console output

One generic "failed" for both is a coin flip dressed as information. State what
happened and, where you can, what to do about it.

### Console windows belong behind a toggle

A terminal appearing over a live projection is unacceptable. Show it while setting
up — the operator can read the launched program's own errors — and hide it while
performing:

```python
if comp.par.Showconsole.eval():
    command, flags = 'cmd /k "%s"' % bat, CREATE_NEW_CONSOLE
else:
    command, flags = 'cmd /c "%s"' % bat, CREATE_NO_WINDOW
```

Send the same information to a log file either way, so hiding the window never
costs visibility.

### A manual "fix it" button is a patch, not a feature

If the automatic path needs a button pressed to work, **the automatic path is
broken**. Keep the button as an escape hatch if it is genuinely useful, but label
it honestly and do not let its existence close the bug. A component that works
only when someone knows which button to press has not been debugged, it has been
worked around.

### Parameter naming is a UX decision, not a technical one

TouchDesigner constrains the internal name (initial capital, then lowercase and
digits, no trailing digit). The `label=` argument is unconstrained — use it. And
write `help=` text as if for someone who has never seen the component, because
that is who reads it:

```python
page.appendToggle('Showconsole')   # name: legal, ugly, invisible
# label='Show console', help='Useful while setting up; turn OFF for a show so no
# terminal appears over the projection.'
```

Group parameters into pages by *task*, not by implementation: what an operator
touches during setup, during a show, and never.

### Outputs are part of the interface

Name and document what comes out of the component. Two `outTOP`s with no
explanation is a puzzle; one holding "the received image" and another "the QR
code" is a product. If an output can legitimately be empty, make empty look
deliberate rather than broken.

## Consequences for the agent building it

These are behavioural, and they are the ones most easily forgotten mid-debugging.

**Do not ask the user to read the Textport as a normal step.** Needing it means
the component is not reporting enough. Fix that instead — the request is a symptom
of a missing status parameter.

**Do not narrate progress the user cannot see.** "It should work now" is worthless
without an observable in the panel. Point at the parameter that will change and
what it will say.

**Prefer a diagnosis script to a list of clicks.** Asking someone to press things
and describe what they see is slow, lossy, and puts the burden on them. A script
they paste once returns precise state (see `debugging.md`).

**Verify in the interface the user actually uses.** A passing internal check is
not the same as the component visibly working. Confirm through the panel and the
outputs, because that is where the claim will be judged.

**When the user says something is a patch, believe them.** They are describing
their real workflow, which is authoritative in a way no amount of code reading
is. Escalate it to a design fix rather than defending the workaround.
