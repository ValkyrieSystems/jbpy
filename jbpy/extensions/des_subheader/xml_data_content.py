import logging

from jbpy import core

logger = logging.getLogger(__name__)


class XmlDataContentSubheader(core.DataExtensionSubheader):
    """XML_DATA_CONTENT Data Extension Segment (DES) Subheader
    See STDI-0002 Volume 2 App F, Table F-1
    """

    allowed_subheader_lengths = (0, 5, 283, 773)

    def __init__(self, name):
        super().__init__(
            name,
            desid_constraint=core.Constant("XML_DATA_CONTENT"),
            desver_constraint=core.Constant(1),
            desshl_constraint=core.Enum(self.allowed_subheader_lengths),
        )

        self.all_fields = [
            core.Field(
                "DESCRC",
                "Cyclic Redundancy Check",
                5,
                charset=core.BCSN_PI,
                decoded_range=core.AnyOf(core.MinMax(0, 65535), core.Constant(99999)),
                converter=core.Integer(),
                default=0,
            ),
            core.Field(
                "DESSHFT",
                "XML File Type",
                8,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="",
            ),
            core.Field(
                "DESSHDT",
                "Date and Time",
                20,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="",
            ),
            core.Field(
                "DESSHRP",
                "Responsible Party",
                40,
                charset=core.U8,
                converter=core.StringUtf8(),
                default="",
            ),
            core.Field(
                "DESSHSI",
                "Specification Identifier",
                60,
                charset=core.U8,
                converter=core.StringUtf8(),
                default="",
            ),
            core.Field(
                "DESSHSV",
                "Specification Version",
                10,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="",
            ),
            core.Field(
                "DESSHSD",
                "Specification Date",
                20,
                charset=core.BCSA,
                converter=core.StringAscii(),
                default="",
            ),
            core.Field(
                "DESSHTN",
                "Target Namespace",
                120,
                charset=core.BCSA,
                converter=core.StringAscii(),
                nullable=True,
                default=None,
            ),
            core.Field(
                "DESSHLPG",
                "Location - Polygon",
                125,
                charset=core.BCSA,
                converter=core.StringAscii(),
                nullable=True,
                default=None,
            ),
            core.Field(
                "DESSHLPT",
                "Location - Point",
                25,
                charset=core.BCSA,
                converter=core.StringAscii(),
                nullable=True,
                default=None,
            ),
            core.Field(
                "DESSHLI",
                "Location - Identifier",
                20,
                charset=core.BCSA,
                converter=core.StringAscii(),
                nullable=True,
                default=None,
            ),
            core.Field(
                "DESSHLIN",
                "Location Identifier Namespace URI",
                120,
                charset=core.BCSA,
                converter=core.StringAscii(),
                nullable=True,
                default=None,
            ),
            core.Field(
                "DESSHABS",
                "Abstract",
                200,
                charset=core.U8,
                converter=core.StringUtf8(),
                nullable=True,
                default=None,
            ),
        ]

    def _populate_user_defined_subheader(self, desshl_field) -> None:
        if desshl_field.value not in self.allowed_subheader_lengths:
            logger.warning(
                f"Invalid user defined subheader length. {desshl_field.value} not in {self.allowed_subheader_lengths}"
            )

        # remove current user-defined subheader fields
        del self._children[self._children.index(desshl_field) + 1 :]
        current_size = 0
        for field in self.all_fields:
            if current_size == desshl_field.value:
                break
            elif current_size < desshl_field.value:
                self._append(field)
                current_size += field.size
            elif current_size > desshl_field.value:
                raise ValueError(
                    f"Invalid XML_DATA_CONTENT header {desshl_field.value=}"
                )
