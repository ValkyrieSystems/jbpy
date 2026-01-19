import argparse
import os
import sys

import jbpy

try:
    from smart_open import open
except ImportError:
    pass


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
            print(jbp.as_json(full_details))
        else:
            jbp.print()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    return 0


if __name__ == "__main__":
    sys.exit(main())
