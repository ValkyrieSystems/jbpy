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
                core.BCSN_PI,
                core.MinMax(1, None),
                core.Integer,
                default=0,
            )
        )

        self._append(
            core.Field(
                "N_GRAY",
                "The number of gray fill pixels",
                5,
                core.BCSN_PI,
                core.AnyRange(),
                core.Integer,
                default=0,
            )
        )

        self._append(
            core.Field(
                "L_LINES",
                "Row Count",
                5,
                core.BCSN_PI,
                core.MinMax(1, None),
                core.Integer,
                default=0,
            )
        )

        self._append(
            core.Field(
                "LAYOVER_ANGLE",
                "Layover Angle",
                3,
                core.BCSN + core.BCSA_SPACE,
                core.AnyOf(
                    core.Constant(""),
                    core.Regex(
                        r"([0-2][0-9]{2}|3[0-5][0-9])"  # 000-359
                    ),
                ),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "SHADOW_ANGLE",
                "Shadow Angle",
                3,
                core.BCSN + core.BCSA_SPACE,
                core.AnyOf(
                    core.Constant(""),
                    core.Regex(
                        r"([0-2][0-9]{2}|3[0-5][0-9])"  # 000-359
                    ),
                ),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "(reserved-001)",
                "",
                16,
                core.ECS,
                core.AnyRange(),
                core.StringAscii,
                default="",
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
                    core.BCSA,
                    core.AnyRange(),
                    core.StringAscii,
                    default="",
                )
            )

        self._append(
            core.Field(
                "(reserved-002)",
                "",
                5,
                core.ECS,
                core.AnyRange(),
                core.StringAscii,
                default="010.0",
            )
        )
