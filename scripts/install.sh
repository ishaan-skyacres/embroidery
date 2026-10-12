#!/usr/bin/env bash
# Install the digitizer and its open-source dependencies for the current OS.
#   ./scripts/install.sh            # then: . .venv/bin/activate && digitize --help
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
OS="$(uname -s)"
case "$OS" in
  Linux)
    if command -v apt-get >/dev/null 2>&1; then
      echo "Debian/Ubuntu detected: installing python3-venv, inkscape (for AI/EPS/PDF and text), DejaVu fonts"
      sudo apt-get install -y python3 python3-venv inkscape fonts-dejavu-core
    elif command -v dnf >/dev/null 2>&1; then
      echo "Fedora detected"
      sudo dnf install -y python3 inkscape dejavu-sans-fonts
    elif command -v pacman >/dev/null 2>&1; then
      sudo pacman -S --needed python inkscape ttf-dejavu
    else
      echo "Unknown Linux distribution: install python3 (3.11+) and inkscape with your package manager"
    fi
    PY=python3 ;;
  Darwin)
    echo "macOS detected"
    if command -v brew >/dev/null 2>&1; then
      brew install python inkscape || true
    else
      echo "Install Homebrew (https://brew.sh) or Python 3.11+ from python.org and Inkscape from inkscape.org"
    fi
    PY=python3 ;;
  MINGW*|MSYS*|CYGWIN*)
    echo "Windows detected: install Python 3.11+ (python.org) and Inkscape (inkscape.org), then run:"
    echo "  py -m venv .venv; .venv\\Scripts\\activate; pip install -e ."
    exit 0 ;;
  *)
    echo "Unknown OS $OS"; PY=python3 ;;
esac
$PY -m venv .venv
. .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e ".[test]"
echo
echo "Done. Activate with:  . .venv/bin/activate"
echo "Try:                  digitize input/rack.svg --size-mm 120 --out out/"
echo "Optional Ink/Stitch engine (Path A): ./scripts/install_inkstitch.sh"
