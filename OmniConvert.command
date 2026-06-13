#!/bin/bash
# OmniConvert — doble clic para abrir la aplicación.
# La primera vez crea el entorno e instala las dependencias (requiere internet).
set -e
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "Primera ejecución: creando entorno de Python…"
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip --quiet
fi

if ! .venv/bin/python -c "import webview" 2>/dev/null; then
  echo "Instalando OmniConvert y sus dependencias…"
  .venv/bin/pip install -e ".[all]" --quiet
fi

exec .venv/bin/python -m omni_convert gui
