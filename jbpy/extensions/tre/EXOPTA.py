from jbpy import core
from jbpy.extensions import tre


class FloatFormatWithSentinel(tre.FloatFormat):
    """Similar to float format but has special handling for sentinel value"""

    def to_bytes_impl(self, decoded_value, size):
        if decoded_value == 999.9 and size == 5:
            return b"999.9"
        return super().to_bytes_impl(decoded_value, size)


class EXOPTA(core.Tre):
    """Exploitation Usability Optical Information Extension Format
    See STDI-0002 Volume 1 App E, Table E-10

    Note
    ----
    Very similar to USE00A...
    """

    def __init__(self):
        super().__init__("EXOPTA", "CETAG", "CEL", core.Constant(107))

        self._append(
            core.Field(
                "ANGLE_TO_NORTH",
                "Angle to True North",
                3,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(0, 359),
                converter=core.Integer(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "MEAN_GSD",
                "Mean Ground Sample Distance",
                5,
                charset=core.BCSN,
                encoded_range=tre.EncodedFixedPoint("unsigned", 3, 1),
                converter=tre.FloatFormat("0{size}.1f"),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "(reserved-001)",
                "",
                1,
                converter=core.Bytes(),
                default=b"1",
            )
        )

        self._append(
            core.Field(
                "DYNAMIC_RANGE",
                "Dynamic Range",
                5,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(None, 65535),
                converter=core.Integer(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "(reserved-002)",
                "",
                7,
                converter=core.Bytes(),
                default=b" " * 7,
            )
        )

        self._append(
            core.Field(
                "OBL_ANG",
                "Obliquity Angle",
                5,
                charset=core.BCSN,
                encoded_range=tre.EncodedFixedPoint("unsigned", 2, 2),
                decoded_range=core.MinMax(0.0, 90.0),
                converter=tre.FloatFormat("0{size}.2f"),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "ROLL_ANG",
                "Roll Angle",
                6,
                charset=core.BCSN,
                encoded_range=tre.EncodedFixedPoint("required", 2, 2),
                decoded_range=core.MinMax(-90.0, 90.0),
                converter=tre.FloatFormat("+0{size}.2f"),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "PRIME_ID",
                "Primary Target ID",
                12,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "PRIME_BE",
                "Basic Encyclopedia (BE) or non-BE ID of primary target",
                15,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "(reserved-003)",
                "",
                5,
                converter=core.Bytes(),
                default=b" " * 5,
            )
        )

        self._append(
            core.Field(
                "N_SEC",
                "Number Of Secondary Targets in Image",
                3,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(0, 250),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "(reserved-004)",
                "",
                2,
                converter=core.Bytes(),
                default=b" " * 2,
            )
        )

        self._append(
            core.Field(
                "(reserved-005)",
                "",
                7,
                converter=core.Bytes(),
                default=b"0" * 6 + b"1",
            )
        )

        self._append(
            core.Field(
                "N_SEG",
                "Number of Segments",
                3,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "MAX_LP_SEG",
                "Maximum Number of Lines Per Segment",
                6,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, 199999),
                converter=core.Integer(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "(reserved-006)",
                "",
                12,
                converter=core.Bytes(),
                default=b" " * 12,
            )
        )

        self._append(
            core.Field(
                "SUN_EL",
                "Sun Elevation",
                5,
                charset=core.BCSN,
                encoded_range=core.AnyOf(
                    core.Constant(b"999.9"),
                    tre.EncodedFixedPoint("required", 2, 1),
                ),
                decoded_range=core.AnyOf(
                    core.Constant(999.9),
                    core.MinMax(-90.0, +90.0),
                ),
                converter=FloatFormatWithSentinel("+0{size}.1f"),
                default=999.9,
            )
        )

        self._append(
            core.Field(
                "SUN_AZ",
                "Sun Azimuth",
                5,
                charset=core.BCSN,
                encoded_range=core.AnyOf(
                    core.Constant(b"999.9"),
                    tre.EncodedFixedPoint("unsigned", 3, 1),
                ),
                decoded_range=core.AnyOf(
                    core.Constant(999.9),
                    core.MinMax(0.0, 359.9),
                ),
                converter=FloatFormatWithSentinel("0{size}.1f"),
                default=999.9,
            )
        )
