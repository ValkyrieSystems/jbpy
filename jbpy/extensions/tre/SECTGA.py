from jbpy import core


class SECTGA(core.Tre):
    """SECTGA TRE
    See STDI-0002 Volume 1 App E, Table E-23
    """

    def __init__(self):
        super().__init__("SECTGA", "CETAG", "CEL", core.Constant(28))

        self._append(
            core.Field(
                "SEC_ID",
                "Designator of Secondary Target",
                12,
                core.BCSA,
                core.AnyRange(),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "SEC_BE",
                "Basic Encyclopedia ID",
                15,
                core.BCSA,
                core.AnyRange(),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "(reserved-001)",
                "",
                1,
                core.BCSN,
                core.Constant(0),
                core.Integer,
                default=0,
            )
        )
