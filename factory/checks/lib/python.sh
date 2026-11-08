# Python helpers. Source common.sh first.
# python_setup: install into .venv with uv, poetry or pip (from the lockfile when there is one),
#               and put .venv/bin first on PATH. `py` runs a tool from the venv.
python_setup() {
  if [ -f uv.lock ] && command -v uv >/dev/null; then
    echo "== uv sync"; uv sync --frozen --all-extras >/dev/null
  elif [ -f poetry.lock ] && command -v poetry >/dev/null; then
    echo "== poetry install"; POETRY_VIRTUALENVS_IN_PROJECT=true poetry install --no-interaction --all-extras >/dev/null
  else
    [ -d .venv ] || python3 -m venv .venv
    echo "== pip install"
    .venv/bin/pip install -q --upgrade pip
    local f
    for f in requirements.txt requirements-dev.txt requirements/dev.txt dev-requirements.txt; do
      [ -f "$f" ] && .venv/bin/pip install -q -r "$f"
    done
    if [ -f pyproject.toml ] || [ -f setup.py ]; then
      .venv/bin/pip install -q -e ".[dev]" 2>/dev/null || .venv/bin/pip install -q -e . || true
    fi
  fi
  export PATH="$PWD/.venv/bin:$PATH"
}
py() { "$@"; }
