import array

from _typeshed import Incomplete
from MySQLdb._exceptions import ProgrammingError as ProgrammingError
from MySQLdb._mysql import string_literal as string_literal
from MySQLdb.constants import FIELD_TYPE as FIELD_TYPE
from MySQLdb.constants import FLAG as FLAG
from MySQLdb.times import (
    Date as Date,
)
from MySQLdb.times import (
    Date_or_None as Date_or_None,
)
from MySQLdb.times import (
    DateTime2literal as DateTime2literal,
)
from MySQLdb.times import (
    DateTime_or_None as DateTime_or_None,
)
from MySQLdb.times import (
    DateTimeDelta2literal as DateTimeDelta2literal,
)
from MySQLdb.times import (
    DateTimeDeltaType as DateTimeDeltaType,
)
from MySQLdb.times import (
    DateTimeType as DateTimeType,
)
from MySQLdb.times import (
    TimeDelta_or_None as TimeDelta_or_None,
)

NoneType: Incomplete
ArrayType = array.array

def Bool2Str(s, d): ...
def Set2Str(s, d): ...
def Thing2Str(s, d): ...
def Float2Str(o, d): ...
def None2NULL(o, d): ...
def Thing2Literal(o, d): ...
def Decimal2Literal(o, d): ...
def array2Str(o, d): ...

conversions: Incomplete
