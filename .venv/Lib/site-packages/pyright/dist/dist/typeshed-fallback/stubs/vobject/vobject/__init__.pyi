from . import icalendar as icalendar
from . import vcard as vcard
from .base import VERSION as VERSION
from .base import Component
from .base import readComponents as readComponents
from .base import readOne as readOne

def iCalendar() -> Component: ...
def vCard() -> Component: ...
