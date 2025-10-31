from jbpy import core


class SECTGA(core.Tre):
    """Secondary Targeting Information Extension Format
    See STDI-0002 Volume 1 App E, Table E-23
    """

    def __init__(self):
        super().__init__("SECTGA", "CETAG", "CEL", core.Constant(28))

        self._append(
            core.Field(
                "SEC_ID",
                "Designator of Secondary Target",
                12,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "SEC_BE",
                "Basic Encyclopedia ID",
                15,
                charset=core.BCSA,
                converter=core.StringAscii(),
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
                default=b"0",
            )
        )
