import decimal
import logging
from typing import Literal

from jbpy import core
from jbpy.extensions import tre

logger = logging.getLogger(__name__)


class SciFloat(core.PythonConverter):
    """Convert to/from float using scientific notation of the form: [±]D.MMMME±XX

    Values that extend beyond the range allowed by the format are clamped to the closest representible number.

    Parameters
    ----------
    sign : {'required', 'unsigned'}
        When is a sign expected
    fractional_digits : int
        Number of digits after the decimal point in the mantissa.
        There is always one digit before the decimal point.
    exponent_digits : int
        Number of digits in the exponent
    """

    def __init__(
        self,
        sign: Literal["required", "unsigned"],
        fractional_digits: int,
        exponent_digits: int,
    ):
        self.sign = sign
        self.fractional_digits = fractional_digits
        self.exponent_digits = exponent_digits

    def to_bytes_impl(self, decoded_value: float, size: int) -> bytes:
        expected_size = (
            len("x.") + self.fractional_digits + len("E±") + self.exponent_digits
        )
        if self.sign == "required":
            expected_size += 1
        assert size == expected_size

        emax = (10**self.exponent_digits) - 1
        emin = -emax
        with decimal.localcontext(
            prec=self.fractional_digits + 1,
            Emin=emin,
            Emax=emax,
            clamp=True,
            traps=[decimal.Overflow],  # type: ignore  # mypy seems to be wrong when it flags this
        ):
            try:
                d = decimal.Decimal.from_float(decoded_value).normalize()
            except decimal.Overflow:
                d = decimal.Decimal.from_float(decoded_value).next_toward(0).normalize()
                logger.warning(
                    f"Value: {decoded_value} does not fit in field. Rounding to {d}"
                )
            exp = max(d.adjusted(), emin)
            mant = round(d.scaleb(-exp), self.fractional_digits)

        if self.sign == "required":
            sgn = "+"
        elif self.sign == "unsigned":
            sgn = "-"
            if mant.is_signed():
                raise ValueError("Value is signed but converter is unsigned")
        else:
            raise ValueError(f"Unrecognized sign: {self.sign}")
        return f"{mant:{sgn}0.{self.fractional_digits}f}E{exp:+0{self.exponent_digits + 1}}".encode()

    def from_bytes_impl(self, encoded_value: bytes) -> float:
        return float(encoded_value)


class RPC00B(core.Tre):
    """Rapid Positioning Capability Extension Format
    See STDI-0002 Volume 1 App E, Table E-22
    """

    def __init__(self):
        super().__init__("RPC00B", "CETAG", "CEL", core.Constant(1041))

        self._append(
            core.Field(
                "SUCCESS",
                "",
                1,
                converter=core.Bytes(),
                default=b"1",
            )
        )

        self._append(
            core.Field(
                "ERR_BIAS",
                "Error - Bias",
                7,
                charset=core.BCSN,
                encoded_range=tre.EncodedFixedPoint("unsigned", 4, 2),
                converter=tre.FloatFormat("0{size}.2f"),
                default=0.0,
            )
        )

        self._append(
            core.Field(
                "ERR_RAND",
                "Error - Random",
                7,
                charset=core.BCSN,
                encoded_range=tre.EncodedFixedPoint("unsigned", 4, 2),
                converter=tre.FloatFormat("0{size}.2f"),
                default=0.0,
            )
        )

        self._append(
            core.Field(
                "LINE_OFF",
                "Line Offset",
                6,
                charset=core.BCSN_PI,
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "SAMP_OFF",
                "Sample Offset",
                5,
                charset=core.BCSN_PI,
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "LAT_OFF",
                "Geodetic Latitude Offset",
                8,
                charset=core.BCSN,
                encoded_range=tre.EncodedFixedPoint("required", 2, 4),
                decoded_range=core.MinMax(-90.0, 90.0),
                converter=tre.FloatFormat("+0{size}.4f"),
                default=0.0,
            )
        )

        self._append(
            core.Field(
                "LONG_OFF",
                "Geodetic Longitude Offset",
                9,
                charset=core.BCSN,
                encoded_range=tre.EncodedFixedPoint("required", 3, 4),
                decoded_range=core.MinMax(-180.0, 180.0),
                converter=tre.FloatFormat("+0{size}.4f"),
                default=0.0,
            )
        )

        self._append(
            core.Field(
                "HEIGHT_OFF",
                "Geodetic Height Offset",
                5,
                charset=core.BCSN,
                decoded_range=core.MinMax(-9999, 9999),
                converter=core.Integer("+"),
                default=0,
            )
        )

        self._append(
            core.Field(
                "LINE_SCALE",
                "Line Scale",
                6,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "SAMP_SCALE",
                "Sample Scale",
                5,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "LAT_SCALE",
                "Geodetic Latitude Scale",
                8,
                charset=core.BCSN,
                encoded_range=tre.EncodedFixedPoint("required", 2, 4),
                decoded_range=core.AllOf(
                    core.MinMax(-90.0, 90.0),
                    core.Not(core.Constant(0.0)),
                ),
                converter=tre.FloatFormat("+0{size}.4f"),
                default=0.0,
            )
        )

        self._append(
            core.Field(
                "LONG_SCALE",
                "Geodetic Longitude Scale",
                9,
                charset=core.BCSN,
                encoded_range=tre.EncodedFixedPoint("required", 3, 4),
                decoded_range=core.AllOf(
                    core.MinMax(-180.0, 180.0),
                    core.Not(core.Constant(0.0)),
                ),
                converter=tre.FloatFormat("+0{size}.4f"),
                default=0.0,
            )
        )

        self._append(
            core.Field(
                "HEIGHT_SCALE",
                "Geodetic Height Scale",
                5,
                charset=core.BCSN,
                decoded_range=core.AllOf(
                    core.MinMax(-9999, 9999),
                    core.Not(core.Constant(0)),
                ),
                converter=core.Integer("+"),
                default=0,
            )
        )

        # (name prefix, description)
        coef_fields = [
            ("LINE_NUM", "Line Numerator Coefficients"),
            ("LINE_DEN", "Line Denominator Coefficients"),
            ("SAMP_NUM", "Sample Numerator Coefficients"),
            ("SAMP_DEN", "Sample Denominator Coefficients"),
        ]
        for prefix, desc in coef_fields:
            for coef_index in range(20):
                self._append(
                    core.Field(
                        f"{prefix}_COEFF_{coef_index + 1}",
                        desc,
                        12,
                        charset=core.BCSA,
                        encoded_range=core.Regex(rb"[+-][0-9]\.[0-9]{6}E[+-][0-9]"),
                        converter=SciFloat("required", 6, 1),
                        default=0.0,
                    )
                )
