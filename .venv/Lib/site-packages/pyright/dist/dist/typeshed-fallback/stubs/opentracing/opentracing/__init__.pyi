from .propagation import (
    Format as Format,
)
from .propagation import (
    InvalidCarrierException as InvalidCarrierException,
)
from .propagation import (
    SpanContextCorruptedException as SpanContextCorruptedException,
)
from .propagation import (
    UnsupportedFormatException as UnsupportedFormatException,
)
from .scope import Scope as Scope
from .scope_manager import ScopeManager as ScopeManager
from .span import Span as Span
from .span import SpanContext as SpanContext
from .tracer import (
    Reference as Reference,
)
from .tracer import (
    ReferenceType as ReferenceType,
)
from .tracer import (
    Tracer as Tracer,
)
from .tracer import (
    child_of as child_of,
)
from .tracer import (
    follows_from as follows_from,
)
from .tracer import (
    start_child_span as start_child_span,
)

tracer: Tracer
is_tracer_registered: bool

def global_tracer() -> Tracer: ...
def set_global_tracer(value: Tracer) -> None: ...
def is_global_tracer_registered() -> bool: ...
