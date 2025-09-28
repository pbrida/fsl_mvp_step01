from typing import ClassVar

from _typeshed import Incomplete
from openpyxl.descriptors.base import Alias
from openpyxl.descriptors.serialisable import Serialisable

class AuthorList(Serialisable):
    tagname: ClassVar[str]
    author: Incomplete
    authors: Alias
    def __init__(self, author=()) -> None: ...
