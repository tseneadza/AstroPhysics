#!/bin/bash
# Astrophysics AI Lab — Hub uses PORT when starting this app.
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

PY=""
for candidate in "$APP_DIR/.venv/bin/python3.14" "$APP_DIR/.venv/bin/python3.13" "$APP_DIR/.venv/bin/python3.12" "$APP_DIR/.venv/bin/python3"; do
  if [ -x "$candidate" ]; then
    PY="$candidate"
    break
  fi
done

if [ -z "$PY" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
  PY="$APP_DIR/.venv/bin/python3"
  for candidate in "$APP_DIR/.venv/bin/python3.14" "$APP_DIR/.venv/bin/python3.13" "$APP_DIR/.venv/bin/python3.12" "$APP_DIR/.venv/bin/python3"; do
    if [ -x "$candidate" ]; then PY="$candidate"; break; fi
  done
fi

DEPS_STAMP="$APP_DIR/.venv/.hub_deps_installed"
if [ ! -f "$DEPS_STAMP" ] || [ "$APP_DIR/requirements.txt" -nt "$DEPS_STAMP" ]; then
  echo "Installing Python dependencies..."
  "$PY" -m pip install --disable-pip-version-check -r "$APP_DIR/requirements.txt"
  touch "$DEPS_STAMP"
fi

FRONTEND_DIR="$APP_DIR/frontend"
DIST_DIR="$FRONTEND_DIR/dist"
BUILD_STAMP="$FRONTEND_DIR/.last_build"
if [ -f "$FRONTEND_DIR/package.json" ]; then
  NEEDED=0
  if [ ! -f "$DIST_DIR/index.html" ]; then NEEDED=1; fi
  if [ -f "$BUILD_STAMP" ] && [ "$FRONTEND_DIR/package.json" -nt "$BUILD_STAMP" ]; then NEEDED=1; fi
  if [ "$NEEDED" -eq 1 ]; then
    echo "Building frontend (Vite)..."
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
      (cd "$FRONTEND_DIR" && npm install)
    fi
    (cd "$FRONTEND_DIR" && npm run build)
    touch "$BUILD_STAMP"
  fi
fi

export PORT="${PORT:-5112}"
echo "Starting Astrophysics AI Lab on PORT=$PORT..."
exec "$PY" -m uvicorn astrophysics.main:app --host 0.0.0.0 --port "$PORT"
