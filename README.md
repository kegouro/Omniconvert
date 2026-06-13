# OmniConvert

Transformador universal de datos: una CLI extensible que convierte archivos
entre formatos heterogéneos (datos tabulares, datos científicos ROOT, audio)
encadenando conversores automáticamente.

```console
$ omniconvert convert eventos.root eventos.json
eventos.root → eventos.json  (root → csv → json)
⠿ Convirtiendo ━━━━━━━━━━━━━━━━━━━━ 100% 0:00:01
✓ Conversión completada: eventos.json
```

No existe un conversor directo ROOT→JSON: OmniConvert encontró solo la ruta
`root → csv → json` mediante búsqueda en anchura sobre el grafo de conversores.

## Interfaz gráfica

Doble clic en **`OmniConvert.command`** abre la aplicación de escritorio
(la primera vez crea el entorno e instala dependencias, requiere internet).
Si macOS bloquea la apertura, haz clic derecho → *Abrir* la primera vez.

También puedes lanzarla desde la terminal:

```bash
make gui                # o bien: omniconvert gui
```

La interfaz guía la conversión en tres pasos: elegir archivo de origen,
elegir formato de destino entre los alcanzables (mostrando la cadena de
conversión que se usará) y convertir con barra de progreso. La ubicación de
salida se propone junto al original sin pisar archivos existentes.

## Instalación

```bash
make install            # core + deps de desarrollo (CSV↔JSON funcionan ya)
make install-all        # añade extras: ROOT (uproot), audio (pydub) y GUI (pywebview)
```

O con pip directamente:

```bash
pip install -e .                  # solo core
pip install -e ".[root,audio]"    # con todos los conversores
```

El conversor MP3→WAV requiere además **ffmpeg** en el sistema
(`brew install ffmpeg` en macOS, `apt install ffmpeg` en Debian/Ubuntu).

## Uso

```bash
# Conversión simple (formatos inferidos de las extensiones)
omniconvert convert datos.csv datos.json

# Encadenamiento automático
omniconvert convert eventos.root eventos.json

# Forzar formatos cuando la extensión no ayuda
omniconvert convert export.dat salida.json --from csv --to json

# Forzar una ruta intermedia concreta
omniconvert convert eventos.root eventos.json --via csv

# Ver conversores disponibles y rutas posibles
omniconvert formats
omniconvert path root json
```

También funciona como módulo: `python -m omni_convert ...`

## Conversores incluidos

| Origen | Destino | Dependencias |
|--------|---------|--------------|
| csv    | json    | — (stdlib) |
| json   | csv     | — (stdlib) |
| root   | csv     | `[root]`: uproot, numpy |
| mp3    | wav     | `[audio]`: pydub + ffmpeg del sistema |

La interfaz gráfica usa el extra `[gui]` (pywebview).

Los extras son opcionales: si falta uno, la CLI sigue funcionando y el
conversor afectado indica el comando `pip install` exacto al usarse.

## Arquitectura

```
src/omni_convert/
├── cli.py                 # Typer: convert, formats, path, gui
├── core/
│   ├── converter.py       # Converter (ABC) + errores
│   ├── registry.py        # Registro dinámico con auto-descubrimiento
│   └── pipeline.py        # BFS de rutas + ejecución encadenada
├── converters/
│   ├── data/              # csv_to_json, json_to_csv, root_to_csv
│   └── audio/             # mp3_to_wav
└── gui/
    ├── api.py             # Puente Python <-> JS (testeable sin ventana)
    ├── app.py             # Ventana pywebview
    └── static/index.html  # Interfaz (HTML/CSS/JS autocontenido)
```

- **Registro dinámico**: `registry.discover()` recorre `omni_convert.converters`
  e importa cada módulo; los conversores se auto-registran con `@register`.
- **Chaining**: los formatos son nodos y los conversores aristas; la pipeline
  ejecuta la ruta más corta usando archivos intermedios temporales.
- **Progreso**: cada conversor informa una fracción 0–1 por callback; la CLI
  la muestra con una barra [rich](https://github.com/Textualize/rich).

### Añadir un conversor propio

```python
from omni_convert.core import Converter, register

@register
class MarkdownToHtml(Converter):
    source_format = "md"
    target_format = "html"

    def convert(self, input_path, output_path, progress):
        ...  # importa dependencias pesadas aquí dentro
        progress(1.0)
```

Si la clase vive dentro de `omni_convert/converters/`, se descubre sola. Desde
un paquete externo, basta con importar el módulo que la define (o llamar a
`registry.discover("mi_paquete.conversores")`).

## Desarrollo

```bash
make test        # pytest (los tests que requieren extras ausentes se omiten)
make test-fast   # pytest en paralelo
make lint        # ruff check + format --check
make format      # autoformato
```

El diseño completo está en
[`docs/superpowers/specs/2026-06-12-omniconvert-design.md`](docs/superpowers/specs/2026-06-12-omniconvert-design.md).
