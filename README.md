# jbpy
[![PyPI - Version](https://img.shields.io/pypi/v/jbpy)](https://pypi.org/project/jbpy/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/jbpy)
[![PyPI - License](https://img.shields.io/pypi/l/jbpy)](./LICENSE)
[![SPEC 0 — Minimum Supported Dependencies](https://img.shields.io/badge/SPEC-0-green?labelColor=%23004811&color=%235CA038)](https://scientific-python.org/specs/spec-0000/)
<br>
[![Tests](https://github.com/ValkyrieSystems/jbpy/actions/workflows/test.yml/badge.svg)](https://github.com/ValkyrieSystems/jbpy/actions/workflows/test.yml)

**jbpy** is a library for reading and writing Joint BIIF Profile files. Including:
* National Imagery Transmission Format (NITF)
* North Atlantic Treaty Organisation (NATO) Secondary Imagery Format (NSIF)

The Joint BIIF Profile is available from the NSG Standards Registry.  See: https://nsgreg.nga.mil/doc/view?i=5533

## License
This repository is licensed under the [MIT license](./LICENSE).

## Testing
Some tests rely on the [JITC Quick Look Test Data](https://jitc.fhu.disa.mil/projects/nitf/testdata.aspx).
If this data is available, it can be used by setting the `JBPY_JITC_QUICKLOOK_DIR` environment variable.

```bash
JBPY_JITC_QUICKLOOK_DIR=<path> pytest
```
