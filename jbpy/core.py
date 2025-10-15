"""Utilities for reading and writing JBP files (NITF, NSIF)

The Field, Group, Subheaders, and Jbp classes have a dictionary-esque interface
with key names directly copied from JBP-2024.1 where possible.

In JBP, the presence of optional fields is controlled by the values of preceding
fields.  This library attempts to mimic this behavior by adding or removing fields
as necessary when a field is updated.  For example adding image segments is accomplished
by setting the NUMI field.

Setting the value of fields is done using the `value` property.  `value` uses common python
types (int, str, etc...) and serializes to the BIIF format behind the scenes.
"""

import abc
import collections.abc
import datetime
import importlib.metadata
import logging
import os
import re
from collections.abc import Callable, Iterable
from typing import Any, Iterator, Self

logger = logging.getLogger(__name__)


class BinaryFile_R:
    """Binary file-like object supporting reading"""

    @abc.abstractmethod
    def seek(self, __offset: int, __whence: int = ...) -> int: ...
    @abc.abstractmethod
    def read(self, __length: int = ...) -> bytes: ...


class BinaryFile_RW(BinaryFile_R):
    """Binary file-like object supporting reading and writing"""

    @abc.abstractmethod
    def write(self, __data: bytes) -> int: ...


class SubFile:
    """File-like object mapping to a contiguous subset of another file-like object"""

    def __init__(self, file: BinaryFile_R, start: int, length: int):
        """
        Initialize a SubFile view.

        Arguments
        ---------
        file : file-like
            An open file object.  Must be binary.
        start : int
            Start byte offset of the subfile
        length : int
            Number of bytes to expose from the start
        """
        self._file = file
        self._start = start
        self._length = length
        self._pos = 0  # position within the subfile

    def seek(self, offset: int, whence: int = 0) -> int:
        """
        Seek to a position within the subfile.

        Arguments
        ---------
        offset : int
            Offset to seek
        whence : int
            0 (start), 1 (current), or 2 (end of subfile)

        Returns
        -------
        int
            Current offset in the SubFile
        """
        if whence == 0:
            new_pos = offset
        elif whence == 1:
            new_pos = self._pos + offset
        elif whence == 2:
            new_pos = self._length + offset
        else:
            raise ValueError(f"whence value {whence} unsupported")

        if new_pos < 0:
            raise OSError("Seek before start of subfile.")

        self._pos = new_pos
        return self._pos

    def tell(self) -> int:
        """Return the current position within the subfile."""
        return self._pos

    def read(self, size: int = -1) -> bytes:
        """
        Read data from the subfile.

        Arguments
        ---------
        size : int
            Number of bytes to read, or -1 for all remaining
        """
        if self._pos >= self._length:
            return b""

        read_len = (
            self._length - self._pos
            if size < 0
            else min(size, self._length - self._pos)
        )
        self._file.seek(self._start + self._pos)
        data = self._file.read(read_len)
        self._pos += len(data)
        return data

    def readinto(self, b):
        self._file.seek(self._start + self._pos)
        num_read = self._file.readinto(b)
        if num_read is not None:
            self._pos += num_read
        return num_read

    def readline(self, size=-1):
        self._file.seek(self._start + self._pos)
        data = self._file.readline(size)
        self._pos += len(data)
        return data

    def readlines(self, hint=-1):
        self._file.seek(self._start + self._pos)
        before = self._file.tell()
        data = self._file.readlines(hint)
        after = self._file.tell()
        self._pos += after - before
        return data


class PythonConverter:
    """Class for converting between JBP field bytes and python types"""

    def __init__(self, name: str, size: int):
        self.name: str = name
        self.size: int = size

    def to_bytes(self, decoded_value):
        encoded = self.to_bytes_impl(decoded_value)
        truncated = encoded[: self.size]
        if len(truncated) < len(encoded):
            logger.warning(
                f"JBP header field {self.name} truncated to {self.size} characters.\n"
                f"    old: {encoded}"
                f"    new: {truncated}"
            )
        return truncated

    def to_bytes_impl(self, decoded_value: Any) -> bytes:
        raise NotImplementedError()

    def from_bytes(self, encoded_value: bytes) -> Any:
        return self.from_bytes_impl(encoded_value)

    def from_bytes_impl(self, encoded_value) -> Any:
        raise NotImplementedError()


class StringUtf8(PythonConverter):
    """Convert to/from str"""

    def to_bytes_impl(self, decoded_value: str) -> bytes:
        return str.ljust(decoded_value, self.size).encode()

    def from_bytes_impl(self, encoded_value: bytes) -> str:
        return encoded_value.decode().rstrip(" ")


class StringAscii(PythonConverter):
    """Convert to/from str"""

    def to_bytes_impl(self, decoded_value: str) -> bytes:
        return str.ljust(decoded_value, self.size).encode("ascii")

    def from_bytes_impl(self, encoded_value: bytes) -> str:
        return encoded_value.decode("ascii").rstrip(" ")


class StringISO8859_1(PythonConverter):  # noqa: N801
    """Convert to/from an ISO 8859-1 str

    Note
    ----
    JBP-2021.2 Table D-1 specifies the full ECS-A character set, which
    happens to match ISO 8859 part 1.
    """

    def to_bytes_impl(self, decoded_value: str) -> bytes:
        return str.ljust(decoded_value, self.size).encode("iso8859_1")

    def from_bytes_impl(self, encoded_value: bytes) -> str:
        return encoded_value.decode("iso8859_1").rstrip(" ")


def int_pair(length: int):
    """returns Python Converter class for handling 2 concatenated ints to/from a tuple"""

    class IntPair(PythonConverter):
        def to_bytes_impl(self, decoded_value: tuple[int, int]) -> bytes:
            return (
                f"{decoded_value[0]:0{length}d}{decoded_value[1]:0{length}d}".encode()
            )

        def from_bytes_impl(self, encoded_value: bytes) -> tuple[int, int]:
            return (int(encoded_value[0:length]), int(encoded_value[length:]))

    return IntPair


class Bytes(PythonConverter):
    """Convert to/from bytes"""

    def to_bytes_impl(self, decoded_value: bytes) -> bytes:
        return decoded_value

    def from_bytes_impl(self, encoded_value: bytes) -> bytes:
        return encoded_value


class Integer(PythonConverter):
    """convert to/from int"""

    def to_bytes_impl(self, decoded_value: int) -> bytes:
        decoded_value = int(decoded_value)
        return f"{decoded_value:0{self.size}}".encode()

    def from_bytes_impl(self, encoded_value: bytes) -> int:
        return int(encoded_value)


class RGB(PythonConverter):
    """convert to/from three int tuple"""

    def to_bytes_impl(self, decoded_value: tuple[int, int, int]) -> bytes:
        assert self.size == 3
        return (
            decoded_value[0].to_bytes(1, "big")
            + decoded_value[1].to_bytes(1, "big")
            + decoded_value[2].to_bytes(1, "big")
        )

    def from_bytes_impl(self, encoded_value: bytes) -> tuple[int, int, int]:
        return (encoded_value[0], encoded_value[1], encoded_value[2])


# Character sets (see 4.6.3.1)
# Extended Character Set (ECS)
ECS = "\x20-\x7e\xa0-\xff\x0a\x0c\x0d"
# Extended Character Set - Alphanumeric (ECS-A)
ECSA = "\x20-\x7e\xa0-\xff"
# Basic Character Set (BCS)
BCS = "\x20-\x7e\x0a\x0c\x0d"
# Basic Character Set - Alphanumeric (BCS-A)
BCSA = "\x20-\x7e"
# Basic Character Set - Numeric (BCS-N)
BCSN = "\x30-\x39\x2b\x2d\x2e\x2f"
# Basic Character Set - Numeric Integer (BCS-N integer)
BCSN_I = "\x30-\x39\x2b\x2d"
# Basic Character Set - Numeric Positive Integer (BCS-N positive integer)
BCSN_PI = "\x30-\x39"
# UTF-8
U8 = "\x00-\xff"


class RangeCheck(abc.ABC):
    """Base Class for checking the range of a JBP field"""

    @abc.abstractmethod
    def isvalid(self, decoded_value: Any) -> bool:
        """Returns ``True`` if field satisfies range check."""


class AnyRange(RangeCheck):
    """Field has no range restrictions"""

    def isvalid(self, decoded_value: Any) -> bool:
        return True


class MinMax(RangeCheck):
    """Field has a minimum and/or maximum value

    Args
    ----
    minimum:
        Minimum value.  A value of 'None' indicates no minimum.
    maximum:
        Maximum value.  A value of 'None' indicates no maximum.

    """

    def __init__(self, minimum: int | None, maximum: int | None):
        self.minimum = minimum
        self.maximum = maximum

    def isvalid(self, decoded_value: int) -> bool:
        valid = True
        if self.minimum is not None:
            valid &= decoded_value >= self.minimum
        if self.maximum is not None:
            valid &= decoded_value <= self.maximum
        return valid


class Regex(RangeCheck):
    """Field value is restricted by a regex"""

    def __init__(self, pattern: str):
        self.pattern = pattern

    def isvalid(self, decoded_value: str) -> bool:
        return bool(re.fullmatch(self.pattern, decoded_value))


class Constant(RangeCheck):
    """Field value must be a constant"""

    def __init__(self, const: str | int):
        self.const = const

    def isvalid(self, decoded_value: str | int) -> bool:
        return decoded_value == self.const


class Enum(RangeCheck):
    """Field value must match one value of an Enumeration"""

    def __init__(self, enumeration: Iterable):
        self.enumeration = set(enumeration)

    def isvalid(self, decoded_value: Any) -> bool:
        return decoded_value in self.enumeration


class AnyOf(RangeCheck):
    """Field value must match one of many different RangeChecks

    Args
    ----
    *ranges: RangeCheck
        RangeCheck objects to check against

    """

    def __init__(self, *ranges: RangeCheck):
        self.ranges = ranges

    def isvalid(self, decoded_value: Any) -> bool:
        # Use any(generator) to ensure short circuit logic
        return any(check.isvalid(decoded_value) for check in self.ranges)


class Not(RangeCheck):
    """Negate a range check"""

    def __init__(self, range_check: RangeCheck):
        self.range_check = range_check

    def isvalid(self, decoded_value: Any) -> bool:
        return not self.range_check.isvalid(decoded_value)


# Common Regex patterns
PATTERN_CC = "[0-9]{2}"
PATTERN_YY = "[0-9]{2}"
PATTERN_MM = "(0[1-9]|1[0-2])"  # MM
PATTERN_DD = "(0[1-9]|[12][0-9]|3[0-1])"  # DD
PATTERN_HH = "([0-1][0-9]|2[0-3])"  # hh
PATTERN_MM = "([0-5][0-9])"  # mm
PATTERN_SS = "([0-5][0-9]|60)"  # ss
DATETIME_REGEX = Regex(
    f"({PATTERN_CC}|--)"
    + f"({PATTERN_YY}|--)"
    + f"({PATTERN_MM}|--)"
    + f"({PATTERN_DD}|--)"
    + f"({PATTERN_HH}|--)"
    + f"({PATTERN_MM}|--)"
    + f"({PATTERN_SS}|--)"
)
DATE_REGEX = Regex(PATTERN_CC + PATTERN_YY + PATTERN_MM + PATTERN_DD)


class JbpIOComponent:
    """Base Class for read/writable JBP components"""

    def __init__(self, name: str):
        self.name = name
        self._parent: ComponentCollection | None = None

    def load(self, fd: BinaryFile_R) -> Self:
        """Read from a file descriptor
        Args
        ----
        fd: file-like
            Binary file-like object to read from

        Returns
        -------
        A reference to self

        """
        try:
            self._load_impl(fd)
            return self
        except Exception:
            logger.error(f"Failed to read {self.name}")
            raise

    def dump(self, fd: BinaryFile_RW, seek_first: bool = False) -> int:
        """Write to a file descriptor
        Args
        ----
        fd: file-like
            Binary file-like object to write to
        seek_first: bool
            Seek to the components offset before writing

        Returns
        -------
        int
            Number of bytes written
        """
        if seek_first:
            fd.seek(self.get_offset(), os.SEEK_SET)

        try:
            return self._dump_impl(fd)
        except Exception:
            logger.error(f"Failed to wite {self.name}")
            raise

    def _load_impl(self, fd: BinaryFile_R) -> None:
        raise NotImplementedError()

    def _dump_impl(self, fd: BinaryFile_RW) -> int:
        raise NotImplementedError()

    def get_offset(self) -> int:
        """Return the offset from the start of the file to this component"""
        offset = 0
        if self._parent is not None:
            offset = self._parent.get_offset_of(self)
        return offset

    def get_size(self) -> int:
        """Size of this component in bytes"""
        raise NotImplementedError()

    def print(self) -> None:
        """Print information about the component to stdout"""
        raise NotImplementedError()

    def finalize(self):
        """Perform any necessary final updates"""
        pass

    def as_filelike(self, file: BinaryFile_R) -> SubFile:
        """Create file object containing just this component

        Arguments
        ---------
        file : file-like
            File object for entire file

        Returns
        -------
        SubFile
            File like object for this component
        """
        return SubFile(file, self.get_offset(), self.get_size())


class Field(JbpIOComponent):
    """JBP Field containing a single value.
    Intended to have 1:1 mapping to rows in JBP-2024.1 header tables.

    Args
    ----
    name: str
        Name of this field
    description: str
        Text description of the field
    size: int
        Size in bytes of the field
    charset: str
        regex expression matching a single character
    range: `RangeCheck` object
        `RangeCheck` object to check acceptable values
    converter_class: `PythonConverter` class
        PythonConverter class to use to convert to/from python data types
    default: any
        Initial python value of the field
    setter_callback: callable
        function to call if the field's value changes

    Attributes
    ----------
    description
        Text description of the field.  For informational purposes only.
    size
        Field size in bytes
    encoded_value
        Field value as bytes
    value
        Field value as python type
    """

    def __init__(
        self,
        name: str,
        description: str,
        size: int,
        charset: str | None,
        range: RangeCheck,
        converter_class: type[PythonConverter],
        *,
        default: Any,
        setter_callback: Callable | None = None,
    ):
        super().__init__(name)
        self.description = description
        self._size = size
        self._charset = charset
        self._range = range
        self._converter_class = converter_class
        self._converter = converter_class(name, size)
        self._setter_callback = setter_callback

        self._encoded_value = self._converter.to_bytes(default)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented

        return (
            self.name == other.name
            and self.description == other.description
            and self._charset == other._charset
            and self.encoded_value == other.encoded_value
        )

    def isvalid(self) -> bool:
        """Check if the field value matches the required character set and range restrictions"""
        valid_charset = (
            True
            if self._charset is None
            else bool(re.fullmatch(f"[{self._charset}]*", self.encoded_value.decode()))
        )

        valid_range = self._range.isvalid(self.value)
        return valid_charset and valid_range

    @property
    def encoded_value(self) -> bytes:
        return self._encoded_value

    @encoded_value.setter
    def encoded_value(self, value: bytes):
        self._encoded_value = value

        if not self.isvalid():
            logger.warning(f"{self.name}: Invalid field value: {self.encoded_value!r}")

    @property
    def size(self) -> int:
        return self._size

    @size.setter
    def size(self, value: int):
        old_value = self._size
        self._size = value
        self._converter = self._converter_class(self.name, self._size)

        if (old_value != self._size) and self._setter_callback:
            self._setter_callback(self)

    @property
    def value(self) -> Any:
        return self._converter.from_bytes(self.encoded_value)

    @value.setter
    def value(self, val: Any):
        self._set_value(val, callback=self._setter_callback)

    def _set_value(self, val, callback=None):
        self.encoded_value = self._converter.to_bytes(val)

        if callback:
            callback(self)

    def _load_impl(self, fd: BinaryFile_R) -> None:
        self.encoded_value = fd.read(self.size)

        if self._setter_callback:
            self._setter_callback(self)

    def _dump_impl(self, fd: BinaryFile_RW) -> int:
        return fd.write(self.encoded_value)

    def get_size(self) -> int:
        return self.size

    def print(self) -> None:
        print(
            f"{self.name:15}{self.size:11} @ {self.get_offset():11} {self.encoded_value!r}"
        )


class BinaryPlaceholder(JbpIOComponent):
    """Represents a block of large binary data.

    This class does not actually read, write or store data, only seek past it.

    """

    def __init__(self, name: str, size: int):
        super().__init__(name)
        self._size = size

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.name == other.name and self._size == other._size

    @property
    def size(self) -> int:
        return self._size

    @size.setter
    def size(self, value: int):
        self._size = value

    def _load_impl(self, fd: BinaryFile_R):
        fd.seek(self.size, os.SEEK_CUR)

    def _dump_impl(self, fd: BinaryFile_RW) -> int:
        if self.size:
            fd.seek(self.size, os.SEEK_CUR)
        return self.size

    def get_size(self) -> int:
        return self.size

    def print(self) -> None:
        print(f"{self.name:15}{self.size:11} @ {self.get_offset():11} <Binary>")


class ComponentCollection(JbpIOComponent):
    """Base class for components with child sub-components"""

    def __init__(self, name: str):
        super().__init__(name)
        self._children: list[JbpIOComponent] = []

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented

        return len(self._children) == len(other._children) and all(
            [left == right for left, right in zip(self._children, other._children)]
        )

    def __len__(self):
        return len(self._children)

    def get_size(self) -> int:
        size = 0
        for child in self._children:
            size += child.get_size()
        return size

    def _load_impl(self, fd: BinaryFile_R) -> None:
        for child in self._children:
            child.load(fd)

    def _dump_impl(self, fd: BinaryFile_RW) -> int:
        written = 0
        for child in self._children:
            written += child.dump(fd)
        return written

    def _append(self, field: JbpIOComponent) -> None:
        field._parent = self
        self._children.append(field)

    def _extend(self, fields: Iterable[JbpIOComponent]) -> None:
        for field in fields:
            self._append(field)

    def get_offset_of(self, child_obj: JbpIOComponent) -> int:
        offset = self.get_offset()

        for child in self._children:
            if child is child_obj:
                return offset
            else:
                offset += child.get_size()
        else:
            raise ValueError(f"Could not find {child_obj.name}")

    def print(self) -> None:
        for child in self._children:
            child.print()

    def finalize(self):
        for child in self._children:
            child.finalize()


class Group(ComponentCollection, collections.abc.Mapping):
    """
    A Collection of JBP fields.  Indexed by JBP short names.

    Args
    ----
    name: str
        Name to give the group of fields

    """

    def __init__(self, name):
        super().__init__(name)

    def _child_names(self) -> list[str]:
        return [child.name for child in self._children]

    def __iter__(self):
        return iter(self._child_names())

    def __getitem__(self, key: str):
        try:
            index = self._index(key)
        except ValueError:
            raise KeyError(key)

        return self._children[index]

    def _insert_after(
        self, existing: JbpIOComponent, field: JbpIOComponent
    ) -> JbpIOComponent:
        insert_pos = self._children.index(existing) + 1
        self._children.insert(insert_pos, field)
        field._parent = self
        return field

    def find_all(self, pattern: str) -> Iterator[JbpIOComponent]:
        """Find child components with names matching a regex pattern
        Args
        ----
        pattern : str
            Regex pattern

        Yields
        ------
        child with name matching `pattern`
        """
        for child in self._children[:]:
            if re.fullmatch(pattern, child.name):
                yield child

    def _remove_all(self, pattern: str) -> None:
        for child in self.find_all(pattern):
            self._children.remove(child)

    def _index(self, name: str) -> int:
        return self._child_names().index(name)

    def print(self) -> None:
        for child in self._children:
            child.print()


class SegmentList(ComponentCollection, collections.abc.Sequence):
    """A sequence of JBP segments"""

    def __init__(
        self, name: str, field_creator: Callable, minimum: int = 0, maximum: int = 1
    ):
        super().__init__(name)
        self.field_creator = field_creator
        self.minimum = minimum
        self.maximum = maximum
        self.set_count(self.minimum)

    def __getitem__(self, idx):
        return self._children[idx]

    def set_count(self, size: int) -> None:
        if not self.minimum <= size <= self.maximum:
            raise ValueError(f"Invalid {size=}")
        for idx in range(len(self._children), size):
            new_field = self.field_creator(idx + 1)
            self._append(new_field)
        for _ in range(size, len(self._children)):
            self._children.pop()


class SecurityFields(Group):
    """
    JBP security header/subheader fields

    Args
    ----
    name: str
        Name to give this component
    x: str
        Value to replace leading "x" of Short Name in fields

    Note
    ----
    See JBP-2024.1 Table 5.10-1 and Table 5.10-2

    """

    def __init__(self, name: str, x: str):
        super().__init__(name)
        self._append(
            Field(
                f"{x}SCLAS",
                "Security Classification",
                1,
                ECSA,
                Enum(["T", "S", "C", "R", "U"]),
                StringISO8859_1,
                default="U",
            )
        )
        self._append(
            Field(
                f"{x}SCLSY",
                "Security Classification System",
                2,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SCODE",
                "Codewords",
                11,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SCTLH",
                "Control and Handling",
                2,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SREL",
                "Releasing Instructions",
                20,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SDCTP",
                "Declassification Type",
                2,
                ECSA,
                Enum(["", "DD", "DE", "GD", "GE", "O", "X"]),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SDCDT",
                "Declassification Date",
                8,
                ECSA,
                AnyOf(Constant(""), DATE_REGEX),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SDCXM",
                "Declassification Exemption",
                4,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SDG",
                "Downgrade",
                1,
                ECSA,
                Enum(["", "S", "C", "R"]),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SDGDT",
                "Downgrade Date",
                8,
                ECSA,
                AnyOf(Constant(""), DATE_REGEX),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SCLTX",
                "Classification Text",
                43,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SCATP",
                "Classification Authority Type",
                1,
                ECSA,
                Enum(["", "O", "D", "M"]),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SCAUT",
                "Classification Authority",
                40,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SCRSN",
                "Classification Reason",
                1,
                ECSA,
                AnyOf(Constant(""), Regex("[A-G]")),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SSRDT",
                "Security Source Date",
                8,
                ECSA,
                AnyOf(Constant(""), DATE_REGEX),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                f"{x}SCTLN",
                "Security Control Number",
                15,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )


class FileHeader(Group):
    """
    JBP File Header

    Args
    ----
    name: str
        Name to give the object
    numi_callback: callable
        Function to call when NUMI changes
    lin_callback: callable
        Function to call when LIn changes
    nums_callback: callable
        Function to call when NUMS changes
    lsn_callback: callable
        Function to call when LSn changes
    numt_callback: callable
        Function to call when NUMT changes
    ltn_callback: callable
        Function to call when LTn changes
    numdes_callback: callable
        Function to call when NUMDES changes
    ldn_callback: callable
        Function to call when LDn changes
    numres_callback: callable
        Function to call when NUMRES changes
    lreshn_callback: callable
        Function to call when LRESHn changes
    lren_callback: callable
        Function to call when LREn changes

    Note
    ----
    See JBP-2024.1 Table 5.11-1

    """

    def __init__(
        self,
        name: str,
        numi_callback: Callable | None = None,
        lin_callback: Callable | None = None,
        nums_callback: Callable | None = None,
        lsn_callback: Callable | None = None,
        numt_callback: Callable | None = None,
        ltn_callback: Callable | None = None,
        numdes_callback: Callable | None = None,
        ldn_callback: Callable | None = None,
        numres_callback: Callable | None = None,
        lreshn_callback: Callable | None = None,
        lren_callback: Callable | None = None,
    ):
        super().__init__(name)
        self.numi_callback = numi_callback
        self.lin_callback = lin_callback
        self.nums_callback = nums_callback
        self.lsn_callback = lsn_callback
        self.numt_callback = numt_callback
        self.ltn_callback = ltn_callback
        self.numdes_callback = numdes_callback
        self.ldn_callback = ldn_callback
        self.numres_callback = numres_callback
        self.lreshn_callback = lreshn_callback
        self.lren_callback = lren_callback

        # Initialize list with required fields
        self._append(
            Field(
                "FHDR",
                "File Profile Name",
                4,
                BCSA,
                Enum(["NITF", "NSIF"]),
                StringAscii,
                default="NITF",
            )
        )
        self._append(
            Field(
                "FVER",
                "File Version",
                5,
                BCSA,
                Enum(["02.10", "01.01"]),
                StringAscii,
                default="02.10",
            )
        )
        self._append(
            Field(
                "CLEVEL",
                "Complexity Level",
                2,
                BCSN_PI,
                MinMax(1, 99),
                Integer,
                default=99,
            )
        )
        self._append(
            Field(
                "STYPE",
                "Standard Type",
                4,
                BCSA,
                Constant("BF01"),
                StringAscii,
                default="BF01",
            )
        )
        self._append(
            Field(
                "OSTAID",
                "Originating Station ID",
                10,
                BCSA,
                Not(Constant("")),
                StringAscii,
                default="unknown",
            )
        )
        self._append(
            Field(
                "FDT",
                "File Date and Time",
                14,
                BCSN_I,
                DATETIME_REGEX,
                StringAscii,
                default="-" * 14,
            )
        )
        self._append(
            Field(
                "FTITLE",
                "File Title",
                80,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._extend(SecurityFields("File Header Security Fields", "F").values())
        self._append(
            Field(
                "FSCOP", "File Copy Number", 5, BCSN_PI, AnyRange(), Integer, default=0
            )
        )
        self._append(
            Field(
                "FSCPYS",
                "File Number of Copies",
                5,
                BCSN_PI,
                AnyRange(),
                Integer,
                default=0,
            )
        )
        self._append(
            Field("ENCRYP", "Encryption", 1, BCSN_PI, Constant(0), Integer, default=0)
        )
        self._append(
            Field(
                "FBKGC",
                "File Background Color",
                3,
                None,
                AnyRange(),
                RGB,
                default=(0, 0, 0),
            )
        )
        self._append(
            Field(
                "ONAME",
                "Originator's Name",
                24,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                "OPHONE",
                "Originator's Phone Number",
                18,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                "FL",
                "File Length",
                12,
                BCSN_PI,
                MinMax(388, 999_999_999_998),
                Integer,
                default=388,
            )
        )
        self._append(
            Field(
                "HL",
                "JBP File Header Length",
                6,
                BCSN_PI,
                MinMax(388, 999_999),
                Integer,
                default=388,
            )
        )
        self._append(
            Field(
                "NUMI",
                "Number of Image Segments",
                3,
                BCSN_PI,
                AnyRange(),
                Integer,
                default=0,
                setter_callback=self._numi_handler,
            )
        )
        self._append(
            Field(
                "NUMS",
                "Number of Graphic Segments",
                3,
                BCSN_PI,
                AnyRange(),
                Integer,
                default=0,
                setter_callback=self._nums_handler,
            )
        )
        self._append(
            Field(
                "NUMX",
                "Reserved for Future Use",
                3,
                BCSN_PI,
                Constant(0),
                Integer,
                default=0,
            )
        )
        self._append(
            Field(
                "NUMT",
                "Number of Text Segments",
                3,
                BCSN_PI,
                AnyRange(),
                Integer,
                default=0,
                setter_callback=self._numt_handler,
            )
        )
        self._append(
            Field(
                "NUMDES",
                "Number of Data Extension Segments",
                3,
                BCSN_PI,
                AnyRange(),
                Integer,
                default=0,
                setter_callback=self._numdes_handler,
            )
        )
        self._append(
            Field(
                "NUMRES",
                "Number of Reserved Extension Segments",
                3,
                BCSN_PI,
                AnyRange(),
                Integer,
                default=0,
                setter_callback=self._numres_handler,
            )
        )
        self._append(
            Field(
                "UDHDL",
                "User Defined Header Data Length",
                5,
                BCSN_PI,
                AnyOf(Constant(0), MinMax(3, 10**5 - 1)),
                Integer,
                default=0,
                setter_callback=self._udhdl_handler,
            )
        )
        self._append(
            Field(
                "XHDL",
                "Extended Header Data Length",
                5,
                BCSN_PI,
                AnyOf(Constant(0), MinMax(3, 10**5 - 1)),
                Integer,
                default=0,
                setter_callback=self._xhdl_handler,
            )
        )

    def _numi_handler(self, field: Field) -> None:
        """Handle NUMI value change"""
        self._remove_all("LISH\\d+")
        self._remove_all("LI\\d+")
        after: JbpIOComponent = field
        for idx in range(1, field.value + 1):
            after = self._insert_after(
                after,
                Field(
                    f"LISH{idx:03}",
                    "Length of nth Image Subheader",
                    6,
                    BCSN_PI,
                    MinMax(439, 999_999),
                    Integer,
                    default=439,
                ),
            )
            after = self._insert_after(
                after,
                Field(
                    f"LI{idx:03}",
                    "Length of nth Image Segment",
                    10,
                    BCSN_PI,
                    MinMax(1, 10**10 - 1),
                    Integer,
                    setter_callback=self._lin_handler,
                    default=1,
                ),
            )
        if self.numi_callback:
            self.numi_callback(field)

    def _lin_handler(self, field: Field) -> None:
        """Handle LIN value change"""
        if self.lin_callback:
            self.lin_callback(field)

    def _nums_handler(self, field: Field) -> None:
        self._remove_all("LSSH\\d+")
        self._remove_all("LS\\d+")
        after: JbpIOComponent = field
        for idx in range(1, field.value + 1):
            after = self._insert_after(
                after,
                Field(
                    f"LSSH{idx:03}",
                    "Length of nth Graphic Subheader",
                    4,
                    BCSN_PI,
                    MinMax(258, 999_999),
                    Integer,
                    default=258,
                ),
            )
            after = self._insert_after(
                after,
                Field(
                    f"LS{idx:03}",
                    "Length of nth Graphic Segment",
                    6,
                    BCSN_PI,
                    MinMax(1, 10**10 - 1),
                    Integer,
                    setter_callback=self._lsn_handler,
                    default=1,
                ),
            )

        if self.nums_callback:
            self.nums_callback(field)

    def _lsn_handler(self, field: Field) -> None:
        if self.lsn_callback:
            self.lsn_callback(field)

    def _numt_handler(self, field: Field) -> None:
        self._remove_all("LTSH\\d+")
        self._remove_all("LT\\d+")
        after: JbpIOComponent = field
        for idx in range(1, field.value + 1):
            after = self._insert_after(
                after,
                Field(
                    f"LTSH{idx:03}",
                    "Length of nth Text Subheader",
                    4,
                    BCSN_PI,
                    MinMax(282, 999_999),
                    Integer,
                    default=282,
                ),
            )
            after = self._insert_after(
                after,
                Field(
                    f"LT{idx:03}",
                    "Length of nth Text Segment",
                    5,
                    BCSN_PI,
                    MinMax(1, 99_999),
                    Integer,
                    setter_callback=self._ltn_handler,
                    default=1,
                ),
            )

        if self.numt_callback:
            self.numt_callback(field)

    def _ltn_handler(self, field: Field) -> None:
        if self.ltn_callback:
            self.ltn_callback(field)

    def _numdes_handler(self, field: Field) -> None:
        self._remove_all("LDSH\\d+")
        self._remove_all("LD\\d+")
        after: JbpIOComponent = field
        for idx in range(1, field.value + 1):
            after = self._insert_after(
                after,
                Field(
                    f"LDSH{idx:03}",
                    "Length of nth Data Extension Segment Subheader",
                    4,
                    BCSN_PI,
                    MinMax(200, 999_999),
                    Integer,
                    default=200,
                ),
            )
            after = self._insert_after(
                after,
                Field(
                    f"LD{idx:03}",
                    "Length of nth Data Extension Segment",
                    9,
                    BCSN_PI,
                    MinMax(1, 10**9 - 1),
                    Integer,
                    setter_callback=self._ldn_handler,
                    default=1,
                ),
            )

        if self.numdes_callback:
            self.numdes_callback(field)

    def _ldn_handler(self, field: Field) -> None:
        if self.ldn_callback:
            self.ldn_callback(field)

    def _numres_handler(self, field: Field) -> None:
        self._remove_all("LRESH\\d+")
        self._remove_all("LRE\\d+")
        after: JbpIOComponent = field
        for idx in range(1, field.value + 1):
            after = self._insert_after(
                after,
                Field(
                    f"LRESH{idx:03}",
                    "Length of nth Reserved Extension Segment Subheader",
                    4,
                    BCSN_PI,
                    MinMax(200, 999_999),
                    Integer,
                    default=200,
                    setter_callback=self._lreshn_handler,
                ),
            )
            after = self._insert_after(
                after,
                Field(
                    f"LRE{idx:03}",
                    "Length of nth Reserved Extension Segment",
                    7,
                    BCSN_PI,
                    MinMax(1, 10**7 - 1),
                    Integer,
                    default=1,
                    setter_callback=self._lren_handler,
                ),
            )

        if self.numres_callback:
            self.numres_callback(field)

    def _lreshn_handler(self, field: Field) -> None:
        if self.lreshn_callback:
            self.lreshn_callback(field)

    def _lren_handler(self, field: Field) -> None:
        if self.lren_callback:
            self.lren_callback(field)

    def _udhdl_handler(self, field: Field) -> None:
        self._remove_all("UDHOFL")
        self._remove_all("UDHD")
        after: JbpIOComponent = field
        if field.value:
            after = self._insert_after(
                after,
                Field(
                    "UDHOFL",
                    "User Defined Header Overflow",
                    3,
                    BCSN_PI,
                    AnyRange(),
                    Integer,
                    default=0,
                ),
            )
        if field.value > 3:
            after = self._insert_after(after, TreSequence("UDHD", field.value - 3))

    def _xhdl_handler(self, field: Field) -> None:
        self._remove_all("XHDLOFL")
        self._remove_all("XHD")
        after: JbpIOComponent = field
        if field.value:
            after = self._insert_after(
                after,
                Field(
                    "XHDLOFL",
                    "Extended Header Data Overflow",
                    3,
                    BCSN_PI,
                    AnyRange(),
                    Integer,
                    default=0,
                ),
            )
        if field.value > 3:
            after = self._insert_after(after, TreSequence("XHD", field.value - 3))

    def finalize(self) -> None:
        super().finalize()
        _update_tre_lengths(self, "UDHDL", "UDHOFL", "UDHD")
        _update_tre_lengths(self, "XHDL", "XHDLOFL", "XHD")
        # Other length fields are handled by the parent Jbp class


class ImageSubheader(Group):
    """
    Image Subheader fields

    Args
    ----
    name: str
        Name to give this component

    Note
    ----
    See JBP-2024.1 Table 5.13-1

    """

    def __init__(self, name: str):
        super().__init__(name)

        self._append(
            Field(
                "IM",
                "File Part Type",
                2,
                BCSA,
                Constant("IM"),
                StringAscii,
                default="IM",
            )
        )
        self._append(
            Field(
                "IID1",
                "Image Identifier 1",
                10,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            )
        )
        self._append(
            Field(
                "IDATIM",
                "Image Date and Time",
                14,
                BCSN,
                DATETIME_REGEX,
                StringAscii,
                default="-" * 14,
            )
        )
        self._append(
            Field(
                "TGTID",
                "Target Identifier",
                17,
                BCSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                "IID2",
                "Image Identifier 2",
                80,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._extend(SecurityFields("Security Fields Image", "I").values())
        self._append(
            Field("ENCRYP", "Encryption", 1, BCSN_PI, Constant(0), Integer, default=0)
        )
        self._append(
            Field(
                "ISORCE",
                "Image Source",
                42,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._append(
            Field(
                "NROWS",
                "Number of Significant Rows in Image",
                8,
                BCSN_PI,
                MinMax(1, None),
                Integer,
                default=1,
            )
        )
        self._append(
            Field(
                "NCOLS",
                "Number of Significant Columns in Image",
                8,
                BCSN_PI,
                MinMax(1, None),
                Integer,
                default=1,
            )
        )
        self._append(
            Field(
                "PVTYPE",
                "Pixel Value Type",
                3,
                BCSA,
                Enum(["INT", "B", "SI", "R", "C"]),
                StringAscii,
                default="INT",
            )
        )
        self._append(
            Field(
                "IREP",
                "Image Representation",
                8,
                BCSA,
                Enum(
                    [
                        "MONO",
                        "RGB",
                        "RGB/LUT",
                        "MULTI",
                        "NODISPLY",
                        "NVECTOR",
                        "POLAR",
                        "VPH",
                        "YCbCr601",
                    ]
                ),
                StringAscii,
                default="MONO",
            )
        )
        self._append(
            Field(
                "ICAT",
                "Image Category",
                8,
                BCSA,
                AnyRange(),
                StringAscii,
                default="VIS",
            )
        )
        self._append(
            Field(
                "ABPP",
                "Actual Bits-Per-Pixel Per Band",
                2,
                BCSN_PI,
                MinMax(1, 96),
                Integer,
                default=1,
            )
        )
        self._append(
            Field(
                "PJUST",
                "Pixel Justification",
                1,
                BCSA,
                Enum(["L", "R"]),
                StringAscii,
                default="R",
            )
        )
        self._append(
            Field(
                "ICORDS",
                "Image Coordinate Representation",
                1,
                BCSA,
                Enum(["", "U", "G", "N", "S", "D"]),
                StringAscii,
                default="",
                setter_callback=self._icords_handler,
            )
        )
        # IGEOLO
        self._append(
            Field(
                "NICOM",
                "Number of Image Comments",
                1,
                BCSN_PI,
                AnyRange(),
                Integer,
                default=0,
                setter_callback=self._nicom_handler,
            )
        )
        # ICOMn
        self._append(
            Field(
                "IC",
                "Image Compression",
                2,
                BCSA,
                Enum(
                    [
                        "NC",
                        "NM",
                        "C1",
                        "C3",
                        "C4",
                        "C5",
                        "C6",
                        "C7",
                        "C8",
                        "I1",
                        "M1",
                        "M3",
                        "M4",
                        "M5",
                        "M6",
                        "M7",
                        "M8",
                    ]
                ),
                StringAscii,
                setter_callback=self._ic_handler,
                default="NC",
            )
        )
        # COMRAT
        self._append(
            Field(
                "NBANDS",
                "Number of Bands",
                1,
                BCSN_PI,
                AnyRange(),
                Integer,
                setter_callback=self._nbands_handler,
                default=1,
            )
        )
        # XBANDS
        # IREPBANDn
        # ISUBCATn
        # IFCn
        # IMFLTn
        # NLUTSn
        # NELUTn
        # LUTDn
        self._append(
            Field(
                "ISYNC", "Image Sync Code", 1, BCSN_PI, Constant(0), Integer, default=0
            )
        )
        self._append(
            Field(
                "IMODE",
                "Image Mode",
                1,
                BCSA,
                Enum(["B", "P", "R", "S"]),
                StringAscii,
                default="B",
            )
        )
        self._append(
            Field(
                "NBPR",
                "Number of Blocks Per Row",
                4,
                BCSN_PI,
                MinMax(1, None),
                Integer,
                default=1,
            )
        )
        self._append(
            Field(
                "NBPC",
                "Number of Blocks Per Column",
                4,
                BCSN_PI,
                MinMax(1, None),
                Integer,
                default=1,
            )
        )
        self._append(
            Field(
                "NPPBH",
                "Number of Pixels Per Block Horizontal",
                4,
                BCSN_PI,
                MinMax(0, 8192),
                Integer,
                default=0,
            )
        )
        self._append(
            Field(
                "NPPBV",
                "Number of Pixels Per Block Vertical",
                4,
                BCSN_PI,
                MinMax(0, 8192),
                Integer,
                default=0,
            )
        )
        self._append(
            Field(
                "NBPP",
                "Number of Bits Per Pixel Per Band",
                2,
                BCSN_PI,
                MinMax(1, 96),
                Integer,
                default=1,
            )
        )
        self._append(
            Field(
                "IDLVL",
                "Image Display Level",
                3,
                BCSN_PI,
                MinMax(1, None),
                Integer,
                default=1,
            )
        )
        self._append(
            Field(
                "IALVL",
                "Attachment Level",
                3,
                BCSN_PI,
                MinMax(0, 998),
                Integer,
                default=0,
            )
        )
        self._append(
            Field(
                "ILOC",
                "Image Location",
                10,
                BCSN,
                AnyRange(),
                int_pair(5),
                default=(0, 0),
            )
        )
        self._append(
            Field(
                "IMAG",
                "Image Magnification",
                4,
                BCSA,
                Regex(r"(\d+\.?\d*)|(\d*\.?\d+)|(\/\d+)"),
                StringAscii,
                default="1.0 ",
            )
        )
        self._append(
            Field(
                "UDIDL",
                "User Defined Image Data Length",
                5,
                BCSN_PI,
                AnyOf(Constant(0), MinMax(3, None)),
                Integer,
                default=0,
                setter_callback=self._udidl_handler,
            )
        )
        self._append(
            Field(
                "IXSHDL",
                "Image Extended Subheader Data Length",
                5,
                BCSN_PI,
                AnyOf(Constant(0), MinMax(3, None)),
                Integer,
                default=0,
                setter_callback=self._ixshdl_handler,
            )
        )

    def _icords_handler(self, field: Field) -> None:
        self._remove_all("IGEOLO")
        if field.value:
            self._insert_after(
                field,
                Field(
                    "IGEOLO",
                    "Image Geographic Location",
                    60,
                    BCSA,
                    AnyRange(),
                    StringAscii,
                    default="",
                ),
            )

    def _nicom_handler(self, field: Field) -> None:
        self._remove_all("ICOM\\d+")
        after = self["NICOM"]
        for idx in range(1, field.value + 1):
            after = self._insert_after(
                after,
                Field(
                    f"ICOM{idx}",
                    "Image Comment {n}",
                    80,
                    ECSA,
                    AnyRange(),
                    StringISO8859_1,
                    default="",
                ),
            )

    def _ic_handler(self, field: Field) -> None:
        self._remove_all("COMRAT")
        if field.value not in ("NC", "NM"):
            self._insert_after(
                self["IC"],
                Field(
                    "COMRAT",
                    "Compression Rate Code",
                    4,
                    BCSA,
                    AnyRange(),
                    StringAscii,
                    default="",
                ),
            )

    def _nbands_handler(self, field: Field) -> None:
        self._remove_all("XBANDS")
        if field.value == 0:
            self._insert_after(
                self["NBANDS"],
                Field(
                    "XBANDS",
                    "Number of Multispectral Bands",
                    5,
                    BCSN_PI,
                    MinMax(10, None),
                    Integer,
                    default=10,
                    setter_callback=self._xbands_handler,
                ),
            )
        self._set_num_band_groups(field.value)

    def _xbands_handler(self, field: Field) -> None:
        self._set_num_band_groups(field.value)

    def _set_num_band_groups(self, count: int) -> None:
        self._remove_all("IREPBAND\\d+")
        self._remove_all("ISUBCAT\\d+")
        self._remove_all("IFC\\d+")
        self._remove_all("IMFLT\\d+")
        self._remove_all("NLUTS\\d+")
        self._remove_all("NELUT\\d+")
        self._remove_all("LUTD\\d+")

        after = self.get("XBANDS", self["NBANDS"])
        for idx in range(1, count + 1):
            after = self._insert_after(
                after,
                Field(
                    f"IREPBAND{idx:05d}",
                    "nth Band Representation",
                    2,
                    BCSA,
                    AnyRange(),
                    StringAscii,
                    default="",
                ),
            )
            after = self._insert_after(
                after,
                Field(
                    f"ISUBCAT{idx:05d}",
                    "nth Band Subcategory",
                    6,
                    BCSA,
                    AnyRange(),
                    StringAscii,
                    default="",
                ),
            )
            after = self._insert_after(
                after,
                Field(
                    f"IFC{idx:05d}",
                    "nth Band Image Filter Condition",
                    1,
                    BCSA,
                    AnyRange(),
                    StringAscii,
                    default="N",
                ),
            )
            after = self._insert_after(
                after,
                Field(
                    f"IMFLT{idx:05d}",
                    "nth Band Standard Image Filter Code",
                    3,
                    BCSA,
                    AnyRange(),
                    StringAscii,
                    default="",
                ),
            )
            after = self._insert_after(
                after,
                Field(
                    f"NLUTS{idx:05d}",
                    "Number of LUTS for the nth Image Band",
                    1,
                    BCSN_PI,
                    MinMax(0, 4),
                    Integer,
                    default=0,
                    setter_callback=self._nluts_handler,
                ),
            )

    def _udidl_handler(self, field: Field) -> None:
        self._remove_all("UDOFL")
        self._remove_all("UDID")
        if field.value > 0:
            after = self._insert_after(
                field,
                Field(
                    "UDOFL",
                    "User Defined Overflow",
                    3,
                    BCSN_PI,
                    AnyRange(),
                    Integer,
                    default=0,
                ),
            )
        if field.value > 3:
            after = self._insert_after(after, TreSequence("UDID", field.value - 3))

    def _ixshdl_handler(self, field: Field) -> None:
        self._remove_all("IXSOFL")
        self._remove_all("IXSHD")
        if field.value > 0:
            after = self._insert_after(
                field,
                Field(
                    "IXSOFL",
                    "Image Extended Subheader Overflow",
                    3,
                    BCSN_PI,
                    AnyRange(),
                    Integer,
                    default=0,
                ),
            )
        if field.value > 3:
            after = self._insert_after(after, TreSequence("IXSHD", field.value - 3))

    def _nluts_handler(self, field: Field) -> None:
        idx = int(field.name.removeprefix("NLUTS"))
        self._remove_all(f"NELUT{idx:05d}\\d+")
        self._remove_all(f"LUTD{idx:05d}\\d+")
        if field.value > 0:
            after = self._insert_after(
                field,
                Field(
                    f"NELUT{idx:05d}",
                    "Number of LUT Entries for the nth Image Band",
                    5,
                    BCSN_PI,
                    MinMax(1, 65536),
                    Integer,
                    default=1,
                    setter_callback=self._nelut_handler,
                ),
            )
            for lutidx in range(1, field.value + 1):
                after = self._insert_after(
                    after,
                    Field(
                        f"LUTD{idx:05d}{lutidx}",
                        "nth Image Band, mth LUT",
                        1,
                        None,
                        AnyRange(),
                        Bytes,
                        default=b"",
                    ),
                )

    def _nelut_handler(self, field: Field) -> None:
        idx = int(field.name.removeprefix("NELUT"))
        for lutd in self.find_all(f"LUTD{idx:05d}\\d+"):
            assert isinstance(lutd, Field)
            lutd.size = field.value

    def finalize(self) -> None:
        super().finalize()
        _update_tre_lengths(self, "UDIDL", "UDOFL", "UDID")
        _update_tre_lengths(self, "IXSHDL", "IXSOFL", "IXSHD")


class ImageSegment(Group):
    def __init__(self, name: str, data_size: int):
        super().__init__(name)
        self._append(ImageSubheader("subheader"))
        self._append(BinaryPlaceholder("Data", data_size))

    def print(self) -> None:
        print(f"# ImageSegment {self.name}")
        super().print()


class GraphicSubheader(Group):
    """
    Graphic Subheader fields

    Args
    ----
    name: str
        Name to give this component

    Note
    ----
    See JBP-2024.1 Table 5.15-1

    """

    def __init__(self, name: str):
        super().__init__(name)

        self._append(
            Field(
                "SY",
                "File Part Type",
                2,
                BCSA,
                Constant("SY"),
                StringAscii,
                default="SY",
            )
        )
        self._append(
            Field(
                "SID",
                "Graphic Identifier",
                10,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            )
        )
        self._append(
            Field(
                "SNAME",
                "Graphic Name",
                20,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._extend(SecurityFields("Security Fields Graphic", "S").values())
        self._append(
            Field("ENCRYP", "Encryption", 1, BCSN_PI, Constant(0), Integer, default=0)
        )
        self._append(
            Field(
                "SFMT",
                "Graphic Type",
                1,
                BCSA,
                Constant("C"),
                StringAscii,
                default="C",
            )
        )
        self._append(
            Field(
                "SSTRUCT",
                "Reserved for Future Use",
                13,
                BCSN_PI,
                Constant(0),
                Integer,
                default=0,
            )
        )
        self._append(
            Field(
                "SDLVL",
                "Graphic Display Level",
                3,
                BCSN_PI,
                MinMax(1, None),
                Integer,
                default=1,
            )
        )
        self._append(
            Field(
                "SALVL",
                "Graphic Attachment Level",
                3,
                BCSN_PI,
                MinMax(0, 998),
                Integer,
                default=0,
            )
        )
        self._append(
            Field(
                "SLOC",
                "Graphic Location",
                10,
                BCSN,
                AnyRange(),
                int_pair(5),
                default=(0, 0),
            )
        )
        self._append(
            Field(
                "SBND1",
                "First Graphic Bound Location",
                10,
                BCSN,
                AnyRange(),
                int_pair(5),
                default=(0, 0),
            )
        )
        self._append(
            Field(
                "SCOLOR",
                "Graphic Color",
                1,
                BCSA,
                Enum(["C", "M"]),
                StringAscii,
                default="",  # should this have a default?
            )
        )
        self._append(
            Field(
                "SBND2",
                "Second Graphic Bound Location",
                10,
                BCSN,
                AnyRange(),
                int_pair(5),
                default=(0, 0),
            )
        )
        self._append(
            Field(
                "SRES2",
                "Reserved for Future Use",
                2,
                BCSN_PI,
                Constant(0),
                Integer,
                default=0,
            )
        )
        self._append(
            Field(
                "SXSHDL",
                "Graphic Extended Subheader Data Length",
                5,
                BCSN_PI,
                AnyOf(
                    Constant(0),
                    MinMax(3, 9741),
                ),
                Integer,
                default=0,
                setter_callback=self._sxshdl_handler,
            )
        )

    def _sxshdl_handler(self, field: Field) -> None:
        self._remove_all("SXSOFL")
        self._remove_all("SXSHD")
        if field.value > 0:
            after = self._insert_after(
                field,
                Field(
                    "SXSOFL",
                    "Graphic Extended Subheader Overflow",
                    3,
                    BCSN_PI,
                    AnyRange(),
                    Integer,
                    default=0,
                ),
            )
        if field.value > 3:
            after = self._insert_after(after, TreSequence("SXSHD", field.value - 3))

    def finalize(self) -> None:
        super().finalize()
        _update_tre_lengths(self, "SXSHDL", "SXSOFL", "SXSHD")


class GraphicSegment(Group):
    def __init__(self, name: str, data_size: int):
        super().__init__(name)
        self._append(GraphicSubheader("subheader"))
        self._append(BinaryPlaceholder("Data", data_size))

    def print(self) -> None:
        print(f"# GraphicSegment {self.name}")
        super().print()


class TextSubheader(Group):
    """
    Text Subheader fields

    Args
    ----
    name: str
        Name to give this component

    Note
    ----
    See JBP-2024.1 Table 5.17-1

    """

    def __init__(self, name: str):
        super().__init__(name)

        self._append(
            Field(
                "TE",
                "File Part Type",
                2,
                BCSA,
                Constant("TE"),
                StringAscii,
                default="TE",
            )
        )
        self._append(
            Field(
                "TEXTID",
                "Text Identifier",
                7,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            )
        )
        self._append(
            Field(
                "TXTALVL",
                "Text Attachment Level",
                3,
                BCSN_PI,
                MinMax(0, 998),
                Integer,
                default=0,
            )
        )
        self._append(
            Field(
                "TXTDT",
                "Text Date and Time",
                14,
                BCSN,
                DATETIME_REGEX,
                StringAscii,
                default="-" * 14,
            )
        )
        self._append(
            Field(
                "TXTITL",
                "Text Title",
                80,
                ECSA,
                AnyRange(),
                StringISO8859_1,
                default="",
            )
        )
        self._extend(SecurityFields("Security Fields Text", "T").values())
        self._append(
            Field("ENCRYP", "Encryption", 1, BCSN_PI, Constant(0), Integer, default=0)
        )
        self._append(
            Field(
                "TXTFMT",
                "Text Format",
                3,
                BCSA,
                Enum(["MTF", "STA", "UTI", "U8S"]),
                StringAscii,
                default="",
            )
        )
        self._append(
            Field(
                "TXSHDL",
                "Text Extended Subheader Data Length",
                5,
                BCSN_PI,
                AnyOf(
                    Constant(0),
                    MinMax(3, 9717),
                ),
                Integer,
                default=0,
                setter_callback=self._txshdl_handler,
            )
        )

    def _txshdl_handler(self, field: Field) -> None:
        self._remove_all("TXSOFL")
        self._remove_all("TXSHD")
        if field.value > 0:
            after = self._insert_after(
                field,
                Field(
                    "TXSOFL",
                    "Text Extended Subheader Overflow",
                    3,
                    BCSN_PI,
                    AnyRange(),
                    Integer,
                    default=0,
                ),
            )
        if field.value > 3:
            after = self._insert_after(after, TreSequence("TXSHD", field.value - 3))

    def finalize(self) -> None:
        super().finalize()
        _update_tre_lengths(self, "TXSHDL", "TXSOFL", "TXSHD")


class TextSegment(Group):
    def __init__(self, name: str, data_size: int):
        super().__init__(name)
        self._append(TextSubheader("subheader"))
        self._append(BinaryPlaceholder("Data", data_size))

    def print(self) -> None:
        print(f"# TextSegment {self.name}")
        super().print()


class ReservedExtensionSegment(Group):
    def __init__(self, name: str, subheader_size: int, data_size: int):
        super().__init__(name)
        self._append(
            Field(
                "subheader",
                "Placeholder",
                subheader_size,
                None,
                AnyRange(),
                Bytes,
                default=b"",
            )
        )
        self._append(BinaryPlaceholder("RESDATA", data_size))

    def print(self) -> None:
        print(f"# ReservedExtensionSegment {self.name}")
        super().print()


class DataExtensionSubheader(Group):
    def __init__(self, name: str):
        super().__init__(name)
        self._append(
            Field(
                "DE",
                "File Part Type",
                2,
                BCSA,
                Constant("DE"),
                StringAscii,
                default="DE",
            )
        )
        self._append(
            Field(
                "DESID",
                "Unique DES Type Identifier",
                25,
                BCSA,
                AnyRange(),
                StringAscii,
                setter_callback=self._desid_handler,
                default="",
            )
        )
        self._append(
            Field(
                "DESVER",
                "Version of the Data Definition",
                2,
                BCSN_PI,
                MinMax(1, None),
                Integer,
                default=1,
            )
        )
        self._extend(SecurityFields("Security Fields DES", "DE").values())
        # DESOFLW
        # DESITEM
        self._append(
            Field(
                "DESSHL",
                "DES User-defined Subheader Length",
                4,
                BCSN_PI,
                AnyRange(),
                Integer,
                setter_callback=self._desshl_handler,
                default=0,
            )
        )
        # DESSHF

    def _desid_handler(self, field: Field) -> None:
        self._remove_all("DESOFLW")
        self._remove_all("DESITEM")
        if field.value == "TRE_OVERFLOW":
            after = self._insert_after(
                self["DESCTLN"],
                Field(
                    "DESOFLW",
                    "DES Overflowed Header Type",
                    6,
                    BCSA,
                    Enum(["XHD", "IXSHD", "SXSHD", "TXSHD", "UDHD", "UDID"]),
                    StringAscii,
                    default="",
                ),
            )
            self._insert_after(
                after,
                Field(
                    "DESITEM",
                    "DES Data Item Overflowed",
                    3,
                    BCSN_PI,
                    AnyRange(),
                    Integer,
                    default=0,
                ),
            )

    def _desshl_handler(self, field: Field) -> None:
        self._remove_all("DESSHF")
        if field.value > 0:
            self._insert_after(
                field, DESSHF_Factory(self["DESID"], self["DESVER"], field)
            )


class DataExtensionSegment(Group):
    def __init__(self, name: str, data_size: int):
        super().__init__(name)
        self._append(DataExtensionSubheader("subheader"))
        self._append(BinaryPlaceholder("DESDATA", data_size))

    def print(self) -> None:
        print(f"# DESegment {self.name}")
        super().print()


class XmlDataContentSubheader(Group):
    def __init__(self, name: str, size: int):
        super().__init__(name)
        self.all_fields = [
            Field(
                "DESCRC",
                "Cyclic Redundancy Check",
                5,
                BCSN_PI,
                AnyOf(MinMax(0, 65535), Constant(99999)),
                Integer,
                default=0,
            ),
            Field(
                "DESSHFT", "XML File Type", 8, BCSA, AnyRange(), StringAscii, default=""
            ),
            Field(
                "DESSHDT",
                "Date and Time",
                20,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            ),
            Field(
                "DESSHRP",
                "Responsible Party",
                40,
                U8,
                AnyRange(),
                StringUtf8,
                default="",
            ),
            Field(
                "DESSHSI",
                "Specification Identifier",
                60,
                U8,
                AnyRange(),
                StringUtf8,
                default="",
            ),
            Field(
                "DESSHSV",
                "Specification Version",
                10,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            ),
            Field(
                "DESSHSD",
                "Specification Date",
                20,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            ),
            Field(
                "DESSHTN",
                "Target Namespace",
                120,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            ),
            Field(
                "DESSHLPG",
                "Location - Polygon",
                125,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            ),
            Field(
                "DESSHLPT",
                "Location - Point",
                25,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            ),
            Field(
                "DESSHLI",
                "Location - Identifier",
                20,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            ),
            Field(
                "DESSHLIN",
                "Location Identifier Namespace URI",
                120,
                BCSA,
                AnyRange(),
                StringAscii,
                default="",
            ),
            Field("DESSHABS", "Abstract", 200, U8, AnyRange(), StringUtf8, default=""),
        ]
        allowed_sizes = {0, 5, 283, 773}
        if size not in allowed_sizes:
            logger.warning(
                f"Invalid user defined subheader length. {size} not in {allowed_sizes}"
            )

        current_size = 0
        for field in self.all_fields:
            if current_size == size:
                break
            elif current_size < size:
                self._append(field)
                current_size += field.size
            elif current_size > size:
                raise ValueError(f"Invalid XML_DATA_CONTENT header {size=}")


def DESSHF_Factory(
    desid_field: Field, desver_field: Field, desshl_field: Field
) -> JbpIOComponent:  # noqa: N802
    """Create the DESSHF field based on the DES type

    Args
    ----
    desid_field: Field
        the DES Subheader's DESID field
    desver_field: Field
        the DES Subheader's DESVER field
    desshl_field: Field
        the DES Subheader's DESSHL field

    Returns
    -------
    JbpIOComponent
        Either a XmlDataContentSubheader or a Field
    """
    if (desid_field.value, desver_field.value) == ("XML_DATA_CONTENT", 1):
        return XmlDataContentSubheader("DESSHF", desshl_field.value)
    return Field(
        "DESSHF",
        "DES User-defined Subheader Fields",
        desshl_field.value,
        BCSA,
        AnyRange(),
        StringAscii,
        default="",
    )


def _update_tre_lengths(header, hdl, ofl, hd):
    length = 0
    if ofl in header:
        length += 3
    if hd in header:
        length += header[hd].get_size()
    header[hdl]._set_value(length)


class Jbp(Group):
    """Class representing an entire NITF/NSIF

    Contains the following keys:
    * FileHeader
    * ImageSegments
    * GraphicSegments
    * TextSegments
    * DataExtensionSegments
    * ReservedExtensionSegments

    """

    def __init__(self):
        super().__init__("Root")
        self._append(
            FileHeader(
                "FileHeader",
                numi_callback=self._numi_handler,
                lin_callback=self._lin_handler,
                nums_callback=self._nums_handler,
                lsn_callback=self._lsn_handler,
                numt_callback=self._numt_handler,
                ltn_callback=self._ltn_handler,
                numdes_callback=self._numdes_handler,
                ldn_callback=self._ldn_handler,
                numres_callback=self._numres_handler,
                lreshn_callback=self._lreshn_handler,
                lren_callback=self._lren_handler,
            )
        )
        self._append(
            SegmentList(
                "ImageSegments",
                lambda n: ImageSegment(n, None),
                maximum=999,
            )
        )
        self._append(
            SegmentList(
                "GraphicSegments",
                lambda n: GraphicSegment(n, None),
                maximum=999,
            )
        )
        self._append(
            SegmentList(
                "TextSegments",
                lambda n: TextSegment(n, None),
                maximum=999,
            )
        )
        self._append(
            SegmentList(
                "DataExtensionSegments",
                lambda n: DataExtensionSegment(n, None),
                maximum=999,
            )
        )
        self._append(
            SegmentList(
                "ReservedExtensionSegments",
                lambda n: ReservedExtensionSegment(n, None, None),
                maximum=999,
            )
        )

    def _numi_handler(self, field: Field) -> None:
        self["ImageSegments"].set_count(field.value)

    def _lin_handler(self, field: Field) -> None:
        idx = int(field.name.removeprefix("LI")) - 1
        self["ImageSegments"][idx]["Data"].size = field.value

    def _nums_handler(self, field: Field) -> None:
        self["GraphicSegments"].set_count(field.value)

    def _lsn_handler(self, field: Field) -> None:
        idx = int(field.name.removeprefix("LS")) - 1
        self["GraphicSegments"][idx]["Data"].size = field.value

    def _numt_handler(self, field: Field) -> None:
        self["TextSegments"].set_count(field.value)

    def _ltn_handler(self, field: Field) -> None:
        idx = int(field.name.removeprefix("LT")) - 1
        self["TextSegments"][idx]["Data"].size = field.value

    def _numdes_handler(self, field: Field) -> None:
        self["DataExtensionSegments"].set_count(field.value)

    def _ldn_handler(self, field: Field) -> None:
        idx = int(field.name.removeprefix("LD")) - 1
        self["DataExtensionSegments"][idx]["DESDATA"].size = field.value

    def _numres_handler(self, field: Field) -> None:
        self["ReservedExtensionSegments"].set_count(field.value)

    def _lreshn_handler(self, field: Field) -> None:
        # this callback should be removed if the Reserved Subheader is implemented
        idx = int(field.name.removeprefix("LRESH")) - 1
        self["ReservedExtensionSegments"][idx]["subheader"].size = field.value

    def _lren_handler(self, field: Field) -> None:
        idx = int(field.name.removeprefix("LRE")) - 1
        self["ReservedExtensionSegments"][idx]["RESDATA"].size = field.value

    def update_lengths(self) -> None:
        """Compute and set the segment lengths"""
        self["FileHeader"]["FL"]._set_value(self.get_size())
        self["FileHeader"]["HL"]._set_value(self["FileHeader"].get_size())

        for idx, seg in enumerate(self["ImageSegments"]):
            self["FileHeader"][f"LISH{idx + 1:03d}"]._set_value(
                seg["subheader"].get_size()
            )
            self["FileHeader"][f"LI{idx + 1:03d}"]._set_value(seg["Data"].size)

        for idx, seg in enumerate(self["GraphicSegments"]):
            self["FileHeader"][f"LSSH{idx + 1:03d}"]._set_value(
                seg["subheader"].get_size()
            )
            self["FileHeader"][f"LS{idx + 1:03d}"]._set_value(seg["Data"].size)

        for idx, seg in enumerate(self["TextSegments"]):
            self["FileHeader"][f"LTSH{idx + 1:03d}"]._set_value(
                seg["subheader"].get_size()
            )
            self["FileHeader"][f"LT{idx + 1:03d}"]._set_value(seg["Data"].size)

        for idx, seg in enumerate(self["DataExtensionSegments"]):
            self["FileHeader"][f"LDSH{idx + 1:03d}"]._set_value(
                seg["subheader"].get_size()
            )
            self["FileHeader"][f"LD{idx + 1:03d}"]._set_value(seg["DESDATA"].size)

        for idx, seg in enumerate(self["ReservedExtensionSegments"]):
            self["FileHeader"][f"LRESH{idx + 1:03d}"]._set_value(
                seg["subheader"].get_size()
            )
            self["FileHeader"][f"LRE{idx + 1:03d}"]._set_value(seg["RESDATA"].size)

    def update_fdt(self) -> None:
        """Set the FDT field to the current time"""
        now = datetime.datetime.now(datetime.timezone.utc)
        self["FileHeader"]["FDT"].value = now.strftime("%Y%m%d%H%M%S")

    def finalize(self) -> None:
        """Compute derived values such as lengths, and CLEVEL"""
        super().finalize()
        self.update_lengths()
        self.update_fdt()
        self.update_clevel()  # must be after lengths

    def _clevel_ccs_extent(self) -> int:
        min_ccs_row = min_ccs_col = 0
        max_ccs_row = max_ccs_col = 0

        level_origin = {0: {"row": 0, "col": 0}}
        for imseg in self["ImageSegments"]:
            alvl = imseg["subheader"]["IALVL"].value
            dlvl = imseg["subheader"]["IDLVL"].value
            iloc_row, iloc_col = imseg["subheader"]["ILOC"].value
            nrows = imseg["subheader"]["NROWS"].value
            ncols = imseg["subheader"]["NCOLS"].value
            level_origin[dlvl] = {
                "row": level_origin[alvl]["row"] + iloc_row,
                "col": level_origin[alvl]["col"] + iloc_col,
            }

            min_ccs_row = min(min_ccs_row, level_origin[dlvl]["row"])
            min_ccs_col = min(min_ccs_col, level_origin[dlvl]["col"])

            max_ccs_row = max(max_ccs_row, level_origin[dlvl]["row"] + nrows)
            max_ccs_col = max(max_ccs_col, level_origin[dlvl]["col"] + ncols)

        if len(self["GraphicSegments"]):
            logger.warning("CLEVEL of JBPs with Graphic Segments is not supported")

        max_extent = max(max_ccs_row - min_ccs_row, max_ccs_col - min_ccs_col)
        if max_extent <= 2047:
            return 3
        if max_extent <= 8191:
            return 5
        if max_extent <= 65535:
            return 6
        if max_extent <= 99_999_999:
            return 7
        return 9

    def _clevel_file_size(self) -> int:
        if self["FileHeader"]["FL"].value < 50 * (1 << 20):
            return 3
        if self["FileHeader"]["FL"].value < 1 * (1 << 30):
            return 5
        if self["FileHeader"]["FL"].value < 2 * (1 << 30):
            return 6
        if self["FileHeader"]["FL"].value < 10 * (1 << 30):
            return 7
        return 9

    def _clevel_image_size(self) -> int:
        clevel = 3
        for imseg in self["ImageSegments"]:
            nrows = imseg["subheader"]["NROWS"].value
            ncols = imseg["subheader"]["NCOLS"].value

            if nrows <= 2048 and ncols <= 2048:
                clevel = max(clevel, 3)
            elif nrows <= 8192 and ncols <= 8192:
                clevel = max(clevel, 5)
            elif nrows <= 65536 and ncols <= 65536:
                clevel = max(clevel, 6)
            elif nrows <= 99_999_999 and ncols <= 99_999_999:
                clevel = max(clevel, 7)
        return clevel

    def _clevel_image_blocking(self) -> int:
        clevel = 3
        for imseg in self["ImageSegments"]:
            horiz = imseg["subheader"]["NPPBH"].value
            vert = imseg["subheader"]["NPPBV"].value

            if horiz <= 2048 and vert <= 2048:
                clevel = max(clevel, 3)
            elif horiz <= 8192 and vert <= 8192:
                clevel = max(clevel, 5)
        return clevel

    def _clevel_irep(self) -> int:
        clevel = 0
        for imseg in self["ImageSegments"]:
            has_lut = bool(imseg["subheader"].find_all("NLUT.*"))
            num_bands = (
                imseg["subheader"].get("XBANDS", imseg["subheader"]["NBANDS"]).value
            )
            # Color (RGB) No Compression
            if (
                imseg["subheader"]["IREP"].value == "RGB"
                and num_bands == 3
                and not has_lut
                and imseg["subheader"]["IC"].value in ("NC", "NM")
                and imseg["subheader"]["IMODE"].value in ("B", "P", "R", "S")
            ):
                if imseg["subheader"]["NBPP"].value == 8:
                    clevel = max(clevel, 3)

                if imseg["subheader"]["NBPP"].value in (8, 16, 32):
                    clevel = max(clevel, 6)

            # Multiband (MULTI) No Compression
            if (
                imseg["subheader"]["IREP"].value == "MULTI"
                and imseg["subheader"]["NBPP"].value in (1, 8, 16, 32, 64)
                and imseg["subheader"]["IC"].value in ("NC", "NM")
                and imseg["subheader"]["IMODE"].value in ("B", "P", "R", "S")
            ):
                if 2 <= num_bands <= 9:
                    clevel = max(clevel, 3)

                if 10 <= num_bands <= 255:
                    clevel = max(clevel, 5)

                if 255 <= num_bands <= 999:
                    clevel = max(clevel, 7)

            # JPEG2000 Compression Multiband (MULTI)
            if (
                imseg["subheader"]["IREP"].value == "MULTI"
                and imseg["subheader"]["NBPP"].value <= 32
                and imseg["subheader"]["IC"].value in ("C8", "M8")
                and imseg["subheader"]["IMODE"].value == "B"
            ):
                if 1 <= num_bands <= 9:
                    clevel = max(clevel, 3)

                if 10 <= num_bands <= 255:
                    clevel = max(clevel, 5)

                if 256 <= num_bands <= 999:
                    clevel = max(clevel, 7)

            # Multiband (MULTI) Individual Band JPEG Compression
            if (
                imseg["subheader"]["IREP"].value == "MULTI"
                and imseg["subheader"]["NBPP"].value in (8, 12)
                and not has_lut
                and imseg["subheader"]["IC"].value in ("C3", "M3")
                and imseg["subheader"]["IMODE"].value in ("B", "S")
            ):
                if 2 <= num_bands <= 9:
                    clevel = max(clevel, 3)

                if 10 <= num_bands <= 255:
                    clevel = max(clevel, 5)

                if 256 <= num_bands <= 999:
                    clevel = max(clevel, 7)

            # Multiband (MULTI) Multi-Component Compression
            if (
                imseg["subheader"]["IREP"].value == "MULTI"
                and imseg["subheader"]["NBPP"].value in (8, 12)
                and not has_lut
                and imseg["subheader"]["IC"].value in ("C6", "M6")
                and imseg["subheader"]["IMODE"].value in ("B", "P", "S")
            ):
                if 2 <= num_bands <= 9:
                    clevel = max(clevel, 3)

                if 10 <= num_bands <= 255:
                    clevel = max(clevel, 5)

                if 256 <= num_bands <= 999:
                    clevel = max(clevel, 7)

            # Matrix Data (NODISPLY)
            if (
                imseg["subheader"]["IREP"].value == "NODISPLY"
                and imseg["subheader"]["NBPP"].value in (8, 16, 32, 64)
                and not has_lut
                and imseg["subheader"]["IMODE"].value in ("B", "P", "R", "S")
            ):
                if 2 <= num_bands <= 9:
                    clevel = max(clevel, 3)

                if 10 <= num_bands <= 255:
                    clevel = max(clevel, 5)

                if 256 <= num_bands <= 999:
                    clevel = max(clevel, 7)

        return clevel

    def _clevel_num_imseg(self) -> int:
        if len(self["ImageSegments"]) <= 20:
            return 3
        if 20 < len(self["ImageSegments"]) <= 100:
            return 5
        return 9

    def _clevel_aggregate_size_of_graphic_segments(self) -> int:
        size = 0
        for field in self["FileHeader"].find_all("LS\\d+"):
            size += field.value

        if size <= 1 * (1 << 20):
            return 3
        if size <= 2 * (1 << 20):
            return 5
        return 9

    def _clevel_cl9(self) -> int:
        """Explicit CLEVEL 9 checks"""
        # 1
        if self["FileHeader"]["FL"].value >= 10 * (1 << 30):
            return 9

        total_num_bands = 0
        for imseg in self["ImageSegments"]:
            # 2
            if (
                imseg["subheader"]["NPPBH"].value == 0
                or imseg["subheader"]["NPPBV"].value == 0
            ):
                return 9
            total_num_bands += imseg.get("XBANDS", imseg["subheader"]["NBANDS"]).value

        # 3
        if total_num_bands > 999:
            return 9

        # 4
        if len(self["ImageSegments"]) > 100:
            return 9

        # 5
        if len(self["GraphicSegments"]) > 100:
            return 9

        # 6
        size = 0
        for field in self["FileHeader"].find_all("LS\\d+"):
            size += field.value
        if size > 2 * (1 << 20):
            return 9

        # 7
        if len(self["TextSegments"]) > 32:
            return 9

        # 8
        if len(self["DataExtensionSegments"]) > 100:
            return 9

        return 0

    def update_clevel(self) -> None:
        """Compute and update the CLEVEL field.  See JBP-2024.1 Table G-1"""
        clevel = 3
        helpers = [attrib for attrib in dir(self) if attrib.startswith("_clevel_")]
        for helper in helpers:
            clevel = max(clevel, getattr(self, helper)())

        self["FileHeader"]["CLEVEL"].value = clevel


class TreSequence(ComponentCollection, collections.abc.MutableSequence):
    """
    TREs which appear one after the other with no intervening bytes

    Intended for use as the user defined and/or extended data fields.  See Section 5.9.3.

    Arguments
    ---------
    name: str
        Name to give the field
    length: int
        Initial length in bytes

    """

    def __init__(self, name, length):
        super().__init__(name)
        self._length = length

    def _load_impl(self, fd):
        if self._children:
            return super()._load_impl(fd)

        # else need to discover which TREs are in the file
        bytes_read = 0
        while bytes_read < self._length:
            tretag = fd.read(6).decode()
            fd.seek(-6, os.SEEK_CUR)
            tre = tre_factory(tretag)
            self._append(tre)
            tre.load(fd)
            bytes_read += tre.get_size()

        if bytes_read != self._length:
            logger.warning(
                f"Length of TREs ({bytes_read}) in {self.name} does not match expected length ({self._length})"
            )

    def __getitem__(self, key):
        return self._children[key]

    def __setitem__(self, key, value):
        value._parent = self
        self._children[key] = value

    def __delitem__(self, key):
        del self._children[key]

    def __len__(self):
        return len(self._children)

    def insert(self, index, element):
        element._parent = self
        self._children.insert(index, element)


class Tre(Group):
    """Base class for TREs

    Includes the TRETAG and TREL tags.

    Arguments
    ---------
    identifier : str
        identifier of the TRE.  Must be exactly 6 characters.
    tretag_rename : str
        Alternative to give the 'TRETAG' field
    trel_rename : str
        Alternative to give the 'TREL' field
    length_constraint : RangeCheck or None
        range check for 'TREL' field.  Defaults to MinMax(1, 99985)

    Note
    ----
    BIIF and JBP define TREs as having 3 fields, TRETAG, TREL, and. TREDATA.
    However, TREs commonly rename TRETAG and TREL and define their own fields as replacing TREDATA.
    """

    def __init__(
        self,
        identifier: str,
        tretag_rename: str = "TRETAG",
        trel_rename: str = "TREL",
        length_constraint: RangeCheck | None = None,
    ):
        if len(identifier) != 6:
            raise ValueError(
                f"TRE identifier '{identifier}' must be exactly 6 characters"
            )

        super().__init__(identifier)
        self.tretag_rename = tretag_rename
        self.trel_rename = trel_rename

        if length_constraint is None:
            length_constraint = MinMax(1, 99985)

        self._append(
            Field(
                tretag_rename,
                "Unique Extension Type Identifier",
                6,
                BCSA,
                Constant(identifier),
                StringAscii,
                default=identifier,
            )
        )

        self._append(
            Field(
                trel_rename,
                "Length of the TREDATA",
                5,
                BCSN_PI,
                length_constraint,
                Integer,
                default=0,
            )
        )

    def finalize(self) -> None:
        """Set the TREL field"""
        length = 0
        for child in self._children:
            if child.name in (self.tretag_rename, self.trel_rename):
                continue
            length += child.get_size()
        self[self.trel_rename]._set_value(length)


class UnknownTre(Tre):
    """TRE without known TREDATA definition.
    see: Table 5.9-1. Registered and Controlled Tagged Record Extension Format
    """

    def __init__(self, name):
        super().__init__(name)
        self["TREL"]._setter_callback = self._trel_handler

        self._append(
            Field(
                "TREDATA",
                "User-Defined Data",
                0,
                None,
                AnyRange(),
                Bytes,
                default=b"",
            )
        )

    def _trel_handler(self, field):
        self["TREDATA"].size = field.value


def available_tres() -> dict[str, Callable[[], Tre]]:
    """All discovered and available TREs

    Returns
    -------
    Dictionary of TRE names to classes
    """
    return {
        plugin.name: plugin.load()
        for plugin in importlib.metadata.entry_points(group="jbpy.extensions.tre")
    }


def tre_factory(tretag: str) -> Tre:
    """Create a TRE instance

    Arguments
    ---------
    tretag : str
        The 6 character name of the TRE

    Returns
    -------
    Tre
        TRE object
    """
    tres = available_tres()
    if tretag in tres:
        return tres[tretag]()

    return UnknownTre(tretag)
