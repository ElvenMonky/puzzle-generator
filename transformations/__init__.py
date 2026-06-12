import importlib
import pkgutil
from pathlib import Path
from typing import TypedDict

from .base import ARCTransformation

for _, module_name, _ in pkgutil.iter_modules([str(Path(__file__).resolve().parent)]):
    importlib.import_module(f"{__name__}.{module_name}")

REGISTRY = ARCTransformation.REGISTRY

TransformationRef = TypedDict('TransformationRef', {'type': str, 'in': list[int | tuple[int, int]]})
Skeleton = list[TransformationRef]