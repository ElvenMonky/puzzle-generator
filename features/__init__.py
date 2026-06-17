import importlib
import pkgutil
from pathlib import Path

from .base import ARCFeature

for _, module_name, _ in pkgutil.iter_modules([str(Path(__file__).resolve().parent)]):
    importlib.import_module(f"{__name__}.{module_name}")

REGISTRY = ARCFeature.REGISTRY