from jbpy import core
from jbpy.extensions import tre


class REGPTB(core.Tre):
    """Registration Points (REGPTB) TRE
    See STDI-0002 Volume 1 App P, Table P-7
    """

    def __init__(self):
        super().__init__("REGPTB", "CETAG", "CEL", core.MinMax(81, 99950))

        self._append(
            core.Field(
                "NUM_PTS",
                "Number of Registration Points",
                4,
                charset=core.BCSN_PI,  # BCSN seems too permissive
                decoded_range=core.MinMax(1, 1298),
                converter=core.Integer(),
                default=0,
                setter_callback=self._num_pts_handler,
            )
        )

        # Fields in "Number of Registration Points loop" handled by NUM_PTS callback

    def _num_pts_handler(self, field: core.Field) -> None:
        """Handle NUM_PTS value change"""
        last_field = self._children[-1]
        after = last_field
        num_before = (
            int(last_field.name.removeprefix("DIY"))
            if last_field.name.startswith("DIY")
            else 0
        )
        num = field.value
        for idx in range(num_before, num):
            after = self._insert_after(
                after,
                core.Field(
                    f"PID{idx + 1:04}",
                    "nth Registration Point ID",
                    10,
                    charset=core.BCSA,
                    converter=core.StringAscii(),
                    default="",
                ),
                core.Field(
                    f"LON{idx + 1:04}",
                    "Longitude/Easting of the nth Registration Point",
                    15,
                    charset=core.BCSN,
                    converter=tre.FlexibleFloat(),
                    default=0.0,
                ),
                core.Field(
                    f"LAT{idx + 1:04}",
                    "Latitude/Northing of the nth Registration Point",
                    15,
                    charset=core.BCSN,
                    converter=tre.FlexibleFloat(),
                    default=0.0,
                ),
                core.Field(
                    f"ZVL{idx + 1:04}",
                    "Elevation of the nth Registration Point",
                    15,
                    charset=core.BCSN,  # probably BCS-A in doc due to spaces;  use nullable for this instead
                    converter=tre.FlexibleFloat(),
                    default=None,
                    nullable=True,
                ),
                core.Field(
                    f"DIX{idx + 1:04}",
                    "Column Number of nth Registration Point",
                    11,
                    charset=core.BCSN,
                    converter=tre.FlexibleFloat(),
                    encoded_range=core.Not(
                        core.Constant(b"0" * 11)
                    ),  # all zeros intentionally left out of value range
                    default=0.0,
                ),
                core.Field(
                    f"DIY{idx + 1:04}",
                    "Row Number of nth Registration Point",
                    11,
                    charset=core.BCSN,
                    converter=tre.FlexibleFloat(),
                    encoded_range=core.Not(
                        core.Constant(b"0" * 11)
                    ),  # all zeros intentionally left out of value range
                    default=0.0,
                ),
            )
        if num < num_before:
            self._children = self._children[: 3 + (6 * num)]
