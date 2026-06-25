"""CLI de OmniConvert basada en Typer."""

from __future__ import annotations

import glob
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from omni_convert.core.converter import ConversionError
from omni_convert.core.pipeline import NoConversionPathError, build_pipeline, find_path
from omni_convert.core.registry import registry

app = typer.Typer(
    name="omniconvert",
    help="OmniConvert: transformador universal de datos.",
    no_args_is_help=True,
)
console = Console()

PROGRESS_RESOLUTION = 1000


def _infer_format(path: Path, override: str | None, label: str) -> str:
    if override:
        return override.lower()
    suffix = path.suffix.lstrip(".").lower()
    if not suffix:
        raise typer.BadParameter(
            f"No se puede inferir el formato de {label} desde '{path}'; indícalo con --from/--to"
        )
    return suffix


def _convert_single_file(
    input_file: Path,
    output_dir: Path | None,
    from_format: str | None,
    to_format: str,
    via: list[str] | None,
    progress_callback=None,
) -> Path:
    out_ext = ".md" if to_format == "md-sci" else f".{to_format}"
    
    if output_dir is not None:
        output_file = output_dir / f"{input_file.stem}{out_ext}"
    else:
        output_file = input_file.parent / f"{input_file.stem}{out_ext}"

    output_file.parent.mkdir(parents=True, exist_ok=True)

    source = _infer_format(input_file, from_format, f"entrada ({input_file.name})")

    pipeline = build_pipeline(registry, source, to_format, via=[v.lower() for v in via or []])
    pipeline.run(input_file, output_file, progress=progress_callback)
    return output_file


@app.command()
def convert(
    input_file: Annotated[
        Path | None,
        typer.Argument(dir_okay=False, readable=True, help="Archivo de entrada"),
    ] = None,
    output_file: Annotated[
        Path | None,
        typer.Argument(dir_okay=False, help="Archivo de salida"),
    ] = None,
    from_format: Annotated[
        str | None,
        typer.Option("--from", "-f", help="Formato de origen (por defecto, la extensión)"),
    ] = None,
    to_format: Annotated[
        str | None,
        typer.Option("--to", "-t", help="Formato de destino (por defecto, la extensión)"),
    ] = None,
    via: Annotated[
        list[str] | None,
        typer.Option("--via", help="Formato(s) intermedio(s) forzados, en orden"),
    ] = None,
    batch: Annotated[
        str | None,
        typer.Option("--batch", help="Patrón glob para procesamiento por lotes"),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Directorio de salida para el procesamiento por lotes"),
    ] = None,
    fail_fast: Annotated[
        bool,
        typer.Option("--fail-fast", help="Detener la ejecución por lotes en el primer error"),
    ] = False,
) -> None:
    """Convierte un archivo o un lote de archivos, encadenando conversores si hace falta."""
    registry.discover()

    if batch:
        if to_format is None:
            console.print("[red]Error:[/] La opción --to es obligatoria para conversiones por lotes.")
            raise typer.BadParameter("La opción --to es obligatoria para conversiones por lotes.")

        matched_paths = glob.glob(batch, recursive=True)
        files = [Path(p) for p in matched_paths if Path(p).is_file()]

        if not files:
            console.print(f"[yellow]Advertencia:[/] No se encontraron archivos que coincidan con el patrón: '{batch}'")
            raise typer.Exit(code=1)

        files = sorted(files)
        max_workers = min(32, (os.cpu_count() or 4) * 2)
        
        if to_format == "md-sci":
            safe_limit = 2
            if max_workers > safe_limit:
                console.print(f"[yellow]! Limitando workers a {safe_limit} para OCR pesado (md-sci) para evitar saturación de RAM.[/]")
                max_workers = safe_limit

        console.print(f"Procesando [bold]{len(files)}[/] archivos en lote con [bold]{max_workers}[/] hilos...")

        failed_files = []
        futures = {}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress_bar:
            overall_task = progress_bar.add_task("[bold blue]Progreso Total Batch", total=len(files))

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for file in files:
                    file_task = progress_bar.add_task(f"En cola: {file.name}", total=PROGRESS_RESOLUTION, visible=False)

                    def make_callback(t_id, name):
                        def cb(fraction):
                            progress_bar.update(t_id, description=f"Convirtiendo {name}", visible=True, completed=int(fraction * PROGRESS_RESOLUTION))
                        return cb

                    future = executor.submit(
                        _convert_single_file,
                        file,
                        output_dir,
                        from_format,
                        to_format,
                        via,
                        make_callback(file_task, file.name),
                    )
                    futures[future] = (file, file_task)

                for future in as_completed(futures):
                    file, file_task = futures[future]
                    try:
                        out_path = future.result()
                        progress_bar.update(file_task, completed=PROGRESS_RESOLUTION, visible=False)
                        progress_bar.advance(overall_task)
                        progress_bar.console.print(f"[green]✓[/] Conversión completada: [bold]{file.name}[/] → [bold]{out_path.name}[/]")
                    except (ConversionError, NotImplementedError) as exc:
                        progress_bar.update(file_task, visible=False)
                        progress_bar.advance(overall_task)
                        progress_bar.console.print(f"[red]Error de conversión en {file.name}:[/] {exc}")
                        failed_files.append((file, exc))
                    except Exception as exc:
                        progress_bar.update(file_task, visible=False)
                        progress_bar.advance(overall_task)
                        progress_bar.console.print(f"[red]Error inesperado procesando {file.name}:[/] {exc}")
                        failed_files.append((file, exc))
                        if fail_fast:
                            progress_bar.console.print("[red]Fail-fast activado. Cancelando tareas pendientes...[/]")
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            break

        if failed_files:
            console.print("\n[bold red]Resumen de errores de procesamiento por lotes:[/]")
            for file, exc in failed_files:
                console.print(f"  - [bold]{file.name}[/]: {exc}")
            raise typer.Exit(code=1)

        console.print("\n[green]✓[/] ¡Procesamiento por lotes finalizado correctamente!")
        return

    # Non-batch single-file execution
    if input_file is None:
        console.print("[red]Error: Falta el archivo de entrada.[/]")
        raise typer.BadParameter("Falta el archivo de entrada cuando no se usa --batch.")
    if output_file is None:
        console.print("[red]Error: Falta el archivo de salida.[/]")
        raise typer.BadParameter("Falta el archivo de salida cuando no se usa --batch.")
    if not input_file.exists():
        console.print(f"[red]Error: El archivo de entrada '{input_file}' no existe.[/]")
        raise typer.BadParameter(f"El archivo de entrada '{input_file}' no existe.")

    source = _infer_format(input_file, from_format, "entrada")
    target = _infer_format(output_file, to_format, "salida")

    try:
        pipeline = build_pipeline(registry, source, target, via=[v.lower() for v in via or []])
    except ConversionError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc

    chain = " → ".join(pipeline.formats)
    console.print(f"[bold]{input_file.name}[/] → [bold]{output_file.name}[/]  ({chain})")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress_bar:
        task = progress_bar.add_task("Convirtiendo", total=PROGRESS_RESOLUTION)
        try:
            pipeline.run(
                input_file,
                output_file,
                lambda fraction: progress_bar.update(
                    task, completed=int(fraction * PROGRESS_RESOLUTION)
                ),
            )
        except ConversionError as exc:
            console.print(f"[red]Error:[/] {exc}")
            raise typer.Exit(code=1) from exc
        except NotImplementedError as exc:
            console.print(f"[red]Error de implementación:[/] {exc}")
            raise typer.Exit(code=1) from exc

    console.print(f"[green]✓[/] Conversión completada: {output_file}")


@app.command()
def formats() -> None:
    """Lista los conversores registrados."""
    registry.discover()
    table = Table("Origen", "Destino", "Conversor")
    for (source, target), cls in registry.items():
        table.add_row(source, target, cls.__name__)
    console.print(table)


@app.command()
def path(
    source: Annotated[str, typer.Argument(help="Formato de origen")],
    target: Annotated[str, typer.Argument(help="Formato de destino")],
) -> None:
    """Muestra la cadena de conversores que se usaría entre dos formatos."""
    registry.discover()
    try:
        steps = find_path(registry, source.lower(), target.lower())
    except NoConversionPathError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    if not steps:
        console.print("Origen y destino son el mismo formato; no hay nada que hacer.")
        return
    chain = " → ".join([steps[0].source_format] + [s.target_format for s in steps])
    names = ", ".join(s.__name__ for s in steps)
    console.print(f"{chain}  (conversores: {names})")


@app.command()
def gui() -> None:
    """Abre la interfaz gráfica de OmniConvert."""
    from omni_convert.gui.app import launch

    try:
        launch()
    except ConversionError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
