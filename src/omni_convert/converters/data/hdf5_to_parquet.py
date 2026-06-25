"""Conversor de HDF5 a Parquet."""

from __future__ import annotations

from pathlib import Path

from omni_convert.core.converter import (
    ConversionError,
    Converter,
    MissingDependencyError,
    ProgressCallback,
)
from omni_convert.core.registry import register


@register
class Hdf5ToParquet(Converter):
    source_format = "hdf5"
    target_format = "parquet"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        if not input_path.is_file():
            raise ConversionError(f"El archivo de entrada no existe: {input_path}")

        try:
            import h5py
        except ImportError as exc:
            raise MissingDependencyError("h5py", "extended") from exc

        try:
            import numpy as np
            import pandas as pd
        except ImportError as exc:
            raise MissingDependencyError("pandas", "extended") from exc

        try:
            import pyarrow  # noqa: F401
        except ImportError as exc:
            raise MissingDependencyError("pyarrow", "extended") from exc

        output_path.mkdir(parents=True, exist_ok=True)
        datasets: list[tuple[str, h5py.Dataset]] = []

        def collect_datasets(name: str, obj: h5py.Group | h5py.Dataset) -> None:
            if isinstance(obj, h5py.Dataset):
                datasets.append((name, obj))

        try:
            with h5py.File(input_path, "r") as f:
                f.visititems(collect_datasets)

                if not datasets:
                    progress(1.0)
                    return

                total = len(datasets)
                for idx, (name, dataset) in enumerate(datasets):
                    data = dataset[...]
                    ndim = data.ndim

                    if ndim == 0:
                        df = pd.DataFrame({"value": [data.item()]})
                    elif ndim == 1:
                        df = pd.DataFrame({"value": data})
                    elif ndim == 2:
                        cols = [f"col_{i}" for i in range(data.shape[1])]
                        df = pd.DataFrame(data, columns=cols)
                    else:
                        rows = data.shape[0]
                        cols_count = int(np.prod(data.shape[1:]))
                        reshaped = data.reshape(rows, cols_count)
                        cols = [f"col_{i}" for i in range(cols_count)]
                        df = pd.DataFrame(reshaped, columns=cols)

                    name_parts = name.strip("/").split("/")
                    parquet_file = output_path.joinpath(*name_parts).with_suffix(".parquet")
                    parquet_file.parent.mkdir(parents=True, exist_ok=True)
                    df.to_parquet(parquet_file, index=False)
                    progress((idx + 1) / total)

        except Exception as exc:
            raise ConversionError(f"Error al convertir HDF5: {exc}") from exc


@register
class H5ToParquet(Hdf5ToParquet):
    source_format = "h5"
