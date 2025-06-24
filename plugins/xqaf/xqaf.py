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

import struct
try:
    import zstandard as zstd
except ImportError:
    zstd = None

from mutagen import FileType, MutagenError, StreamInfo
from mutagen._vorbis import VCommentDict
from mutagen._util import loadfile, insert_bytes, resize_bytes


class XQAFError(MutagenError):
    pass


class XQAFFlags(int):
    """Flags for XQAF files.

    These flags are used in the XQAF header to indicate various properties
    of the audio file, such as compression and 64-bit fields.
    """
    _GAPLESS = 1 << 0
    _COMPRESSED_TAGS = 1 << 1
    _IS_64BIT = 1 << 31

    @property
    def is_compressed(self):
        return (self & XQAFFlags._COMPRESSED_TAGS) != 0

    @property
    def is_64bit(self):
        return (self & XQAFFlags._IS_64BIT) != 0


class XQAFInfo(StreamInfo):
    """XQAF stream information.

    Attributes:
      channels (`int`): number of audio channels
      length (`float`): file length in seconds, as a float
      sample_rate (`int`): audio sampling rate in Hz
    """

    def __init__(self, fileobj):
        self._parse_header(fileobj)

    def _parse_header(self, fileobj):
        """Parse the XQAF header to extract metadata."""
        # See spec at https://chiselapp.com/user/MistressRemilia/repository/cl-remiaudio/file?name=docs/extended-qoa-format.md&ci=tip
        header = fileobj.read(10)
        if not header.startswith(b"XQAF") or len(header) < 10:
            raise XQAFError("Invalid XQAF header")


        major, minor, flags = struct.unpack(">ccI", header[4:])
        self._flags = XQAFFlags(flags)

        header_length = 24
        header_format = ">3sIBIIII"
        if self._flags.is_64bit:
            # In 64 bit mode the data offsets and lengths are 64-bit,
            # with the exception of tag length which is always 32-bit.
            header_length = 36
            header_format = ">3sIBQQQI"

        extended_header = fileobj.read(header_length)
        if len(extended_header) != header_length:
            raise XQAFError("Insufficient data for reading XQAF header")
        (sample_rate, number_of_samples, channels, data_offset, data_length,
         tag_offset, tag_length) = struct.unpack(header_format, extended_header)

        self.sample_rate = int.from_bytes(sample_rate, 'big')
        self.channels = channels

        if self.sample_rate > 0:
            self.length = number_of_samples / float(self.sample_rate)

        # Store data and tag offsets for internal use
        self._data_offset = data_offset
        self._data_length = data_length
        self._tag_offset = tag_offset
        self._tag_length = tag_length


class XQAFVCommentDict(VCommentDict):

    def load(self, fileobj, errors='replace', framing=True, compression=False):
        super().load(fileobj, errors=errors, framing=framing)

    def save(self, filething, framing=True, compression=False):
        """Save the Vorbis comment to a file-like object."""
        f = filething.fileobj
        info = XQAFInfo(f)

        compression = (compression and bool(zstd)) or info._flags.is_compressed
        if info._flags.is_compressed and not zstd:
            # Fail instead of silently overwriting compressed tags
            raise XQAFError("Compression of XQAF tags is not implemented")

        tag_data = self.write(framing=framing)
        new_size = len(tag_data)
        data_offset = info._data_offset
        tag_offset = info._tag_offset

        # If compression is enabled, compress the tag data
        if compression:
            if not zstd:
                raise XQAFError("Compression of XQAF tags requires zstd")
            tag_data = zstd.compress(tag_data)
            new_size = len(tag_data)

            if not info._flags.is_compressed:
                flags = info._flags | XQAFFlags._COMPRESSED_TAGS
                f.seek(6)
                f.write(struct.pack(">I", flags))

        if tag_offset > 0 and info._tag_length > 0:
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
        if info._flags.is_64bit:
            tag_offset_position = 34
            format = ">Q"
        else:
            tag_offset_position = 26
            format = ">I"

        # Update the data offsets and length in the file header
        f.seek(18)
        f.write(struct.pack(format, data_offset))
        f.seek(tag_offset_position)  # Skip the data length, it hasn't changed
        f.write(struct.pack(format, tag_offset))
        f.write(struct.pack(">I", new_size))

        # Write the Vorbis comment data
        f.seek(tag_offset)
        f.write(tag_data)


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
                # FIXME: According to the spec framing is required, but the
                # official xqaf tool does not write it.
                self.tags = XQAFVCommentDict(tag_data, framing=False)
        except IOError as e:
            raise XQAFError(e)

    @loadfile(writable=True)
    def save(self, filething=None, compression=False):
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
                        raise XQAFError("Decompression of XQAF tags not available")
                    # Tags compressed by xqatool do not specify a content size.
                    # Hence we need to specify max_output_size to successfully
                    # decompress the data.
                    tag_data = zstd.decompress(tag_data, max_output_size=3*len(tag_data))

                return tag_data
        return None
