# td-tox-builder

A [Claude Code](https://claude.com/claude-code) skill for building, debugging and
designing TouchDesigner `.tox` components from Python.

A `.tox` can only be produced by TouchDesigner itself, so this skill does not emit
binaries. It writes a **build script** that you run inside TouchDesigner, and that
script assembles the component and saves the `.tox`. The script is the source of
truth: versionable, diffable and reproducible.

The skill also carries a catalog of 34 TouchDesigner and Windows gotchas (G1 to G34),
each with symptom, cause and fix. Most of them are silent failures: the component
builds, every check passes, and something still does not work.

## What it does

- **Generates build scripts** for new components from a short spec: inputs, outputs,
  Spout/OSC transport, external processes, dependency bootstrap and custom parameters.
- **Generates bootstrap scripts** (ASCII-only PowerShell) for components that launch an
  external Python/conda process, installing everything under a single chosen folder.
- **Diagnoses components that misbehave**: callbacks that never run, a web server that
  answers TouchDesigner's default page, duplicated log lines, ports already in use,
  statuses stuck forever, deferred work that never happens.
- **Guides component design** so an operator can run it from its parameter panel
  without ever opening the Textport.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- TouchDesigner 2022 or later (to run the generated build scripts)
- Windows, for the bootstrap and external-process patterns
- Python 3.9 or later, only to run the bundled offline checks

## Installation

Clone the repository and copy the `td-tox-builder` folder into your Claude Code skills
directory.

Personal skill (available in every project):

```bash
git clone https://github.com/DGApex/td-tox-builder.git
cp -r td-tox-builder/td-tox-builder ~/.claude/skills/
```

On Windows (PowerShell):

```powershell
git clone https://github.com/DGApex/td-tox-builder.git
Copy-Item -Recurse td-tox-builder\td-tox-builder "$env:USERPROFILE\.claude\skills\"
```

Project skill (shared with everyone working on one repository): copy the folder into
`<your-project>/.claude/skills/` instead.

## Usage

In Claude Code, invoke the skill with an optional component name:

```
/td-tox-builder MyComponent
```

Claude will also load it on its own when you ask for something it covers, such as
"build a .tox that receives video over Spout" or "my component's status is stuck on
starting".

The workflow is:

1. **Spec.** Claude asks about inputs, outputs, transport, external processes and
   controls, and proposes a default set if you are unsure.
2. **Draft.** It generates `build_<name>_tox.py` (and `setup_<name>.ps1` if needed),
   shows every file inline and asks before writing anything.
3. **Build.** You run the script from the TouchDesigner Textport (Alt+T):

   ```python
   exec(open('C:/path/to/build_mycomponent_tox.py', encoding='utf-8').read())
   ```

   Expected output:

   ```
   [build] MyComponent built and saved -> C:/path/to/project/MyComponent.tox
   ```

4. **Troubleshoot.** If something fails, paste the Textport output and Claude maps it
   to the matching gotcha.

Two details in that command matter. Running through `exec(open(...))` instead of
dragging the `.py` into TouchDesigner avoids a Text DAT serving a stale cached copy of
the script (G2). The `encoding='utf-8'` argument is required because TouchDesigner's
Python opens files as cp1252 by default, which can corrupt any accented character
silently (G25).

## Repository layout

```
td-tox-builder/
  SKILL.md                    Entry point and router: workflow and non-negotiables
  reference.md                TouchDesigner Python API cheatsheet and gotcha catalog G1-G34
  component-design.md         How a component should report its own state to an operator
  debugging.md                Method for turning silent TouchDesigner failures into loud ones
  check_td_namespace.py       Static guard for injected-name handoffs (G26)
  check_td_menu_ids.py        Static guard for alpha-blend menu ID mistakes (G27)
  check_td_preflight.py       Regression for the shipped preflight helpers (G29, G30)
  templates/
    build_tox_template.py     Build script template, every customisation marked "# >>> EDIT"
    setup_template.ps1        ASCII-only from-zero bootstrap for external processes
    td_preflight.py           Portable helpers to copy into a project (menus, globals)
```

`SKILL.md` acts as a router: Claude loads only the companion documents a task needs.

## Offline checks

The three `check_*.py` scripts are pure standard library, read-only, and never import
TouchDesigner. Run them against your own generated builders before handing a component
to an operator:

```bash
python td-tox-builder/check_td_preflight.py
python td-tox-builder/check_td_namespace.py path/to/build_mycomponent_tox.py
python td-tox-builder/check_td_menu_ids.py  path/to/build_mycomponent_tox.py
```

Without arguments, `check_td_namespace.py` and `check_td_menu_ids.py` scan
`execution/build_*_tox.py` and `execution/*_builder.py` in the current directory. Each
script documents its own blind spots in its docstring. They are bounded evidence: a pass
does not prove that a component works inside TouchDesigner.

## Gotcha catalog

Full detail in [`td-tox-builder/reference.md`](td-tox-builder/reference.md).

| ID | Gotcha |
|---|---|
| G1 | Parameter and header names must be valid identifiers |
| G2 | A Text DAT caches its own copy of the script |
| G3 | Extension promotion is fragile and fails silently |
| G4 | Spout and OSC operator parameter names vary by build |
| G5 | PowerShell launched from a Setup button must be ASCII-only |
| G6 | `conda` (or any tool) is not on PATH for TouchDesigner's subprocess |
| G7 | Make the `.tox` self-contained and portable |
| G8 | Bootstrap a fresh machine under a chosen install path |
| G9 | The conda Terms-of-Service gate blocks env creation on fresh installs |
| G10 | PowerShell wrapper functions eat short flags (`-e`, `-r`) |
| G11 | Spout fails across two GPUs |
| G12 | TouchDesigner auto-creates the callbacks DAT and yours gets ignored |
| G13 | Never sleep on TouchDesigner's main thread |
| G14 | The `.tox` is a build artifact; loading it duplicates the component |
| G15 | `cmd` deletes the outermost quote pair |
| G16 | A scheduled delay is measured against the root timeline |
| G17 | Resizing a Script CHOP destroys its channel names |
| G18 | Texture 3D TOP records every frame by default |
| G19 | Viewer-only parameters: `fillmode` does not touch the pixels |
| G20 | "paths" parameters silently reject OP objects |
| G21 | The Projection TOP's fisheye is centred on the camera's view axis |
| G22 | Aspect ratio is not resolution |
| G23 | Look At overrides rotation parameters and never sets which edge is up |
| G24 | Standard SOP attributes reject a default, only at cook time |
| G25 | `open()` in TouchDesigner decodes as cp1252 |
| G26 | Injected TouchDesigner names are not guaranteed to be in `globals()` |
| G27 | Menu labels are not enum IDs |
| G28 | Correct node type and live pixels do not prove source identity |
| G29 | Unit menu IDs, labels and abbreviations are different contracts |
| G30 | Reusing source does not transfer its imported globals |
| G31 | A GLSL TOP takes at most 3 inputs |
| G32 | A Composite TOP with one input is an error |
| G33 | Text TOP antialias and Movie File In alpha conventions |
| G34 | Probe geometry inside large solid areas |

## Design principles

- **The component is the interface.** Every state worth knowing lands on a read-only
  parameter in plain language. If diagnosing a component requires the Textport, it is
  not finished.
- **Existence is not identity.** A reference that resolves says nothing about what it
  resolved to. Verify embedded code by content, using version markers.
- **Make silent failures loud.** Any "do it if it exists" path has an else branch that
  names the features that die.
- **Idempotent rebuilds.** Running a build script twice yields the same project, never
  two competing copies.

## Origin

The gotcha catalog was hardened while building a real-time video bridge component
(FluxRT) in a separate project. Those project files are not part of this repository;
the lessons were generalised so they apply to any component.

## Contributing

Contributions are welcome, especially new gotchas found in real projects. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
