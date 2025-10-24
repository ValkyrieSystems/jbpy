from jbpy import core


class BLOCKA(core.Tre):
    """Image Block Information Extension Format
    See STDI-0002 Volume 1 App E, Table E-9
    """

    def __init__(self):
        super().__init__("BLOCKA", "CETAG", "CEL", core.Constant(123))

        self._append(
            core.Field(
                "BLOCK_INSTANCE",
                "Block number of this image block",
                2,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "N_GRAY",
                "The number of gray fill pixels",
                5,
                charset=core.BCSN_PI,
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "L_LINES",
                "Row Count",
                5,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "LAYOVER_ANGLE",
                "Layover Angle",
                3,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(None, 359),
                converter=core.Integer(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "SHADOW_ANGLE",
                "Shadow Angle",
                3,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(None, 359),
                converter=core.Integer(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "(reserved-001)",
                "",
                16,
                converter=core.Bytes(),
                default=core.BCSA_SPACE.encode() * 16,
            )
        )

        for name, desc in (
            ("FRLC_LOC", "First Row Last Column Location"),
            ("LRLC_LOC", "Last Row Last Column Location"),
            ("LRFC_LOC", "Last Row First Column Location"),
            ("FRFC_LOC", "First Row First Column Location"),
        ):
            self._append(
                core.Field(
                    name,
                    desc,
                    21,
                    charset=core.BCSA,
                    converter=core.StringAscii(),
                    default=None,
                    nullable=True,
                )
            )

        self._append(
            core.Field(
                "(reserved-002)",
                "",
                5,
                converter=core.Bytes(),
                default=b"010.0",
            )
        )
