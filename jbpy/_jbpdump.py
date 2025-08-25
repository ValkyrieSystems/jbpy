import argparse
import os
import shutil
import sys

import jbpy

try:
    from smart_open import open
except ImportError:
    pass


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Extract raw byte data from a JBP file"
    )
    parser.add_argument("filename", help="Path to JBP file")
    group = parser.add_argument_group("Segment Selection", "Zero-based index")
    ex_group = group.add_mutually_exclusive_group(required=True)
    ex_group.add_argument("--image-segment", type=int)
    ex_group.add_argument("--graphic-segment", type=int)
    ex_group.add_argument("--text-segment", type=int)
    ex_group.add_argument("--data-extension-segment", type=int)
    ex_group.add_argument("--reserved-extension-segment", type=int)
    config = parser.parse_args(args)

    jbp = jbpy.Jbp()
    with open(config.filename, "rb") as infile:
        jbp.load(infile)

        if config.image_segment is not None:
            srcfilobj = jbp["ImageSegments"][config.image_segment]["Data"].as_filelike(
                infile
            )
        elif config.graphic_segment is not None:
            srcfilobj = jbp["GraphicSegments"][config.graphic_segment][
                "Data"
            ].as_filelike(infile)
        elif config.text_segment is not None:
            srcfilobj = jbp["TextSegments"][config.text_segment]["Data"].as_filelike(
                infile
            )
        elif config.data_extension_segment is not None:
            srcfilobj = jbp["DataExtensionSegments"][config.data_extension_segment][
                "DESDATA"
            ].as_filelike(infile)
        elif config.reserved_extension_segment is not None:
            srcfilobj = jbp["ReservedExtensionSegments"][
                config.reserved_extension_segment
            ]["RESDATA"].as_filelike(infile)

        try:
            shutil.copyfileobj(srcfilobj, sys.stdout.buffer)
        except BrokenPipeError:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        return 0


if __name__ == "__main__":
    sys.exit(main())
