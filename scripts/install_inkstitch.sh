#!/usr/bin/env bash
# Install Ink/Stitch from source for headless use (Path A), isolated in its own Python 3.11 venv.
#   ./scripts/install_inkstitch.sh [install_dir]   (default: ~/inkstitch/inkstitch)
# Requires: git, python3.11 (or uv), and network access. No Inkscape GUI needed.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
DIR="${1:-$HOME/inkstitch/inkstitch}"
COMMIT="${INKSTITCH_COMMIT:-a6a3d480f006292c709a145f56a4e1cabbd5cf8a}"
VENV="$HERE/.venv-inkstitch"

if [ ! -d "$DIR/.git" ]; then
  mkdir -p "$(dirname "$DIR")"
  git clone --depth 1 https://github.com/inkstitch/inkstitch "$DIR"
fi
( cd "$DIR" && git fetch --depth 1 origin "$COMMIT" 2>/dev/null && git checkout -q "$COMMIT" ) || echo "Using the checked-out Ink/Stitch commit"

if command -v uv >/dev/null 2>&1; then
  uv venv "$VENV" --python 3.11
  PIP="uv pip install -p $VENV/bin/python"
else
  python3.11 -m venv "$VENV"
  PIP="$VENV/bin/python -m pip install"
fi
# inkex pulls in pygobject (GTK) which is only needed for GUI; install it without deps.
$PIP pystitch networkx "shapely>=2.0.0" lxml platformdirs "numpy==2.2.6" "jinja2>2.9" colormath2 "flask>=2.2.0" \
     fonttools "trimesh>=3.15.2" "xxhash>=4.0.1" diskcache cssselect tinycss2 pyparsing packaging pyserial pillow
$PIP --no-deps "inkex==1.4.1"
SP="$($VENV/bin/python -c 'import site; print(site.getsitepackages()[0])')"
"$VENV/bin/python" "$HERE/scripts/make_wx_stub.py" "$SP" "$DIR"
( cd "$DIR" && "$VENV/bin/python" -c "from lib import extensions; print('Ink/Stitch imports OK')" )
echo "export INKSTITCH_DIR=$DIR"
echo "export INKSTITCH_PYTHON=$VENV/bin/python"
