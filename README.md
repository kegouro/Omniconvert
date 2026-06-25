<div align="center">
  <br>
  <img src="screenshot.png" alt="OmniConvert GUI" width="700">
  <br><br>

  # 🌐 OmniConvert
  <h3>Universal Data Transformer</h3>

  [![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://python.org)
  [![CI](https://github.com/kegouro/Omniconvert/actions/workflows/ci.yml/badge.svg)](https://github.com/kegouro/Omniconvert/actions)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
  [![CLI](https://img.shields.io/badge/Interface-CLI%20%2B%20GUI-green?logo=terminal&logoColor=white)](#)
  [![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey?logo=apple&logoColor=white)](#)

</div>

---

### 📑 Table of Contents · Tabla de Contenido

- [English](#english)
  - [What is OmniConvert?](#what-is-omniconvert)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [Architecture & Design](#architecture--design)
  - [Bundled Converters](#bundled-converters)
  - [How to Improve / Contribute](#how-to-improve--contribute)
- [Español](#español)
  - [¿Qué es OmniConvert?](#qué-es-omniconvert)
  - [Instalación](#instalación)
  - [Inicio Rápido](#inicio-rápido)
  - [Arquitectura y Diseño](#arquitectura-y-diseño)
  - [Conversores Incluidos](#conversores-incluidos)
  - [Cómo Mejorar / Contribuir](#cómo-mejorar--contribuir)
- [License · Licencia](#license--licencia)

---

## English

### What is OmniConvert?

> **One command. Any format.** OmniConvert takes a source file and a target format and figures out the best conversion path — even if no direct converter exists. It models file formats as **nodes** and converters as **edges** in a directed graph, then runs **Breadth-First Search** to find the shortest chain.

```console
$ omniconvert convert events.root events.json

  events.root → events.json  (root → csv → json)

  ⠿ Converting ━━━━━━━━━━━━━━━━━━━━━━━━ 100%  0:00:01
  ✓ Done: events.json
```

No direct `root → json` converter exists, yet OmniConvert found the shortest path automatically. This chaining works across **any** set of registered converters — graph-based, infinitely extensible.

<details>
<summary>🖥️ <b>Desktop GUI</b> — Double-click to launch</summary>
<br>
<p>Double-click <b><code>OmniConvert.command</code></b> on macOS (first run sets up the environment). The GUI walks you through three steps:</p>
<ol>
  <li>Pick source file via native file dialog</li>
  <li>Choose target format — the UI shows reachable formats and their conversion chains</li>
  <li>Convert with a live progress bar</li>
</ol>

```bash
make gui          # or: omniconvert gui
```
</details>

### Installation

```bash
# Core + dev tools (CSV ↔ JSON work out of the box)
make install

# Everything: ROOT, audio, and GUI
make install-all
```

Or pick your extras with pip:

```bash
pip install -e "."                # core only
pip install -e ".[extended,ocr]"  # + extended & ocr converters
pip install -e ".[gui]"           # + desktop GUI
pip install -e ".[all]"           # everything
```

> **⚠️ MP3 → WAV** requires `ffmpeg` on your system: `brew install ffmpeg` (macOS), `apt install ffmpeg` (Linux).

### Quick Start

| Command | What it does |
|---------|-------------|
| `omniconvert convert data.csv data.json` | Simple conversion (formats auto-detected) |
| `omniconvert convert events.root events.json` | Automatic multi-step chaining |
| `omniconvert convert export.dat out.json --from csv --to json` | Force formats when extension doesn't match |
| `omniconvert convert file.root file.json --via csv` | Force a specific intermediate format |
| `omniconvert convert --batch "data/*.csv" --to json` | **⚡️ Ultra-fast Concurrent Batch Processing** |
| `omniconvert convert book.pdf book.md --to md-sci` | **🔬 Scientific OCR (Deep Learning based equations)** |
| `omniconvert formats` | List all registered converters |
| `omniconvert path root json` | Dry-run: shows the shortest conversion path |
| `python -m omni_convert ...` | Use as a Python module |

### Architecture & Design

```
src/omni_convert/
├── cli.py                         # Typer CLI — 4 commands: convert, formats, path, gui
├── core/
│   ├── converter.py               # ABC Converter + ConversionError, MissingDependencyError
│   ├── registry.py                # Dynamic registry with pkgutil auto-discovery
│   └── pipeline.py                # BFS shortest-path + Pipeline chained execution
├── converters/
│   ├── data/                      # csv↔json, root→csv
│   └── audio/                     # mp3→wav
└── gui/
    ├── api.py                     # Python ↔ JS bridge (testable without a window!)
    ├── app.py                     # pywebview native desktop window
    └── static/index.html          # Self-contained HTML/CSS/JS single-page app
```

#### 🔑 Key Design Decisions

| Decision | Why |
|----------|-----|
| **Graph-based chaining** | Formats = nodes, converters = edges. BFS guarantees shortest path. |
| **Dynamic registry** | `@register` decorator + `pkgutil.walk_packages` auto-discovers converters. Plug-and-play from external packages. |
| **Lazy dependency imports** | `uproot`, `pydub`, `pywebview` imported inside `convert()`, not at module level. Registry works without them; missing deps produce clear `pip install` hints. |
| **Progress callbacks** | Each converter reports `0.0 → 1.0`. CLI renders via [Rich](https://github.com/Textualize/rich) progress bars; GUI pushes to JavaScript. |
| **Testable GUI** | `GuiApi` never imports `pywebview` globally. Tests inject a fake window to verify API logic without a real GUI. |

#### 📊 Conversion Flow

```mermaid
graph LR
    A[📁 data.root] -->|RootToCsv| B[📄 temp.csv]
    B -->|CsvToJson| C[📄 temp.json]
    C --> D[✅ output.json]

    style A fill:#f9f,stroke:#333
    style D fill:#9f9,stroke:#333
```

### ✨ Key Features

- **🧠 Auto-Routing Core**: Dijkstra-based graph search that figures out multi-step conversions on its own.
- **⚡️ Blazing Fast Batching**: Converts hundreds of files in parallel via ThreadPool executors, fully utilizing your CPU cores while limiting RAM intelligently for heavy ML models.
- **🎨 Premium Terminal UI**: Built with `rich`, featuring beautiful progress bars, dynamic spinners, and async heartbeats so you always know exactly what's processing.
- **🧩 Pluggable Architecture**: Zero-friction plugins. Just drop a file in `converters/` with the `@register` decorator and OmniConvert does the rest.
- **🔬 Deep Learning OCR**: Uses `marker-pdf` and `pix2tex` for high-fidelity conversion of scientific papers directly to LaTeX-embedded Markdown.

### Bundled Converters

| # | Source → Target | Class | Dependencies |
|---|----------------|-------|-------------|
| 1 | csv → json | `CsvToJson` | stdlib |
| 2 | json → csv | `JsonToCsv` | stdlib |
| 3 | root → csv | `RootToCsv` | `uproot`, `numpy` |
| 4 | mp3 → wav | `Mp3ToWav` | `pydub` + system `ffmpeg` |

### How to Improve / Contribute

**Add a converter in 30 seconds:**

```python
from omni_convert.core import Converter, register

@register
class YamlToJson(Converter):
    source_format = "yaml"
    target_format = "json"

    def convert(self, input_path, output_path, progress):
        import yaml, json                     # heavy imports go here
        with open(input_path) as f:
            data = yaml.safe_load(f)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        progress(1.0)
```

Place it in `src/omni_convert/converters/` and it auto-discovers. From an external package, call `registry.discover("my_package.converters")`.

**💡 Ideas for expansion:**

| Area | Converters | Notes |
|------|-----------|-------|
| 🖼️ Images | png↔jpg, webp↔avif | `pillow` or `opencv` |
| 🎥 Video | mp4↔gif, mov↔webm | `ffmpeg-python` |
| 📄 Documents | md↔html, pdf↔docx | `markdown`, `pdfkit` |
| ⚡ Performance | Rust-backed via PyO3 | For compute-heavy transforms |
| 🌐 Web API | Server mode | FastAPI + streaming |

**Development:**

```bash
make test         # pytest (missing extras → skipped gracefully)
make test-fast    # pytest in parallel with xdist
make lint         # ruff check + format --check
make format       # auto-format
```

Full design doc: [`docs/superpowers/specs/2026-06-12-omniconvert-design.md`](docs/superpowers/specs/2026-06-12-omniconvert-design.md)

---

## Español

### ¿Qué es OmniConvert?

> **Un comando. Cualquier formato.** OmniConvert toma un archivo de origen y un formato de destino y encuentra la mejor ruta de conversión — incluso si no existe un conversor directo. Modela los formatos como **nodos** y los conversores como **aristas** en un grafo dirigido, luego ejecuta **Búsqueda en Anchura (BFS)** para hallar la cadena más corta.

```console
$ omniconvert convert eventos.root eventos.json

  eventos.root → eventos.json  (root → csv → json)

  ⠿ Convirtiendo ━━━━━━━━━━━━━━━━━━━━━━━━ 100%  0:00:01
  ✓ Conversión completada: eventos.json
```

No existe un conversor directo `root → json`, pero OmniConvert encontró la ruta más corta automáticamente. Este encadenamiento funciona sobre **cualquier** conjunto de conversores registrados — basado en grafos, infinitamente extensible.

<details>
<summary>🖥️ <b>Interfaz gráfica</b> — Doble clic para abrir</summary>
<br>
<p>Haz doble clic en <b><code>OmniConvert.command</code></b> en macOS (el primer inicio configura el entorno). La interfaz te guía en tres pasos:</p>
<ol>
  <li>Elige archivo de origen con el diálogo nativo del sistema</li>
  <li>Elige formato de destino — la UI muestra formatos alcanzables y sus cadenas</li>
  <li>Convierte con barra de progreso en vivo</li>
</ol>

```bash
make gui          # o: omniconvert gui
```
</details>

### Instalación

```bash
# Core + herramientas de desarrollo (CSV ↔ JSON funcionan ya)
make install

# Todo: ROOT, audio y GUI
make install-all
```

O elige tus extras con pip:

```bash
pip install -e "."                # solo core
pip install -e ".[extended,ocr]"  # + conversores extendidos y ocr
pip install -e ".[gui]"           # + interfaz gráfica
pip install -e ".[all]"           # todo
```

> **⚠️ MP3 → WAV** requiere `ffmpeg` en el sistema: `brew install ffmpeg` (macOS), `apt install ffmpeg` (Linux).

### Inicio Rápido

| Comando | Acción |
|---------|-------------|
| `omniconvert convert data.csv data.json` | Conversión simple (detecta formatos automáticamente) |
| `omniconvert convert events.root events.json` | Encadenamiento automático de múltiples pasos |
| `omniconvert convert export.dat out.json --from csv --to json` | Fuerza formatos si la extensión no concuerda |
| `omniconvert convert file.root file.json --via csv` | Obliga a pasar por un formato intermedio específico |
| `omniconvert convert --batch "data/*.csv" --to json` | **⚡️ Procesamiento concurrente ultra rápido por lotes** |
| `omniconvert convert book.pdf book.md --to md-sci` | **🔬 OCR Científico (Extrae ecuaciones mediante Deep Learning)** |
| `omniconvert formats` | Muestra la lista de todos los conversores registrados |
| `omniconvert path root json` | Muestra la ruta de conversión óptima sin ejecutarla |

---

### Arquitectura y Diseño

OmniConvert no usa conversores monolíticos como "docx to epub". Define módulos pequeños y reusables.

### ✨ Características Principales

- **🧠 Enrutamiento Automático**: Algoritmo de búsqueda de grafos (Dijkstra) que encuentra el mejor camino de conversión.
- **⚡️ Batching Ultra Rápido**: Convierte cientos de archivos en paralelo a través de ThreadPools, aprovechando tu CPU y limitando inteligentemente la RAM en modelos de ML pesados.
- **🎨 UI de Terminal (TUI) Premium**: Interfaz moderna desarrollada con `rich` que presenta barras de progreso asíncronas, *spinners* dinámicos y "heartbeats" para saber exactamente qué ocurre.
- **🧩 Arquitectura de Plugins**: Agregar un conversor es tan fácil como crear un archivo con `@register`.
- **🔬 OCR con IA Avanzada**: Integra `marker-pdf` y `pix2tex` para conversiones científicas pesadas, rescatando ecuaciones de papers y convirtiéndolas en LaTeX perfecto.

#### 🔑 Decisiones Clave de Diseño

| Decisión | Por Qué |
|----------|---------|
| **Encadenamiento por grafos** | Formatos = nodos, conversores = aristas. BFS garantiza camino más corto. |
| **Registro dinámico** | Decorador `@register` + `pkgutil.walk_packages` auto-descubre conversores. Plug-and-play desde paquetes externos. |
| **Imports perezosos** | `uproot`, `pydub`, `pywebview` se importan dentro de `convert()`, no a nivel de módulo. El registro funciona sin ellos; las dependencias faltantes muestran instrucciones `pip install` claras. |
| **Progreso por callback** | Cada conversor reporta `0.0 → 1.0`. CLI renderiza con barras [Rich](https://github.com/Textualize/rich); GUI lo empuja a JavaScript. |
| **GUI testeable** | `GuiApi` nunca importa `pywebview` globalmente. Los tests inyectan una ventana falsa para verificar la lógica sin GUI real. |

#### 📊 Flujo de Conversión

```mermaid
graph LR
    A[📁 data.root] -->|RootToCsv| B[📄 temp.csv]
    B -->|CsvToJson| C[📄 temp.json]
    C --> D[✅ output.json]

    style A fill:#f9f,stroke:#333
    style D fill:#9f9,stroke:#333
```

### Conversores Incluidos

| # | Origen → Destino | Clase | Dependencias |
|---|-----------------|-------|-------------|
| 1 | csv → json | `CsvToJson` | stdlib |
| 2 | json → csv | `JsonToCsv` | stdlib |
| 3 | root → csv | `RootToCsv` | `uproot`, `numpy` |
| 4 | mp3 → wav | `Mp3ToWav` | `pydub` + `ffmpeg` del sistema |

### Cómo Mejorar / Contribuir

**Añade un conversor en 30 segundos:**

```python
from omni_convert.core import Converter, register

@register
class YamlToJson(Converter):
    source_format = "yaml"
    target_format = "json"

    def convert(self, input_path, output_path, progress):
        import yaml, json                     # imports pesados van aquí
        with open(input_path) as f:
            data = yaml.safe_load(f)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        progress(1.0)
```

Colócalo en `src/omni_convert/converters/` y se auto-descubre. Desde un paquete externo, llama a `registry.discover("mi_paquete.converters")`.

**💡 Ideas de expansión:**

| Área | Conversores | Notas |
|------|------------|-------|
| 🖼️ Imágenes | png↔jpg, webp↔avif | `pillow` o `opencv` |
| 🎥 Video | mp4↔gif, mov↔webm | `ffmpeg-python` |
| 📄 Documentos | md↔html, pdf↔docx | `markdown`, `pdfkit` |
| ⚡ Rendimiento | Backend Rust vía PyO3 | Para transformaciones intensivas |
| 🌐 API Web | Modo servidor | FastAPI + streaming |

**Desarrollo:**

```bash
make test         # pytest (extras faltantes → omitidos)
make test-fast    # pytest en paralelo con xdist
make lint         # ruff check + format --check
make format       # auto-formato
```

Documento de diseño completo: [`docs/superpowers/specs/2026-06-12-omniconvert-design.md`](docs/superpowers/specs/2026-06-12-omniconvert-design.md)

---

## License · Licencia

<div align="center">

[![MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**MIT** © 2026 [Jose Labarca](https://github.com/kegouro)

</div>

---

<sub>Parte del **[Pharos Project](https://kegouro.github.io)** — infraestructura científica y educativa sin barreras de entrada. · José Labarca Baeza</sub>
