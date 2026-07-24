# Contributing to Marklift

Thank you for helping improve Marklift. Contributions should preserve its
small, offline-first Windows desktop design.

## Development setup

Marklift requires Python 3.11 on Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Start the application with `marklift`.

## Checks before submitting

```powershell
ruff check .
pytest -q
```

The performance suite is opt-in: `pytest -q -m performance`.

## Coding standards

- Keep the engine independent of Qt.
- Keep user-facing text in `src/app/strings.py`.
- Preserve deterministic, sequential conversion behavior.
- Do not add runtime networking, telemetry, accounts, or update checks.
- Add or update tests for behavior changes.
- Do not commit generated builds, virtual environments, or Tesseract binaries.

## Pull requests

Explain the user-visible or maintenance change, include test results, and
document compatibility or licensing impact. Keep pull requests focused. A
maintainer may request additional Windows verification before merging.

Contributions are provided under the project's GNU Affero General Public
License, version 3 or any later version.
