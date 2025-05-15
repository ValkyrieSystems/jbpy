**pybiif** is a library for reading and writing Joint BIIF Profile files. Including:
* National Imagery Transmission Format (NITF)
* North Atlantic Treaty Organisation (NATO) Secondary Imagery Format (NSIF)

## License
This repository is licensed under the [MIT license](./LICENSE).

## Testing
Some tests rely on the [JITC Quick Look Test Data](https://jitc.fhu.disa.mil/projects/nitf/testdata.aspx).
If this data is available, it can be used by setting the `PYBIIF_JITC_QUICKLOOK_DIR` environment variable.

```bash
PYBIIF_JITC_QUICKLOOK_DIR=<path> pytest
```
