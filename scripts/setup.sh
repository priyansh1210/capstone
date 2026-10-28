#!/usr/bin/env bash
# Create the virtual environment and install dependencies (Linux/macOS/Git Bash).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
[ -d .venv ] || "$PY" -m venv .venv
if [ -x .venv/bin/python ]; then VPY=.venv/bin/python; else VPY=.venv/Scripts/python.exe; fi
"$VPY" -m pip install --upgrade pip
"$VPY" -m pip install -r requirements.txt
"$VPY" -m pip install -e . --no-deps || {
  SITE=$("$VPY" -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
  echo "$(pwd)/src" > "$SITE/amm-src.pth"
  echo "editable install unavailable; wrote $SITE/amm-src.pth"
}
"$VPY" -c "import amm, river, sklearn; print('ok: amm', amm.__version__, '| river', river.__version__, '| sklearn', sklearn.__version__)"
