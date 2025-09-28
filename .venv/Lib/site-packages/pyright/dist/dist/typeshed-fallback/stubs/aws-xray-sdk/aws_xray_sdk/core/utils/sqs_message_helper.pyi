from collections.abc import Mapping
from typing import Final

from _typeshed import Incomplete

SQS_XRAY_HEADER: Final = "AWSTraceHeader"

class SqsMessageHelper:
    @staticmethod
    def isSampled(sqs_message: Mapping[str, Incomplete]) -> bool: ...
