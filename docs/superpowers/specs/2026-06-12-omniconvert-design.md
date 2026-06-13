# OmniConvert — Diseño

**Fecha:** 2026-06-12
**Estado:** aprobado por spec del usuario (el prompt original delega las decisiones de diseño)

## Objetivo

CLI en Python para transformación universal de datos entre formatos heterogéneos
(datos tabulares, datos científicos ROOT, audio), extensible mediante un registro
dinámico de conversores y con encadenamiento automático de conversiones.

## Requisitos (de la spec)

- Módulo core con registry dinámico que registra conversores automáticamente.
- Conversores mínimos: CSV→JSON, ROOT→CSV (uproot), MP3→WAV (pydub).
- CLI con Typer, chaining de conversiones, barra de progreso.
- Tests unitarios y Makefile.

## Decisiones clave (cambios sobre la estructura propuesta)

1. **src-layout instalable**: paquete `src/omni_convert/` con entry point
   `omniconvert` en `pyproject.toml`, en vez de módulos sueltos bajo `src/`.
   Evita imports accidentales y permite `pip install -e .`.
2. **Chaining automático por BFS**: el registry expone el grafo de formatos
   (nodos = formatos, aristas = conversores). `pipeline.find_path()` encuentra la
   ruta más corta entre dos formatos; `--via` fuerza formatos intermedios.
   Así `omniconvert convert datos.root datos.json` funciona sin conversor directo.
3. **Cuarto conversor JSON→CSV**: necesario para que existan cadenas reales
   (ROOT→CSV→JSON) y para round-trips en tests.
4. **Imports perezosos de dependencias pesadas**: `uproot` y `pydub` se importan
   dentro de `convert()`. La CLI y el registro funcionan sin extras; si falta una
   dependencia se lanza `MissingDependencyError` con la instrucción de instalación
   (`pip install 'omniconvert[root]'` / `[audio]`).
5. **Progreso como callback**: cada conversor recibe `progress: Callable[[float], None]`
   (fracción 0–1). La CLI lo conecta a una barra `rich`; la pipeline reescala el
   progreso de cada paso al tramo `[i/n, (i+1)/n]`. Sin módulo `utils/progress.py`.
6. **Eliminado `utils/validators.py`**: cada conversor valida su propia entrada
   (principio de cohesión); Typer valida existencia/lectura del archivo de entrada.
7. **Fuera de alcance** (YAGNI): wav→mp4, png→svg, pdf→text, parquet, sqlite,
   `plugins/` como directorio — la extensión se hace registrando conversores con el
   decorador `@register` desde cualquier paquete (documentado en README).

## Arquitectura

```
src/omni_convert/
├── __init__.py            # versión
├── __main__.py            # python -m omni_convert
├── cli.py                 # Typer: convert, formats, path
├── core/
│   ├── converter.py       # Converter (ABC), ConversionError, MissingDependencyError
│   ├── registry.py        # ConverterRegistry + descubrimiento con pkgutil
│   └── pipeline.py        # find_path (BFS), build_pipeline, Pipeline.run
└── converters/
    ├── data/csv_to_json.py, json_to_csv.py, root_to_csv.py
    └── audio/mp3_to_wav.py
```

- **`Converter`** (ABC): atributos de clase `source_format`/`target_format` y método
  `convert(input_path, output_path, progress)`. Una clase = una arista del grafo.
- **`ConverterRegistry`**: dict `{(src, dst): clase}`. `register` es un decorador;
  `discover()` recorre `omni_convert.converters` con `pkgutil.walk_packages` e
  importa cada módulo (los conversores se auto-registran al importarse). Los módulos
  de conversores solo importan stdlib a nivel de módulo, por lo que el
  descubrimiento nunca falla por extras ausentes.
- **`Pipeline`**: lista de instancias de `Converter`; ejecuta cada paso con archivos
  intermedios en un `TemporaryDirectory`.
- **CLI**: `convert IN OUT [--from] [--to] [--via]` (formatos inferidos de la
  extensión), `formats` (tabla de conversores), `path SRC DST` (muestra la cadena).

## Manejo de errores

- `ConversionError` → mensaje rojo y exit code 1.
- `MissingDependencyError(paquete, extra)` → indica el comando pip exacto.
- Sin ruta entre formatos → `NoConversionPathError` listando formatos conocidos.
- ffmpeg ausente al decodificar MP3 → error con sugerencia `brew install ffmpeg`.

## Testing

- **Unitarios puros**: registry (registro, duplicados, descubrimiento), pipeline
  (BFS directo/encadenado/sin ruta/`--via`, ejecución con conversores falsos,
  progreso monótono), CSV↔JSON con `tmp_path`.
- **ROOT**: fixture generado en el propio test con `uproot.recreate`
  (`pytest.importorskip("uproot")`).
- **Audio**: unitario con módulo `pydub` falso inyectado en `sys.modules`
  (no requiere pydub ni ffmpeg); test de dependencia ausente con
  `sys.modules["pydub"] = None`; integración real solo si hay pydub + ffmpeg.
- **CLI**: `typer.testing.CliRunner` end-to-end (csv→json, formats, path, cadena
  root→json si hay uproot).

## Interfaz gráfica (añadida 2026-06-12)

- **Stack**: pywebview (ventana WebKit nativa de macOS) + un `index.html`
  autocontenido. Extra de pip `[gui]`; import perezoso como el resto de extras.
- **Separación testeable**: `gui/api.py` (clase `GuiApi`, puente JS↔Python) no
  importa pywebview a nivel de módulo — los tests la ejercitan con una ventana
  falsa que captura `evaluate_js`. Solo `gui/app.py` y los diálogos nativos
  tocan pywebview.
- **Flujo en 3 pasos**: origen (diálogo nativo) → destino (chips con los
  formatos *alcanzables* por BFS desde el formato de origen, mostrando la
  cadena) → convertir (progreso vía `evaluate_js`). La salida propuesta vive
  junto al original y nunca pisa archivos existentes por defecto.
- **Estética**: minimalismo editorial "hoja impresa" — papel cálido, marco
  perimetral fino, Didot para el wordmark, Avenir Next para UI, SF Mono para
  chips y rutas, acento terracota único. Tipografías del sistema: funciona
  sin red.
- **Ejecutable**: `OmniConvert.command` (doble clic en Finder); crea el venv
  e instala extras en la primera ejecución y luego lanza `python -m
  omni_convert gui`.

## Tooling

- `pyproject.toml` (hatchling), extras `[root]`, `[audio]`, `[all]`, `[dev]`.
- `audioop-lts` como dependencia condicional para Python ≥ 3.13 (pydub depende del
  módulo `audioop` eliminado de la stdlib en 3.13).
- Makefile: `install`, `install-all`, `test`, `test-fast` (xdist), `lint`,
  `format`, `clean`.
- CI en GitHub Actions: matriz Python 3.11–3.13, con ffmpeg, ruff + pytest.
