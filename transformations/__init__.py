import importlib
import pkgutil
from pathlib import Path

from .base import ARCTransformation

package_dir = Path(__file__).resolve().parent

for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
    importlib.import_module(f"{__name__}.{module_name}")

REGISTRY = ARCTransformation.REGISTRY