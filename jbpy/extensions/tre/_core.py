import math
import re
from typing import Literal

from jbpy import core


class FloatFormat(core.PythonConverter):
    """Convert to/from float with a static string format specification

    Parameters
    ----------
    format_spec : str
        Format specification that defines how the bytes will be presented.
        ``{size}`` replacement field(s) will be replaced with the ``size`` arg of `to_bytes`
    """

    def __init__(self, format_spec: str):
        self.format_spec = format_spec

    def to_bytes_impl(self, decoded_value: float, size: int) -> bytes:
        decoded_value = float(decoded_value)
        return f"{decoded_value:{self.format_spec.format(size=size)}}".encode()

    def from_bytes_impl(self, encoded_value: bytes) -> float:
        return float(encoded_value)


class FlexibleFloat(core.PythonConverter):
    """Convert to/from float to a flexible string format specification

    Perhaps useful for cases where the presence of a sign and location of the decimal point aren't specified.
    """

    def to_bytes_impl(self, decoded_value: float, size: int) -> bytes:
        decoded_value = float(decoded_value)
        if decoded_value.is_integer():
            return core.Integer().to_bytes(int(decoded_value), size)

        abs_decoded_value = abs(decoded_value)
        if abs_decoded_value >= 1:
            integer_digits = math.floor(math.log10(abs_decoded_value)) + 1
        else:
            integer_digits = 0

        if decoded_value < 0:
            sign = "-"
        else:
            sign = ""

        precision = max(size - 1 - len(sign) - integer_digits, 0)
        if abs_decoded_value < 1:
            working_str = sign + f"{abs_decoded_value:.{precision}f}"[1:]
        else:
            working_str = sign + f"{abs_decoded_value:.{precision}f}"
        return working_str.encode()

    def from_bytes_impl(self, encoded_value: bytes) -> float:
        return float(encoded_value)


class EncodedFixedPoint(core.RangeCheck):
    """Encoded value is a decimal number with a fixed number of digits following the decimal point

    Parameters
    ----------
    sign : {'required', 'unsigned'}
        When is a sign expected
    integer_digits : int
        Number of digits before the decimal point
    fractional_digits : int
        Number of digits after the decimal point
    """

    def __init__(
        self,
        sign: Literal["required", "unsigned"],
        integer_digits: int,
        fractional_digits: int,
    ):
        self.sign = sign
        self.integer_digits = integer_digits
        self.fractional_digits = fractional_digits

    @property
    def pattern(self):
        sgn = {"required": b"[+-]", "unsigned": b""}[self.sign]
        return (
            sgn
            + bytes(f"[0-9]{{{self.integer_digits}}}", encoding="ascii")
            + rb"\."
            + bytes(f"[0-9]{{{self.fractional_digits}}}", encoding="ascii")
        )

    def isvalid(self, value):
        return bool(re.fullmatch(self.pattern, value))
