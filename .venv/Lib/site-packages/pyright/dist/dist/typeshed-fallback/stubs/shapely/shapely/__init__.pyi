from typing import Final

from . import affinity as affinity
from ._coverage import *
from ._geometry import *
from .constructive import *
from .coordinates import *
from .creation import *
from .errors import setup_signal_checks as setup_signal_checks
from .geometry import (
    GeometryCollection as GeometryCollection,
)
from .geometry import (
    LinearRing as LinearRing,
)
from .geometry import (
    LineString as LineString,
)
from .geometry import (
    MultiLineString as MultiLineString,
)
from .geometry import (
    MultiPoint as MultiPoint,
)
from .geometry import (
    MultiPolygon as MultiPolygon,
)
from .geometry import (
    Point as Point,
)
from .geometry import (
    Polygon as Polygon,
)
from .io import *
from .lib import (
    Geometry as Geometry,
)
from .lib import (
    GEOSException as GEOSException,
)
from .lib import (
    geos_capi_version as geos_capi_version,
)
from .lib import (
    geos_capi_version_string as geos_capi_version_string,
)
from .lib import (
    geos_version as geos_version,
)
from .lib import (
    geos_version_string as geos_version_string,
)
from .linear import *
from .measurement import *
from .predicates import *
from .set_operations import *
from .strtree import *

__version__: Final[str]
