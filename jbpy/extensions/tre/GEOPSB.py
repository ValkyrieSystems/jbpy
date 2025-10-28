from jbpy import core


class GEOPSB(core.Tre):
    """Geopositioning Information TRE
    See STDI-0002 Volume 1 App P, Table P-2
    """

    def __init__(self):
        super().__init__("GEOPSB", "CETAG", "CEL", core.Constant(443))

        self._append(
            core.Field(
                "TYP",
                "Coordinate System Type",
                3,
                charset=core.BCSA,
                decoded_range=core.Enum(["MAP", "GEO", "DIG"]),
                converter=core.StringAscii(),
                default="MAP",
            )
        )

        self._append(
            core.Field(
                "UNI",
                "Coordinate Units",
                3,
                charset=core.BCSA,
                decoded_range=core.Enum(["SEC", "DEG", "M"]),
                converter=core.StringAscii(),
                default="M",
            )
        )

        self._append(
            core.Field(
                "DAG",
                "Geodetic Datum Name",
                80,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="World Geodetic System 1984",
            )
        )

        self._append(
            core.Field(
                "DCD",
                "Geodetic Datum Code",
                4,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="WGE",
            )
        )

        self._append(
            core.Field(
                "ELL",
                "Ellipsoid Name",
                80,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="World Geodetic System 1984",
            )
        )

        self._append(
            core.Field(
                "ELC",
                "Ellipsoid Code",
                3,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="WE",
            )
        )

        self._append(
            core.Field(
                "DVR",
                "Vertical Datum Reference",
                80,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="Geodetic",
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "VDCDVR",
                "Code (Category) of Vertical Reference",
                4,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="GEOD",
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "SDA",
                "Sounding Datum Name",
                80,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="Mean Sea",
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "VDCSDA",
                "Code for Sounding Datum",
                4,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="MSL",
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "ZOR",
                "Z Values False Origin",
                15,
                charset=core.BCSN_PI,  # BCS-N from document seems too permissive
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "GRD",
                "Grid Code",
                3,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "GRN",
                "Grid Description",
                80,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "ZNA",
                "Grid Zone Number",
                4,
                charset=core.BCSN,
                encoded_range=core.Regex(rb"[-0-9][0-9]{3}"),
                converter=core.Integer(),
                default=0,
            )
        )
