"""CLI de OmniConvert basada en Typer."""

from __future__ import annotations

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


@app.command()
def convert(
    input_file: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="Archivo de entrada"),
    ],
    output_file: Annotated[Path, typer.Argument(dir_okay=False, help="Archivo de salida")],
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
) -> None:
    """Convierte un archivo, encadenando conversores si hace falta."""
    registry.discover()
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


if __name__ == "__main__":
    app()
