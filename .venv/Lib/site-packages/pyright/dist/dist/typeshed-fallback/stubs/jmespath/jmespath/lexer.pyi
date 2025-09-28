from collections.abc import Iterator
from typing import ClassVar, TypedDict, type_check_only

from jmespath.exceptions import EmptyExpressionError as EmptyExpressionError
from jmespath.exceptions import LexerError as LexerError

@type_check_only
class _LexerTokenizeResult(TypedDict):
    type: str
    value: str
    start: int
    end: int

class Lexer:
    START_IDENTIFIER: ClassVar[set[str]]
    VALID_IDENTIFIER: ClassVar[set[str]]
    VALID_NUMBER: ClassVar[set[str]]
    WHITESPACE: ClassVar[set[str]]
    SIMPLE_TOKENS: ClassVar[dict[str, str]]
    def tokenize(self, expression: str) -> Iterator[_LexerTokenizeResult]: ...
