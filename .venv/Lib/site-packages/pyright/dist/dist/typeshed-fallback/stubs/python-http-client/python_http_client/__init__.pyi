from typing import Final

from .client import Client as Client
from .exceptions import (
    BadRequestsError as BadRequestsError,
)
from .exceptions import (
    ForbiddenError as ForbiddenError,
)
from .exceptions import (
    GatewayTimeoutError as GatewayTimeoutError,
)
from .exceptions import (
    HTTPError as HTTPError,
)
from .exceptions import (
    InternalServerError as InternalServerError,
)
from .exceptions import (
    MethodNotAllowedError as MethodNotAllowedError,
)
from .exceptions import (
    NotFoundError as NotFoundError,
)
from .exceptions import (
    PayloadTooLargeError as PayloadTooLargeError,
)
from .exceptions import (
    ServiceUnavailableError as ServiceUnavailableError,
)
from .exceptions import (
    TooManyRequestsError as TooManyRequestsError,
)
from .exceptions import (
    UnauthorizedError as UnauthorizedError,
)
from .exceptions import (
    UnsupportedMediaTypeError as UnsupportedMediaTypeError,
)

dir_path: Final[str]
__version__: Final[str]
