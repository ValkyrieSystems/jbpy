from jbpy import core
from jbpy.extensions import tre


class ICHIPB(core.Tre):
    """ICHIPB TRE
    See STDI-0002 Volume 1 App B, Tables B-1 and B-2
    """

    def __init__(self):
        super().__init__("ICHIPB", "CETAG", "CEL", core.Constant(224))

        self._append(
            core.Field(
                "XFRM_FLG",
                "Non-linear Transformation Flag",
                2,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(None, 1),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "SCALE_FACTOR",
                "Scale Factor Relative to R0",
                10,
                charset=core.BCSN,
                encoded_range=tre.EncodedFixedPoint("unsigned", 4, 5),
                converter=tre.FloatFormat("0{size}.5f"),
                default=0.0,
            )
        )

        self._append(
            core.Field(
                "ANAMRPH_CORR",
                "Anamorphic Correction Indicator",
                2,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(None, 1),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "SCANBLK_NUM",
                "Scan Block Number",
                2,
                charset=core.BCSN_PI,
                converter=core.Integer(),
                default=0,
            )
        )

        for coord in ((1, 1), (1, 2), (2, 1), (2, 2)):
            for comp in ("row", "column"):
                self._append(
                    core.Field(
                        f"OP_{comp[:3].upper()}_{''.join(map(str, coord))}",
                        f"Output product {comp} number component of grid point index {coord} for intelligent data",
                        12,
                        charset=core.BCSN,
                        encoded_range=tre.EncodedFixedPoint("unsigned", 8, 3),
                        converter=tre.FloatFormat("0{size}.3f"),
                        default=0.0,
                    )
                )

        for coord in ((1, 1), (1, 2), (2, 1), (2, 2)):
            for comp in ("row", "column"):
                self._append(
                    core.Field(
                        f"FI_{comp[:3].upper()}_{''.join(map(str, coord))}",
                        f"Grid point {coord}, {comp} number in full image coordinate system",
                        12,
                        charset=core.BCSN,
                        encoded_range=tre.EncodedFixedPoint("unsigned", 8, 3),
                        converter=tre.FloatFormat("0{size}.3f"),
                        default=0.0,
                    )
                )

        for comp in ("row", "column"):
            self._append(
                core.Field(
                    f"FI_{comp[:3].upper()}",
                    f"Full Image Number Of {comp.capitalize()}s",
                    8,
                    charset=core.BCSN_PI,
                    converter=core.Integer(),
                    default=0,
                )
            )
