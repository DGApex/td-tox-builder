---
name: td-tox-builder
description: "Build, debug, and design TouchDesigner .tox components. Use when creating a .tox or adding operators to one (it generates the Python build script that assembles the component inside TD), when diagnosing a component that builds cleanly but misbehaves (callbacks that never run, a server answering TouchDesigner's default page, duplicated log lines, a port already in use, a status stuck forever, parameter changes that appear not to apply, deferred work that never happens), or when choosing a component's parameters, statuses and buttons so an operator can run it without opening the Textport. Carries a catalog of 34 TouchDesigner and Windows gotchas with fixes, including silent failures that pass every check."
argument-hint: "[<component-name>]"
user-invocable: true
allowed-tools: Read, Glob, Grep, Write, Edit, AskUserQuestion
---

When this skill is invoked, you help the user build a **TouchDesigner `.tox`
component** by authoring a Python *build script* they run inside TD. A `.tox` can
only be produced by TouchDesigner, so the build script — not a binary — is the
deliverable and source of truth.

## Companion files — load what the task needs, not all of it

All paths are relative to the directory containing this `SKILL.md`.
This file is the router; the documents carry the
depth. **The skill is self-contained: it never depends on a particular project's
notes or memories.**

| Load this | When |
|---|---|
| `reference.md` | Always before writing a build script. TD Python API cheatsheet + the gotcha catalog (G1–G34), each with symptom, cause and fix |
| `component-design.md` | **Before choosing parameters, statuses or buttons.** How a component reports its own state, and how the agent should behave while building one. Hard to retrofit once in use |
| `debugging.md` | When a component builds cleanly but misbehaves, or a symptom survived one round of guessing. TD failures are mostly silent; this is the method for making them loud |
| `check_td_namespace.py` | Run on builders before delivery; prevents missing builtins during startup and helper handoffs (G26). Pure stdlib, read-only |
| `check_td_menu_ids.py` | Run before delivery; catches known alpha-blend identifier mistakes (G27). Menu fixtures must come from observed/documented per-parameter lists |
| `templates/td_preflight.py` | Portable helpers for isolated-builder global dependencies (G30) and runtime ID/label/unit resolution (G29); copy or inline into the project, never depend on the skill at runtime |
| `check_td_preflight.py` | Run before delivery; reproduces missing-import and abbreviated-unit failures using the actual shipped helpers; explicitly synthetic menus, not native evidence |
| `templates/build_tox_template.py` | The generator template you copy and fill in |
| `templates/setup_template.ps1` | Only for components that launch an external process (ASCII-only bootstrap skeleton) |

Read `reference.md` and the template before generating anything. Read
`component-design.md` at spec time — its decisions shape the parameter list. Reach
for `debugging.md` the moment something is wrong, rather than guessing twice.

**On the worked example:** the gotcha catalog was hardened while building the
FluxRT bridge `.tox` in a **different project**. Its files (`build_fluxrt_tox.py`,
`setup_fluxrt.ps1`, `td_fluxrt_bridge.py`) are **not present in this repository** —
they are cited as the origin of each lesson, not as files you can open here. Treat
every FluxRT reference below as a described shape, and never instruct the user to
read one of those paths.

Follow the **collaboration protocol**: Question → Options → Decision → Draft →
Approval. Show every file inline and ask "May I write this to `[filepath]`?" before
any Write/Edit.

---

## 1. Parse arguments

- `<component-name>` (optional) — the COMP / `.tox` name (PascalCase, valid
  identifier). If missing, ask the user for it via `AskUserQuestion`.

## 2. Read the companions

Read `reference.md` and `templates/build_tox_template.py` now so your generated
script uses the proven patterns and you can answer error questions precisely.

## 3. Elicit the component spec

Use `AskUserQuestion` (batch the questions) to pin down what the component needs:

- **Inputs** — how many `inTOP`s, and what each is (e.g. video, reference, mask).
- **Outputs** — how many `outTOP`s.
- **Transport** — does it use Spout (video) and/or OSC (control)? Or is it
  self-contained (no external app)?
- **External process** — does pressing a button launch a separate program
  (e.g. a Python bridge via `conda run`)? If yes, capture the exact command.
- **Dependency bootstrap** — does it need a "Setup" button that installs/downloads
  dependencies (→ an ASCII-only PowerShell script)? If yes, also ask:
  - **Install path** — should Setup prompt for a folder and install everything
    self-contained under it (recommended → an `Installdir` param + prefix env)?
  - **From-zero** — should Setup auto-install missing prerequisites (git/git-lfs via
    winget, Miniconda) so a fresh machine works with no manual steps (G8)?
  - **Reproducibility** — pin versions via a `requirements.lock.txt` (pip freeze,
    filtered) so the target matches this machine exactly?
- **Portability** — embed the bridge/installer/lock as Text DATs so the `.tox`
  works on another machine by itself (G7)?
- **Controls** — the list of live parameters (name + type: Str/Int/Float/Toggle/
  File/Folder/Menu/Pulse). Remind the user names must be valid identifiers (G1).

If the user is unsure, propose a sensible default set, describing the FluxRT shape
as a reference (video in + reference in + result out + prompt/seed/steps + Setup/
Start/Stop) — described, not linked: those files live in another project.

## 4. Generate the build script

Copy `templates/build_tox_template.py` and fill in every `# >>> EDIT` block from
the spec:

- **EDIT 1** — `PROJECT_ROOT` (forward slashes) + `COMP_NAME`.
- **EDIT 2** — the embedded extension class: rename it to `<Name>Ext`, keep it in
  sync with the Text DAT name; implement the OSC/process methods the component
  needs; delete the bridge/Setup bits if there is no external process.
- **EDIT 3** — parexec routing: the `op('<Name>Ext')` reference and the
  button→method map.
- **EDIT 4–6** — input/output TOPs, wiring, and the custom-parameter page.

Write it to `execution/build_<name>_tox.py` (or alongside the user's project).
Show the full draft inline; ask permission before writing.

Enforce these non-negotiables (each maps to a gotcha in `reference.md`, or to
`component-design.md` for the first):
- **Preflight before mutation (G30).** For an AST/exec-composed builder, load
  definitions with explicit imports/dependencies and validate its actual scope
  before creating or clearing TD nodes. The caller's `import os` does not fill
  a different exec namespace. Test both globals and builtins injection.
- **Resolve the parameter's actual menu (G29).** Match IDs and labels without
  case assumptions; pixel aliases apply only to unit parameters. Never guess
  an index or select the first/default item to silence a failure. Include the
  operator path, requested value, menuNames and menuLabels in error reports.
- **Offline tests are bounded evidence.** Synthetic menus are labelled as such.
  A permissive mock cannot establish native enum validity. During an authorized
  operator-run build, compile/cook one representative new text/shader path and
  inspect errors before final save; never force-cook the full show as a test.
- **Verify the component's whole network in every state (G32).** Before saving,
  step the component through each state it offers (menu entries, modes), call its
  own refresh, cook every TOP *of the component* (not the rest of the show) and
  collect `errors()` per state. Wire multi-input operators by index and assert the
  position (`dst.inputs[i] == src`); a GLSL TOP stops at 3 inputs — use GLSL Multi
  beyond that, and never wire from the source's output connector (G31). Probe
  geometry only inside large solid areas and state what the probe proves (G34).
- **Recover partial builds by identity.** Use versioned code markers as well as
  presence of late-created nodes. Keep the service off until assembly succeeds;
  retry the intended component, never delete unrelated versions or clear data.
- **The component is the interface.** Every state worth knowing lands on a
  read-only parameter in plain language, not only in `print()`. Show progress for
  anything slow, name which failure happened when there are several, and put
  console windows behind a toggle so none appears over a live projection. If
  diagnosing the component requires the Textport, it is not finished. Full doctrine
  in `component-design.md`.
- **Purge auto-created callbacks DATs before creating your own (G12)**, and verify
  the reference by CONTENT via a marker - TD claims those names first and silently
  renames yours.
- **Never sleep on the main thread (G13)**; schedule with `run()` instead.
- **Make the rebuild idempotent across the whole project (G14)**, not just the root.
- **Launch external processes through a `.bat` (G15)** so spaced paths survive cmd.
- **Anchor scheduled delays to `op.TDResources`, not the root timeline (G16)** —
  `run(..., delayFrames=N)` waits on `root` by default and stays queued forever
  when that timeline is stopped, silently. Anything deferred (`run()` callbacks
  AND `onFrameStart` work) is dead in that state, so a component that defers must
  be able to report "no frames are advancing" on its own panel.
- Custom-parameter and header **names are valid identifiers**; use `label=` for
  display text, or omit headers (G1).
- `existing.destroy()` before `create` so re-runs are idempotent.
- Bind Spout/OSC names with the `_try([candidate names], ...)` helper (G4).
- The parexec **instantiates the extension from the sibling Text DAT** and caches
  per `comp.id` — never rely on extension promotion (G3).
- External processes launch via `cmd /k` + `CREATE_NEW_CONSOLE`, with a `Condacmd`
  param for PATH issues (G6).

## 5. Generate the bootstrap script (only if needed)

If the component has a Setup button / external deps, emit an **ASCII-only**
PowerShell `setup_<name>.ps1` from `templates/setup_template.ps1`. Fill its
`# >>> EDIT` blocks: hardware gate, pinned deps / lockfile, repo+model downloads.
Keep the bootstrap patterns:
- A `-InstallDir` param; install everything under it incl. a conda **prefix env**.
- Auto-install git/git-lfs via **winget** and **Miniconda** silently if missing (G8).
- **ASCII-only** — no em dashes / box-drawing / smart quotes (G5).
- Generate the lock with `conda run -n <env> pip freeze`, then filter GPU torch +
  editable installs (see reference.md "Reproducibility with a lockfile").

Also wire the `.tox` to **embed** this script + the bridge + the lock as Text DATs
and write them to `<Installdir>/bridge` on Setup, so the `.tox` is portable (G7).
Show every file inline; ask before writing.

## 6. Tell the user how to run it (cache-proof)

Instruct the user to run the build script from the **Textport (Alt+T)**:

```python
exec(open('<ABSOLUTE PATH TO build_<name>_tox.py>', encoding='utf-8').read())
```

Explain **why** this and not "drag the .py in and Run": a dragged-in Text DAT keeps
its own cached copy, so file edits don't take effect and the same error reappears
(G2). The `exec(open(...))` form always reads the file fresh. **`encoding='utf-8'`
is part of the line, every time**: TD's Python opens files as cp1252 by default,
so a script with an accent either crashes before its first print or — worse —
runs with mojibake baked into its Text DATs (G25). Generated scripts carry a
literal probe that aborts on a wrong decode; it does not excuse the argument.

Success looks like:
```
[build] <Name> component built and saved -> <PROJECT_ROOT>/<Name>.tox
```

## 7. Verify & troubleshoot

For a live image that disagrees with a selector, apply **G28 before changing
rendering code or rebuilding**: enumerate component copies, compare the exact
resolved source path with the instance the user operates, then distinguish
cooking from actual pixel changes. A reference-only correction applies live;
save the `.toe` to persist the project connection. See `debugging.md` and G28
in `reference.md`. Do not infer the selected source from a valid node name.

Resolve TD dependencies explicitly before passing them to helper modules:
`factories = dict(textDAT=textDAT, pbrMAT=pbrMAT)`. Never pass `globals()` as
an operator registry: names available through builtins are absent from it.
Run `python <skill-directory>/check_td_namespace.py <builder.py>` and execute
the actual builder-to-helper handoff in regression tests with factories in
globals and in builtins. A test that invents the dependency dictionary does
not cover that boundary. See reference G26. Native build success still needs
native evidence; do not rebuild a user's live component without authorization.

Menu labels and menu IDs are different. Query `par.menuNames` or authoritative
parameter documentation before writing enum candidates. For alpha blending,
native IDs are `srcblend='sa'`, `destblend='omsa'`; descriptive aliases alone
are insufficient. Run `check_td_menu_ids.py` and test the actual setter with
independent, per-parameter menu fixtures. Never populate a fake menu with the
strings the implementation hopes to find. See reference G27.

Ask the user to paste the Textport output. Handle the common cases:

| Symptom | Cause → Fix | Ref |
|---|---|---|
| `First argument must be parameter name…` | Invalid param/header name → use valid id + `label=` | G1 |
| Same error reappears after a fix | Text DAT cached → run via `exec(open(...))` | G2 |
| `KeyError: 'textDAT'` in a helper factory map | Operator lives in builtins, omitted by globals() → explicitly resolve and pass the factory names | G26 |
| Blend menu rejects `srcalpha` | Actual enum is `sa` (destination `omsa`) → use observed menuNames, update independent fixtures and sweep sibling materials | G27 |
| Reflection/video moves but does not follow the selected scene | Another component copy supplies the image → compare full resolved paths and correct the source reference live; no rebuild | G28 |
| `UnicodeDecodeError: 'charmap' codec can't decode byte …` before any `[build]` line | TD opened the UTF-8 file as cp1252 → add `encoding='utf-8'` to `open()` | G25 |
| Accented text renders as `Ã³` / `Ã` | same cause, script ran mis-decoded → same fix; the probe should have aborted, add it | G25 |
| `'td.baseCOMP' object has no attribute 'X'` | Relied on promotion → parexec instantiates the class | G3 |
| `[build] WARN <node> has no par '…'` | Spout/OSC par-name variance → set that one par by hand | G4 |
| PowerShell `MissingEndParenthesisInExpression` / mojibake | `.ps1` not ASCII → strip non-ASCII | G5 |
| Setup/Start console: `'conda' not recognized` | conda not on TD's PATH → set `Condacmd` to `condabin/conda.bat` | G6 |
| `IndexError` wiring input 3+ of a GLSL TOP / an input silently replaced | GLSL TOP has 3 inputs → `glslmultiTOP`; wire by index and assert, never from the output connector | G31 |
| `Not enough sources specified` on a Composite TOP | Fewer than 2 inputs in some state → two transparent bases; check every TOP in every state | G32 |
| `WARN … antialias: none of (…) in ['aa1', … 'aa32']` / no `premultiply` par | Use the real ids (`aa4`); measure the image alpha convention instead of assuming | G33 |
| Geometry probe fails with the right hue but dimmer | Probe landed on a thin stroke → probe inside solid neighbourhoods, several points | G34 |

For anything else, point at the matching section of `reference.md`.

## 8. Log it (offer)

Offer to record the new component in the project's own documentation (a
changelog, session log or overview file, if the project keeps one). Do not write
unless the user agrees.

## Patterns used

Custom **TouchDesigner Component Authoring** pattern. The robust build patterns and
the gotcha catalog were hardened while building the FluxRT bridge `.tox` in another
project; this skill generalizes them to any component. The lessons travel — the
FluxRT files do not.
