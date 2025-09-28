from typing import Final

from .filters import *
from .filterset import FilterSet as FilterSet
from .filterset import UnknownFieldBehavior as UnknownFieldBehavior

__version__: Final[str]

def parse_version(version: str) -> tuple[str | int]: ...

VERSION: tuple[str | int, ...]
