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

The Joint BIIF Profile is available from the NSG Standards Registry.  See: https://nsgreg.nga.mil/doc/view?i=5674

## Install
`jbpy` can be installed using pip:

```sh
$ python -m pip install jbpy
```

`jbpy` can also be installed using conda and the conda-forge channel:

```sh
$ conda install --channel conda-forge jbpy
```

## License
This repository is licensed under the [MIT license](./LICENSE).

## Testing
Some tests rely on the [JITC Quick Look Test Data](https://jitc.fhu.disa.mil/projects/nitf/testdata.aspx).
If this data is available, it can be used by setting the `JBPY_JITC_QUICKLOOK_DIR` environment variable.

```bash
JBPY_JITC_QUICKLOOK_DIR=<path> pytest
```

## Support Data Extensions
The JBP document provides extensibility through Support Data Extensions (SDEs) such as Tagged Record Extensions (TREs)
and Data Extension Segments (DES).
To mimic this extensibility, `jbpy` defines two entry point groups which are used to load SDE plugins:

1. `jbpy.extensions.tre`
1. `jbpy.extensions.des_subheader`

`jbpy` provides a number of built-in SDEs and will load additional SDEs from separately installed packages provided
they are declared under these entry point groups as described below.

> [!WARNING]
> There is not currently a mechanism to arbitrate multiple SDEs that are registered under the same plugin name.

### TREs
A TRE plugin is named using a 6-character (left-justified and space-padded) TRETAG.
The object reference must resolve to a function with no required arguments that instantiates a `jbpy.core.Tre` object.

 `pyproject.toml` example:

```toml
[project.entry-points."jbpy.extensions.tre"]
"MYTRE " = "my_package.my_module:my_tre_func"
```

Once registered, a TRE object can be instantiated using `jbpy.tre_factory`:

```python
>>> import jbpy
>>> tre = jbpy.tre_factory("MYTRE")  # note: tag passed to factory must have trailing spaces stripped

```

### DES Subheaders
A DES subheader plugin is named using a 27-character string formed by concatenating the 25-character DESID and 2-digit
DESVER.
The object reference must resolve to a function that accepts a string-valued name and instantiates a
`jbpy.core.DataExtensionSubheader` object.

`pyproject.toml` example:

```toml
[project.entry-points."jbpy.extensions.des_subheader"]
"MY DES SUBHEADER         24" = "my_des_subheader_func"
```

Once registered, a DES subheader object can be instantiated using `jbpy.des_subheader_factory`:

```python
>>> import jbpy
>>> des_subhdr = jbpy.des_subheader_factory("MY DES SUBHEADER", 24)

```
