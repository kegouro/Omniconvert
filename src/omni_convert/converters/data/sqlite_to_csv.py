"""Conversor de SQLite a directorio de CSVs y schema.sql."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from omni_convert.core.converter import ConversionError, Converter, ProgressCallback
from omni_convert.core.registry import register


@register
class SqliteToCsv(Converter):
    source_format = "sqlite"
    target_format = "csv"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        if not input_path.is_file():
            raise ConversionError(f"El archivo de entrada no existe: {input_path}")

        tables = []
        conn = None
        try:
            conn = sqlite3.connect(input_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
        except Exception as exc:
            raise ConversionError(f"Error al abrir la base de datos SQLite: {exc}") from exc
        finally:
            if conn and not tables:
                conn.close()

        # Filtrar tablas del sistema
        user_tables = [t for t in tables if not t[0].startswith("sqlite_")]
        if not user_tables:
            try:
                output_path.mkdir(parents=True, exist_ok=True)
                (output_path / "schema.sql").write_text("\n", encoding="utf-8")
            except Exception as exc:
                raise ConversionError(f"Error al crear el esquema vacío: {exc}") from exc
            progress(1.0)
            return

        try:
            output_path.mkdir(parents=True, exist_ok=True)
            # Escribir schema.sql
            schema_statements = [f"{sql};" for _, sql in user_tables if sql]
            (output_path / "schema.sql").write_text("\n".join(schema_statements) + "\n", encoding="utf-8")
        except Exception as exc:
            conn.close()
            raise ConversionError(f"Error al escribir el archivo de esquema: {exc}") from exc

        # Escribir CSVs de tablas
        total_tables = len(user_tables)
        try:
            for index, (table_name, _) in enumerate(user_tables):
                csv_path = output_path / f"{table_name}.csv"
                try:
                    cursor.execute(f'SELECT * FROM "{table_name}"')
                    columns = [desc[0] for desc in cursor.description]
                    with open(csv_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(columns)
                        while True:
                            rows = cursor.fetchmany(1000)
                            if not rows:
                                break
                            writer.writerows(rows)
                except Exception as exc:
                    raise ConversionError(f"Error al exportar la tabla {table_name}: {exc}") from exc
                progress((index + 1) / total_tables)
        finally:
            conn.close()


@register
class DbToCsv(SqliteToCsv):
    source_format = "db"
