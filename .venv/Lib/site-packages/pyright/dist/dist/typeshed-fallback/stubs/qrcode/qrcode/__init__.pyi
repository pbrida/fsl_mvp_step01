from _typeshed import ConvertibleToInt
from qrcode import image as image
from qrcode.constants import (
    ERROR_CORRECT_H as ERROR_CORRECT_H,
)
from qrcode.constants import (
    ERROR_CORRECT_L as ERROR_CORRECT_L,
)
from qrcode.constants import (
    ERROR_CORRECT_M as ERROR_CORRECT_M,
)
from qrcode.constants import (
    ERROR_CORRECT_Q as ERROR_CORRECT_Q,
)
from qrcode.main import GenericImage
from qrcode.main import QRCode as QRCode
from qrcode.main import make as make

from ._types import ErrorCorrect, MaskPattern

def run_example(
    data: str = "http://www.lincolnloop.com",
    version: ConvertibleToInt | None = None,
    error_correction: ErrorCorrect = 0,
    box_size: ConvertibleToInt = 10,
    border: ConvertibleToInt = 4,
    image_factory: type[GenericImage] | None = None,
    mask_pattern: MaskPattern | None = None,
) -> None: ...
