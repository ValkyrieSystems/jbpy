import argparse
import collections.abc
import json
import os
import sys

import jbpy

try:
    from smart_open import open
except ImportError:
    pass


class _Encoder(json.JSONEncoder):
    def __init__(self, *args, full_details=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_details = full_details

    def default(self, obj):
        if isinstance(obj, collections.abc.Mapping):
            return dict(obj)
        if isinstance(obj, bytes):
            return list(obj)
        if isinstance(obj, jbpy.core.Field):
            if self.full_details:
                return {
                    "size": obj.size,
                    "offset": obj.get_offset(),
                    "value": obj.value,
                }
            return obj.value
        if isinstance(obj, jbpy.core.BinaryPlaceholder):
            if self.full_details:
                return {
                    "size": obj.size,
                    "offset": obj.get_offset(),
                    "value": "__binary__",
                }
            return f"__binary__ ({obj.get_size()} bytes)"
        if isinstance(obj, jbpy.core.SegmentList):
            return list(obj)
        if isinstance(obj, jbpy.core.TreSequence):
            return list(obj)
        return super().default(obj)


def main(args=None):
    parser = argparse.ArgumentParser(description="Display JBP Header content")
    parser.add_argument("filename", help="Path to JBP file")
    parser.add_argument(
        "--format",
        choices=["text", "json", "json-full"],
        default="text",
        help="Output format.  json-full adds offsets and sizes",
    )
    config = parser.parse_args(args)

    jbp = jbpy.Jbp()
    with open(config.filename, "rb") as file:
        jbp.load(file)

    try:
        if "json" in config.format:
            full_details = config.format == "json-full"
            print(json.dumps(jbp, indent=2, cls=_Encoder, full_details=full_details))
        else:
            jbp.print()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    return 0


if __name__ == "__main__":
    sys.exit(main())
