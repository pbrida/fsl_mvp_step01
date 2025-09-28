from typing import ClassVar

from _typeshed import Incomplete
from openpyxl.descriptors.serialisable import Serialisable

class ExternalReference(Serialisable):
    tagname: ClassVar[str]
    id: Incomplete
    def __init__(self, id) -> None: ...
