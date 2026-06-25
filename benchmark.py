#!/usr/bin/env python3
"""Script de benchmarking para OmniConvert Milestone 5."""

import os
import shutil
import time
import sys
from pathlib import Path
from typer.testing import CliRunner

from omni_convert.core.converter import Converter, ProgressCallback
from omni_convert.core.registry import register, registry
from omni_convert.core.pipeline import build_pipeline
from omni_convert.cli import app

# 1. Registrar un conversor de prueba con sleep para simular sobrecarga constante
@register
class DummyBenchmarkConverter(Converter):
    source_format = "benchmark_in"
    target_format = "benchmark_out"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        time.sleep(0.05)  # 50 ms de retraso controlado
        output_path.write_text("benchmark_ok", encoding="utf-8")
        progress(1.0)


def main():
    temp_dir = Path("temp_benchmark")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    print("Generando 100 archivos de prueba...")
    num_files = 100
    files = []
    for i in range(num_files):
        f = temp_dir / f"test_{i}.benchmark_in"
        f.write_text(f"data_{i}", encoding="utf-8")
        files.append(f)

    # --- Ejecución Secuencial ---
    print("Ejecutando modo secuencial...")
    start_seq = time.perf_counter()
    for file in files:
        output_file = file.parent / f"{file.stem}.benchmark_out"
        pipeline = build_pipeline(registry, "benchmark_in", "benchmark_out")
        pipeline.run(file, output_file)
    seq_time = time.perf_counter() - start_seq
    print(f"Tiempo secuencial total: {seq_time:.4f} segundos")

    # Limpiar archivos de salida secuenciales
    for file in files:
        out_file = file.parent / f"{file.stem}.benchmark_out"
        if out_file.exists():
            out_file.unlink()

    # --- Ejecución Concurrente (a través del CLI) ---
    print("Ejecutando modo concurrente (CLI)...")
    runner = CliRunner()
    pattern = str(temp_dir / "*.benchmark_in")

    start_con = time.perf_counter()
    result = runner.invoke(app, [
        "convert",
        "--batch", pattern,
        "--to", "benchmark_out"
    ])
    con_time = time.perf_counter() - start_con
    print(f"Tiempo concurrente total (CLI): {con_time:.4f} segundos")

    # Verificar que el CLI terminó con éxito
    if result.exit_code != 0:
        print(f"Error: La ejecución del CLI falló con código {result.exit_code}")
        print(result.output)
        cleanup(temp_dir)
        sys.exit(1)

    # Verificar que todos los archivos de salida existen
    for file in files:
        out_file = file.parent / f"{file.stem}.benchmark_out"
        if not out_file.exists():
            print(f"Error: No se encontró el archivo de salida {out_file}")
            cleanup(temp_dir)
            sys.exit(1)

    # Calcular speedup
    speedup = seq_time / con_time
    print(f"\nSpeedup obtenido: {speedup:.2f}x (Requerido: >= 2.50x)")

    cleanup(temp_dir)

    if speedup >= 2.5:
        print("¡Prueba de rendimiento SUPERADA!")
        sys.exit(0)
    else:
        print("Error: El speedup es menor que 2.5x.")
        sys.exit(1)


def cleanup(directory):
    if directory.exists():
        shutil.rmtree(directory)


if __name__ == "__main__":
    main()
