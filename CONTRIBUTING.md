# Contributing

Thanks for your interest in improving td-tox-builder. The most valuable contributions
are new gotchas found while building real components, and corrections to existing ones.

## Adding a gotcha

Gotchas live in `td-tox-builder/reference.md`, numbered sequentially (the next one is
G35). Each entry follows the same shape:

1. **Title** stating the fact, not the symptom.
2. **Symptom**: what the user sees, quoting exact error text when there is one.
3. **Cause**: why it happens, with a pointer to TouchDesigner documentation or a
   docstring when available.
4. **Fix**: the pattern to use instead, with a short code sample.

Then:

- Add a row to the troubleshooting table in `td-tox-builder/SKILL.md` if the gotcha has
  a recognisable symptom.
- Add a row to the gotcha table in `README.md`.
- If the mistake can be detected statically, consider a `check_*.py` script or an
  extra case in an existing one.

## Checks

The `check_*.py` scripts must stay pure standard library, read-only, and free of
TouchDesigner imports. Each one states its blind spots in its docstring. Run them
before opening a pull request:

```bash
cd td-tox-builder
python check_td_preflight.py
python check_td_namespace.py templates/build_tox_template.py
python check_td_menu_ids.py templates/build_tox_template.py
```

The same checks run in CI on every push and pull request.

## Style

- Keep `templates/setup_template.ps1` ASCII-only (G5). CI verifies this.
- Keep the skill self-contained: no references to files outside this repository.
- Write in plain, direct English. Be specific about what a check or test can and
  cannot prove.

## Pull requests

Keep each pull request focused on one change, and describe how you verified it,
including the TouchDesigner version when the change depends on native behaviour.
