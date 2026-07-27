# Local background tests (Windows)

`run-pytest-background.cmd` runs pytest and writes its output to
`.local-artifacts/test-runs/latest.log`; its exit status is written to
`.local-artifacts/test-runs/latest.exitcode`.  That directory is ignored by Git.

When a caller must not open a console window or hold pytest's output pipes, launch
the script from an existing non-interactive console with `start /b`:

```cmd
cmd /d /c start "" /b scripts\run-pytest-background.cmd tests\distillation\test_engine.py -q
```

The script uses `DISTILL_ANYONE_PYTHON` when set, otherwise the repository's
`.venv\Scripts\python.exe`, then `python` on `PATH`. For example, from a CMD
session with a project interpreter selected:

```cmd
set "DISTILL_ANYONE_PYTHON=<path-to-project-python>"
cmd /d /c start "" /b scripts\run-pytest-background.cmd -q
```

Inspect `latest.exitcode` before treating the run as successful.  A missing pytest
installation or a failing test remains a non-zero exit code and is recorded in the
log.
