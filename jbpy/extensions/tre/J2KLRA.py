from jbpy import core
from jbpy.extensions import tre


class J2KLRA(core.Tre):
    """JPEG 2000 Layer Target Bit-Rates TRE
    See BIIF Profile for JPEG 2000 Version 01.20, Table 8-3

    The ranges here are from Table 8-3 "Recommended J2KLRA TRE" rather than the apparent subset/profile
    that is in Table F-17 "JPEG 2000 Layer Target Bit-Rates (J2KLRA TRE) Format for TPJE"
    """

    def __init__(self):
        min_length = 1 + 2 + 5 + 3 + 1 * (3 + 9)
        max_length = 1 + 2 + 5 + 3 + 999 * (3 + 9) + 2 + 5 + 3
        super().__init__("J2KLRA", "CETAG", "CEL", core.MinMax(min_length, max_length))

        self._append(
            core.Field(
                "ORIG",
                "Original compressed data",
                1,
                charset=core.BCSN_PI,  #  BCS-N seems too permissive
                converter=core.Integer(),
                default=0,
                setter_callback=self._orig_handler,
            )
        )

        # Original compressed image information
        self._append(
            core.Field(
                "NLEVELS_O",
                "Number of wavelet levels in original image",
                2,
                charset=core.BCSN_PI,  #  BCS-N seems too permissive
                decoded_range=core.MinMax(None, 32),
                converter=core.Integer(),
                default=0,
            )
        )
        self._append(
            core.Field(
                "NBANDS_O",
                "Number of bands in original image",
                5,
                charset=core.BCSN_PI,  #  BCS-N seems too permissive
                decoded_range=core.MinMax(1, 16384),
                converter=core.Integer(),
                default=0,
            )
        )
        self._append(
            core.Field(
                "NLAYERS_O",
                "Number of layers in original image",
                3,
                charset=core.BCSN_PI,  #  BCS-N seems too permissive
                decoded_range=core.MinMax(1, None),
                converter=core.Integer(),
                default=0,
                setter_callback=self._nlayers_o_handler,
            )
        )
        # Handled by NLAYERS_O callback:
        # - LAYER_IDn
        # - BITRATEn
        # Handled by ORIG callback:
        # - NLEVELS_I
        # - NBANDS_I
        # - NLAYERS_I

    def _orig_handler(self, field: core.Field) -> None:
        """Conditional fields (NLEVELS_I, NLAYERS_I, NBANDS_I) are present if this field indicates a parsed stream"""
        indicates_parsed_stream = (
            field.value % 2
        )  # even values are original, odd values are parsed
        nxxx_i_field_present = [
            f"N{x}_I" in self for x in ("LEVELS", "BANDS", "LAYERS")
        ]
        if all(nxxx_i_field_present):
            has_nxxx_i_fields = True
        elif not any(nxxx_i_field_present):
            has_nxxx_i_fields = False
        else:
            raise RuntimeError("Only some of the conditional fields are present")
        if indicates_parsed_stream and not has_nxxx_i_fields:
            self._append(
                core.Field(
                    "NLEVELS_I",
                    "Number of wavelet levels in this image",
                    2,
                    charset=core.BCSN_PI,  #  BCS-N seems too permissive
                    decoded_range=core.MinMax(None, 32),
                    converter=core.Integer(),
                    default=0,
                )
            )
            self._append(
                core.Field(
                    "NBANDS_I",
                    "Number of bands in this image",
                    5,
                    charset=core.BCSN_PI,  #  BCS-N seems too permissive
                    decoded_range=core.MinMax(1, 16384),
                    converter=core.Integer(),
                    default=0,
                )
            )
            self._append(
                core.Field(
                    "NLAYERS_I",
                    "Number of layers in this image",
                    3,
                    charset=core.BCSN_PI,  #  BCS-N seems too permissive
                    decoded_range=core.MinMax(1, None),
                    converter=core.Integer(),
                    default=0,
                )
            )
        if not indicates_parsed_stream and has_nxxx_i_fields:
            self._remove_all(r"N(LEVELS|BANDS|LAYERS)_I")

    def _nlayers_o_handler(self, field: core.Field) -> None:
        """Handle repeated LAYER_ID/BITRATE section controlled by NLAYERS_O"""
        bitrate_before = tuple(self.find_all(r"BITRATE[0-9]{3}"))
        nlayers_before = len(bitrate_before)
        expected_suffixes = [f"{x:03}" for x in range(nlayers_before)]
        assert expected_suffixes == [
            x.name.removeprefix("BITRATE") for x in bitrate_before
        ]
        assert expected_suffixes == [
            x.name.removeprefix("LAYER_ID") for x in self.find_all(r"LAYER_ID[0-9]{3}")
        ]
        nlayers = field.value
        after = bitrate_before[-1] if bitrate_before else field
        for idx in range(nlayers_before, nlayers):
            after = self._insert_after(
                after,
                core.Field(
                    f"LAYER_ID{idx:03d}",
                    "Layer ID Number",
                    3,
                    charset=core.BCSN_PI,  #  BCS-N seems too permissive
                    decoded_range=core.MinMax(None, 998),
                    converter=core.Integer(),
                    default=0,
                ),
            )
            after = self._insert_after(
                after,
                core.Field(
                    f"BITRATE{idx:03d}",
                    "Bitrate",
                    9,
                    charset=core.BCSN,  # BCS-A seems too permissive
                    encoded_range=tre.EncodedFixedPoint("unsigned", 2, 6),
                    decoded_range=core.MinMax(0, 37.0),
                    converter=tre.FloatFormat("0{size}.6f"),
                    default=0.0,
                ),
            )
        for idx in range(nlayers, nlayers_before):
            self._remove_all(rf"(BITRATE|LAYER_ID){idx:03d}")
