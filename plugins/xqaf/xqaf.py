# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 Philipp Wolfer
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

from enum import Enum, IntFlag
import struct
try:
    import zstandard as zstd
except ImportError:
    zstd = None

from mutagen import FileType, MutagenError, StreamInfo
from mutagen._vorbis import VCommentDict
from mutagen._util import (
    delete_bytes,
    insert_bytes,
    intround,
    loadfile,
    resize_bytes,
)


_XQAF_BASE_HEADER_SIZE = 10
_XQAF_EXTENDED_HEADER_SIZE_32 = 24
_XQAF_EXTENDED_HEADER_SIZE_64 = 36
_MAX_UINT32 = 0xFFFFFFFF


class XQAFError(MutagenError):
    pass

class XQAFInvalidHeaderError(XQAFError):
    pass


class XQAFCompressionMode(Enum):
    """XQAF tag compression modes.

    NONE: Do not compress the tags.
    COMPRESS: Compress the tags using zstandard.
    KEEP: Compress the tags if the existing tags in the file are compressed,
          otherwise do not compress them.
    """
    NONE = 0
    COMPRESS = 1
    KEEP = 2


class XQAFFlags(IntFlag):
    """Flags for XQAF files.

    These flags are used in the XQAF header to indicate various properties
    of the audio file, such as compression and 64-bit fields.
    """
    GAPLESS = 1 << 0
    COMPRESSED_TAGS = 1 << 1
    IS_64BIT = 1 << 31

    @property
    def is_gapless(self):
        return XQAFFlags.GAPLESS in self

    @property
    def is_compressed(self):
        return XQAFFlags.COMPRESSED_TAGS in self

    @property
    def is_64bit(self):
        return XQAFFlags.IS_64BIT in self


class XQAFInfo(StreamInfo):
    """XQAF stream information.

    Attributes:
      channels (`int`): number of audio channels
      length (`float`): file length in seconds, as a float
      sample_rate (`int`): audio sampling rate in Hz
      bitrate (`int`): audio bitrate, in bits per second
      gapless (`bool`): indicates whether the audio is supposed to be played gaplessly
    """

    def __init__(self, fileobj):
        self._parse_header(fileobj)

    def _parse_header(self, fileobj):
        """Parse the XQAF header to extract metadata."""
        # See spec at https://chiselapp.com/user/MistressRemilia/repository/cl-remiaudio/file?name=docs/extended-qoa-format.md&ci=tip
        header = fileobj.read(_XQAF_BASE_HEADER_SIZE)
        if not header.startswith(b"XQAF") or len(header) < _XQAF_BASE_HEADER_SIZE:
            raise XQAFInvalidHeaderError("Invalid XQAF header")

        _major, _minor, flags = struct.unpack(">ccI", header[4:])
        self._flags = XQAFFlags(flags)

        header_length = _XQAF_EXTENDED_HEADER_SIZE_32
        header_format = ">3sIBIIII"
        if self._flags.is_64bit:
            # In 64 bit mode the data offsets and lengths are 64-bit,
            # with the exception of tag length which is always 32-bit.
            header_length = _XQAF_EXTENDED_HEADER_SIZE_64
            header_format = ">3sIBQQQI"

        extended_header = fileobj.read(header_length)
        if len(extended_header) != header_length:
            raise XQAFInvalidHeaderError("Insufficient data for reading XQAF header")
        (sample_rate, number_of_samples, channels, data_offset, data_length,
         tag_offset, tag_length) = struct.unpack(header_format, extended_header)

        # Validate the header data. Proceeding with invalid offsets or lengths
        # could lead to undefined behavior and potentially damage the file.
        if number_of_samples == 0:
            raise XQAFInvalidHeaderError("Sample count is zero")
        elif data_length == 0:
            raise XQAFInvalidHeaderError("QOA data size is zero")
        elif data_offset < _XQAF_BASE_HEADER_SIZE + header_length:
            raise XQAFInvalidHeaderError("Data offset is smaller than header size")
        elif tag_offset != 0 and tag_offset < _XQAF_BASE_HEADER_SIZE + header_length:
            raise XQAFInvalidHeaderError("Tag offset is smaller than header size")
        elif (data_offset <= tag_offset < data_offset + data_length
              or data_offset < tag_offset + tag_length < data_offset + data_length):
            raise XQAFInvalidHeaderError("Tag block overlaps with data block")

        self.sample_rate = int.from_bytes(sample_rate, 'big')
        self.channels = channels
        self.gapless = self._flags.is_gapless

        if self.sample_rate > 0:
            self.length = number_of_samples / float(self.sample_rate)

        if self.length > 0:
            self.bitrate = intround(data_length * 8 / self.length)

        # Store data and tag offsets for internal use
        self._data_offset = data_offset
        self._data_length = data_length
        self._tag_offset = tag_offset
        self._tag_length = tag_length

    @property
    def _has_existing_tags(self) -> bool:
        """Check if the XQAF file has tags."""
        return self._tag_offset > 0 and self._tag_length > 0

    @property
    def _header_tag_offset_position(self) -> int:
        """Get the position of the tag offset in the header."""
        if self._flags.is_64bit:
            return 34
        else:
            return 26


class XQAFVCommentDict(VCommentDict):

    @loadfile()
    def load(self, filething, errors='replace'):
        super().load(filething.fileobj, errors=errors, framing=False)

    @loadfile(writable=True)
    def save(self, filething, compression=XQAFCompressionMode.KEEP):
        """Save the Vorbis comment to a file-like object."""
        f = filething.fileobj
        info = XQAFInfo(f)

        tag_data = self.write(framing=False)
        new_size = len(tag_data)
        data_offset = info._data_offset
        tag_offset = info._tag_offset
        new_flags = info._flags

        # If compression is enabled, compress the tag data
        if compression == XQAFCompressionMode.COMPRESS or (
            compression == XQAFCompressionMode.KEEP and info._flags.is_compressed):
            if not zstd:
                raise XQAFError("Compression of XQAF tags unavailable (requires zstandard)")
            tag_data = zstd.compress(tag_data)
            new_size = len(tag_data)
            if not info._flags.is_compressed:
                new_flags |= XQAFFlags.COMPRESSED_TAGS
        elif info._flags.is_compressed:
            # Disable the compression bit if we are not compressing
            new_flags &= ~XQAFFlags.COMPRESSED_TAGS

        # If the offsets exceed 32-bit, we need to upgrade to 64-bit mode
        if not info._flags.is_64bit and (
            data_offset + new_size > _MAX_UINT32 or tag_offset + new_size > _MAX_UINT32):
            info = self._upgrade_to_64bit(f, info)
            data_offset = info._data_offset
            tag_offset = info._tag_offset
            new_flags = info._flags

        # Resize the file for the new tag size and adjust offsets accordingly
        if info._has_existing_tags:
            # Resize existing tags to new size
            resize_bytes(f, info._tag_length, new_size, info._tag_offset)
            if tag_offset < data_offset:
                # If the tag block comes before the data block, we need to adjust the data offset
                data_offset += new_size - info._tag_length
        else:
            # Add a new tag block just before the data block
            tag_offset = info._data_offset
            insert_bytes(f, new_size, tag_offset)
            # Shift the data block offset
            data_offset = info._data_offset + new_size

        # In 64-bit mode the offsets and length fields are 64-bit, with the exception
        # of the tag length which is always 32-bit.
        format = ">Q" if info._flags.is_64bit else ">I"

        # Update the data offsets and length in the file header
        self._update_flags(f, new_flags)
        f.seek(18)
        f.write(struct.pack(format, data_offset))
        f.seek(info._header_tag_offset_position)  # Skip the data length, it hasn't changed
        f.write(struct.pack(format, tag_offset))
        f.write(struct.pack(">I", new_size))

        # Write the Vorbis comment data
        f.seek(tag_offset)
        f.write(tag_data)

    @loadfile(writable=True)
    def delete(self, filething=None):
        self.clear()
        f = filething.fileobj
        info = XQAFInfo(f)
        if not info._has_existing_tags:
            return
        delete_bytes(f, info._tag_length, info._tag_offset)
        f.seek(info._header_tag_offset_position)
        format = ">QI" if info._flags.is_64bit else ">II"
        f.write(struct.pack(format, 0, 0))

    @staticmethod
    def _update_flags(fileobj, flags: XQAFFlags):
        """Update the flags in the XQAF header."""
        fileobj.seek(6)
        fileobj.write(struct.pack(">I", flags))

    @classmethod
    def _upgrade_to_64bit(cls, fileobj, info: XQAFInfo) -> XQAFInfo:
        """Upgrade the XQAF file to 64-bit mode."""
        if info._flags.is_64bit:
            return info

        # Resize the header to the larger size
        resize_bytes(fileobj, _XQAF_EXTENDED_HEADER_SIZE_32, _XQAF_EXTENDED_HEADER_SIZE_64, _XQAF_BASE_HEADER_SIZE)
        length_offset = _XQAF_EXTENDED_HEADER_SIZE_64 - _XQAF_EXTENDED_HEADER_SIZE_32

        # Write the new tags for 64-bit mode
        info._flags |= XQAFFlags.IS_64BIT
        cls._update_flags(fileobj, info._flags)

        # Update the data positions
        info._data_offset = info._data_offset + length_offset
        fileobj.seek(18)
        fileobj.write(struct.pack(">QQ", info._data_offset, info._data_length))
        if info._has_existing_tags:
            info._tag_offset = info._tag_offset + length_offset
        fileobj.write(struct.pack(">QI", info._tag_offset, info._tag_length))

        return info


class XQAF(FileType):
    """XQAF(filething)

    Arguments:
        filething (filething)

    Attributes:
        info (`XQAFInfo`)
    """

    _mimes = ["audio/x-xqaf"]

    @loadfile()
    def load(self, filething):
        try:
            self.info = XQAFInfo(filething.fileobj)
            tag_data = self._read_tag_data(filething)
            if tag_data:
                self.tags = XQAFVCommentDict(tag_data)
        except IOError as e:
            raise XQAFError(e)

    @loadfile(writable=True)
    def save(self, filething=None, compression=XQAFCompressionMode.KEEP):
        super().save(filething, compression=compression)

    def add_tags(self):
        """Add empty tags to the file."""
        if self.tags is None:
            self.tags = XQAFVCommentDict()
        else:
            raise XQAFError("tags already exists")

    @staticmethod
    def score(filename, fileobj, header):
        filename = filename.lower()
        return header.startswith(b"XQAF") and (
            filename.endswith(".xqa") or filename.endswith(".xqaf"))

    def _read_tag_data(self, filething):
        if self.info._tag_offset > 0 and self.info._tag_length > 0:
            filething.fileobj.seek(self.info._tag_offset)
            tag_data = filething.fileobj.read(self.info._tag_length)
            if tag_data:
                if self.info._flags.is_compressed:
                    if not zstd:
                        raise XQAFError("Decompression of XQAF tags unavailable (requires zstandard)")
                    # Tags compressed by xqatool do not specify a content size.
                    # Hence we need to specify max_output_size to successfully
                    # decompress the data.
                    tag_data = zstd.decompress(tag_data, max_output_size=3*len(tag_data))

                return tag_data
        return None
