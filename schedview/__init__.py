from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rubin_sim")
except PackageNotFoundError:
    # package is not installed
    pass

from .dayobs import DayObs
from .sphere import *
from .util import band_column
