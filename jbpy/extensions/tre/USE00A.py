from jbpy import core
from jbpy.extensions import tre


class FloatFormatWithSentinel(tre.FloatFormat):
    """Similar to float format but has special handling for sentinel value"""

    def to_bytes_impl(self, decoded_value, size):
        if decoded_value == 999.9 and size == 5:
            return b"999.9"
        return super().to_bytes_impl(decoded_value, size)


class USE00A(core.Tre):
    """Exploitation Usability TRE, Version A
    See STDI-0002 Volume 1 App D, Table D-2
    """

    def __init__(self):
        super().__init__("USE00A", "CETAG", "CEL", core.Constant(107))

        self._append(
            core.Field(
                "ANGLE_TO_NORTH",
                "Angle to North",
                3,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(0, 359),
                converter=core.Integer(),
                default=0,
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
                default="000.0",
            )
        )

        self._append_reserved("Reserved0", "Reserved", 1, nullable=True)

        self._append(
            core.Field(
                "DYNAMIC_RANGE",
                "Dynamic Range",
                5,
                charset=core.BCSN_PI,
                converter=core.Integer(),
                default=0,
            )
        )

        self._append_reserved("Reserved1", "Reserved", 3, nullable=True)
        self._append_reserved("Reserved2", "Reserved", 1, nullable=True)
        self._append_reserved("Reserved3", "Reserved", 3, nullable=True)

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

        for n, sz in enumerate([12, 15, 4, 1, 3, 1, 1]):
            self._append_reserved(f"Reserved{4 + n}", "Reserved", sz, nullable=True)

        self._append(
            core.Field(
                "N_REF",
                "Number of Reference Lines",
                2,
                charset=core.BCSN_PI,
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "REV_NUM",
                "Revolution Number",
                5,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
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
                "Maximum Lines Per Segment",
                6,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=None,
                nullable=True,
            )
        )

        # unclear why these reserved fields specifically don't have "<>" in the type column
        self._append_reserved("Reserved11", "Reserved", 6, nullable=False)
        self._append_reserved("Reserved12", "Reserved", 6, nullable=False)

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
                    core.MinMax(0.0, 359.0),
                ),
                converter=FloatFormatWithSentinel("0{size}.1f"),
                default=999.9,
            )
        )

    def _append_reserved(self, name, desc, size, nullable):
        """Append reserved field"""
        self._append(
            core.Field(
                name,
                desc,
                size,
                converter=core.Bytes(),
                default=None if nullable else core.BCSA_SPACE.encode() * size,
                nullable=nullable,
            )
        )
