from jbpy import core
from jbpy.extensions import tre


class PRJPSB(core.Tre):
    """Projection Parameters TRE
    See STDI-0002 Volume 1 App P, Table P-3
    """

    def __init__(self):
        super().__init__("PRJPSB", "CETAG", "CEL", core.MinMax(113, 248))

        self._append(
            core.Field(
                "PRN",
                "Projection Name",
                80,  # 3 in "Administrative Updates: 02 April 2024" version seems like a mistake
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="Transverse Mercator",
            )
        )

        self._append(
            core.Field(
                "PCO",
                "Projection Code",
                2,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="TC",
            )
        )

        self._append(
            core.Field(
                "NUM_PRJ",
                "Number of Projection Parameters",
                1,
                charset=core.BCSN_PI,  # BCSN is too permissive
                converter=core.Integer(),
                default=0,
                setter_callback=self._num_prj_handler,
            )
        )

        # PRJn

        self._append(
            core.Field(
                "XOR",
                "Projection False X (Easting) Origin",
                15,
                charset=core.BCSN,
                converter=tre.FlexibleFloat(),
                default=0.0,
            )
        )

        self._append(
            core.Field(
                "YOR",
                "Projection False Y (Northing) Origin",
                15,
                charset=core.BCSN,
                converter=tre.FlexibleFloat(),
                default=0.0,
            )
        )

    def _num_prj_handler(self, field: core.Field) -> None:
        """Handle NUM_PRJ value change"""
        prj_before = tuple(sorted(self.find_all(r"PRJ[1-9]"), key=lambda x: x.name))
        num = field.value
        after = prj_before[-1] if prj_before else field
        for idx in range(len(prj_before), num):
            new_field = core.Field(
                f"PRJ{idx + 1}",
                "nth Projection Parameter",
                15,
                charset=core.BCSN,
                converter=tre.FlexibleFloat(),  # probably what we want?
                default=0.0,
            )
            after = self._insert_after(after, new_field)
        for idx in range(num, len(prj_before)):
            self._remove_all(f"PRJ{idx + 1}")
