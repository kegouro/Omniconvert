"""Núcleo de OmniConvert: conversor base, registro y pipeline."""

from omni_convert.core.converter import (
    ConversionError,
    Converter,
    MissingDependencyError,
    ProgressCallback,
)
from omni_convert.core.pipeline import (
    NoConversionPathError,
    Pipeline,
    build_pipeline,
    find_path,
)
from omni_convert.core.registry import ConverterRegistry, register, registry

__all__ = [
    "ConversionError",
    "Converter",
    "ConverterRegistry",
    "MissingDependencyError",
    "NoConversionPathError",
    "Pipeline",
    "ProgressCallback",
    "build_pipeline",
    "find_path",
    "register",
    "registry",
]
