# Contributing

Please describe a reproducible problem before expanding the scope. Use synthetic fixtures and
never include credentials or private source data in issues or pull requests.

```console
python -m venv .venv
python -m pip install -r requirements-dev.txt
python -m pip install .
python -m ruff check .
python -m ruff format --check .
python -m bandit -r src -ll
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
python -m build
python scripts/verify_install.py
```

Use the virtual environment's Python (activate it, or use its explicit path). Regression tests
must establish the user-visible failure and run on supported Python versions. Test assertions
must not be weakened to hide failures. Keep runtime dependencies justified. Public commits
are maintained by the repository owner; CI never writes commits or updates source files.
