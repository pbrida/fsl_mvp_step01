from collections.abc import Mapping

from _typeshed import Incomplete
from braintree.exchange_rate_quote import ExchangeRateQuote

class ExchangeRateQuotePayload:
    quotes: list[ExchangeRateQuote]
    def __init__(self, data: Mapping[str, Incomplete]) -> None: ...
    def get_quotes(self) -> list[ExchangeRateQuote]: ...
