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
