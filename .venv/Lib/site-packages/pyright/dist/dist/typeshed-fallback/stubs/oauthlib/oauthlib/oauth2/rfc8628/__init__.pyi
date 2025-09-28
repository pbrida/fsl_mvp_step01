from logging import Logger

from .errors import (
    AuthorizationPendingError as AuthorizationPendingError,
)
from .errors import (
    ExpiredTokenError as ExpiredTokenError,
)
from .errors import (
    SlowDownError as SlowDownError,
)

log: Logger
