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
                core.BCSN,
                core.Regex(
                    core.PATTERN_CC
                    + core.PATTERN_YY
                    + core.PATTERN_MM
                    + core.PATTERN_DD
                    + core.PATTERN_HH
                    + core.PATTERN_mm
                    + core.PATTERN_SS
                ),  # should hyphens be allowed?
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "MISSION",
                "Mission Identification",
                14,
                core.BCSA,
                core.AnyRange(),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "PASS",
                "Pass Number",
                2,
                core.BCSA,
                core.AnyRange(),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "OP_NUM",
                "Image Operation Number",
                3,
                core.BCSN_PI,
                core.AnyRange(),
                core.Integer,
                default=0,
            )
        )

        self._append(
            core.Field(
                "START_SEGMENT",
                "Start Segment ID",
                2,
                core.BCSA,
                core.Regex(r"[A-Z]{2}"),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "REPRO_NUM",
                "Reprocess Number",
                2,
                core.BCSN_PI,
                core.AnyRange(),
                core.Integer,
                default=0,
            )
        )

        self._append(
            core.Field(
                "REPLAY_REGEN",
                "Replay Regen",
                3,
                core.BCSA,
                core.AnyRange(),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "BLANK_FILL",
                "Blank Fill",
                1,
                core.BCSA,
                core.AnyOf(core.Constant(""), core.Constant("_")),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "START_COLUMN",
                "Starting Column Block",
                3,
                core.BCSN_PI,
                core.MinMax(1, None),
                core.Integer,
                default=0,
            )
        )

        self._append(
            core.Field(
                "START_ROW",
                "Starting Row Block",
                5,
                core.BCSN_PI,
                core.MinMax(1, None),
                core.Integer,
                default=0,
            )
        )

        self._append(
            core.Field(
                "END_SEGMENT",
                "Ending Segment ID",
                2,
                core.BCSA,  # BCS-N in document seems to be a mistake
                core.Regex(r"[A-Z]{2}"),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "END_COLUMN",
                "Ending Column Block",
                3,
                core.BCSN_PI,
                core.MinMax(1, None),
                core.Integer,
                default=0,
            )
        )

        self._append(
            core.Field(
                "END_ROW",
                "Ending Row Block",
                5,
                core.BCSN_PI,
                core.MinMax(1, None),
                core.Integer,
                default=0,
            )
        )

        self._append(
            core.Field(
                "COUNTRY",
                "Country Code",
                2,
                core.BCSA,
                core.AnyOf(core.Constant(""), core.Regex(r"[A-Z]{2}")),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "WAC",
                "World Aeronautical Chart",
                4,
                core.BCSN + core.BCSA_SPACE,
                core.AnyOf(
                    core.Constant(""),
                    core.Regex(
                        r"(?!0000)(0[0-9]{3}|1[0-7][0-9]{2}|18[0-5][0-9])|186[0-6]"  # 0001-1866
                    ),
                ),
                core.StringAscii,
                default="",
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
                core.BCSA,  # BCS-N seems like a mistake in the document
                core.Regex(dd + mm + x + ddd + mm + y),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "reserved0",  # blank in document
                "reserved",
                5,
                core.BCSA,
                core.AnyRange(),
                core.StringAscii,
                default="",
            )
        )

        self._append(
            core.Field(
                "reserved1",  # blank in document
                "reserved",
                8,
                core.BCSA,
                core.AnyRange(),
                core.StringAscii,
                default="",
            )
        )
