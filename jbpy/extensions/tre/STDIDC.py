from jbpy import core


class STDIDC(core.Tre):
    """Standard Identifier (STDIDC) TRE, Version C
    See STDI-0002 Volume 1 App D, Table D-1
    """

    def __init__(self):
        super().__init__("STDIDC", "CETAG", "CEL", core.Constant(89))

        self._append(
            core.Field(
                "ACQUISITION_DATE",
                "Acquisition Date",
                14,
                charset=core.BCSN,
                decoded_range=core.Regex(
                    core.PATTERN_CC
                    + core.PATTERN_YY
                    + core.PATTERN_MM
                    + core.PATTERN_DD
                    + core.PATTERN_HH
                    + core.PATTERN_mm
                    + core.PATTERN_SS
                ),  # should hyphens be allowed?
                converter=core.StringAscii(),
                default="",
            )
        )

        self._append(
            core.Field(
                "MISSION",
                "Mission Identification",
                14,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="",
            )
        )

        self._append(
            core.Field(
                "PASS",
                "Pass Number",
                2,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="",
            )
        )

        self._append(
            core.Field(
                "OP_NUM",
                "Image Operation Number",
                3,
                charset=core.BCSN_PI,
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "START_SEGMENT",
                "Start Segment ID",
                2,
                charset=core.BCSA,
                decoded_range=core.Regex(r"[A-Z]{2}"),
                converter=core.StringAscii(),
                default="",
            )
        )

        self._append(
            core.Field(
                "REPRO_NUM",
                "Reprocess Number",
                2,
                charset=core.BCSN_PI,
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "REPLAY_REGEN",
                "Replay Regen",
                3,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="",
            )
        )

        self._append(
            core.Field(
                "BLANK_FILL",
                "Blank Fill",
                1,
                charset=core.BCSA,
                decoded_range=core.Constant("_"),
                converter=core.StringAscii(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "START_COLUMN",
                "Starting Column Block",
                3,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "START_ROW",
                "Starting Row Block",
                5,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "END_SEGMENT",
                "Ending Segment ID",
                2,
                charset=core.BCSA,  # BCS-N in document seems to be a mistake
                decoded_range=core.Regex(r"[A-Z]{2}"),
                converter=core.StringAscii(),
                default="",
            )
        )

        self._append(
            core.Field(
                "END_COLUMN",
                "Ending Column Block",
                3,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "END_ROW",
                "Ending Row Block",
                5,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
            )
        )

        self._append(
            core.Field(
                "COUNTRY",
                "Country Code",
                2,
                charset=core.BCSA,
                decoded_range=core.Regex(r"[A-Z]{2}"),
                converter=core.StringAscii(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "WAC",
                "World Aeronautical Chart",
                4,
                charset=core.BCSN_PI,
                decoded_range=core.MinMax(1, 1866),
                converter=core.Integer(),
                default=None,
                nullable=True,
            )
        )

        dd = r"[0-8][0-9]"  # 00-89
        mm = r"[0-5][0-9]"  # 00-59
        x = r"(N|S)"
        ddd = r"(0[0-9]{2}|1[0-7][0-9])"  # 000-179
        y = r"(E|W)"
        self._append(
            core.Field(
                "LOCATION",
                "Location",
                11,
                charset=core.BCSA,  # BCS-N seems like a mistake in the document
                decoded_range=core.Regex(dd + mm + x + ddd + mm + y),
                converter=core.StringAscii(),
                default="",
            )
        )

        self._append(
            core.Field(
                "reserved0",  # blank in document
                "reserved",
                5,
                converter=core.Bytes(),
                default=None,
                nullable=True,
            )
        )

        self._append(
            core.Field(
                "reserved1",  # blank in document
                "reserved",
                8,
                converter=core.Bytes(),
                default=None,
                nullable=True,
            )
        )
