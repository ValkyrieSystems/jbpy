# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]


## [0.3.0] - 2025-10-16

### Added
- `readinto`, `readline`, and `readlines` methods to `SubFile`
- `py.typed` marker file
- `examples` subpackage demonstrating how jbpy can be used
- `image_data` submodule containing functions to aid parsing image segment data

### Changed
- `AnyOf` now short-circuits

### Removed
- Unnecessary LSSHn and LTSHn callbacks
- MIL-STD-2500C based `ICAT` enumeration. JBP uses the NTB Field Value Registry.

### Fixed
- Only add `DESSHF` to `DataExtensionSubheader` when `DESSHL` is nonzero


## [0.2.0] - 2025-08-26

### Added
- Support for Text and Graphic subheaders
- `SubFile` class and `as_filelike` method to improve compatibility with other libraries
- `jbpdump` utility for pulling the content out of segments
- `jbpinfo` now supports formatting the output as JSON
- CLI utilities now use `smart_open` if it is installed

### Fixed
- Handling for broken pipes when output of CLI utility is piped to another command


## [0.1.0] - 2025-05-26

### Added
- Basic JBP functionality copied from SARkit's `_nitf_io.py`

[unreleased]: https://github.com/ValkyrieSystems/jbpy/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/ValkyrieSystems/jbpy/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ValkyrieSystems/jbpy/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ValkyrieSystems/jbpy/releases/tag/v0.1.0
