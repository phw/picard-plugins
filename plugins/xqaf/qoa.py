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

from mutagen import FileType, MutagenError, StreamInfo
from mutagen._util import loadfile


class QOAError(MutagenError):
    pass


class QOAInfo(StreamInfo):
    """QOA stream information.

    Attributes:
      channels (`int`): number of audio channels
      length (`float`): file length in seconds, as a float
      sample_rate (`int`): audio sampling rate in Hz
    """

    def __init__(self, fileobj):
        # See spec at https://qoaformat.org/qoa-specification.pdf
        header = fileobj.read(8)
        if not header.startswith(b"qoaf") or len(header) < 8:
            raise QOAError("Invalid QOA header")

        number_of_samples = struct.unpack(">I", header[4:8])[0]

        # Read the first sample header
        sample_header = fileobj.read(8)
        if len(sample_header) < 8:
            raise QOAError("Insufficient data for reading QOA header")

        (channels, sample_rate, _fsamples, _fsize) = struct.unpack(">B3sHH", sample_header)

        self.sample_rate = int.from_bytes(sample_rate, 'big')
        self.channels = channels

        if self.sample_rate > 0:
            self.length = number_of_samples / float(self.sample_rate)


class QOA(FileType):
    """QOA(filething)

    Arguments:
        filething (filething)

    Attributes:
        info (`QOAInfo`)
    """

    _mimes = ["audio/x-qoa"]

    @loadfile()
    def load(self, filething):
        try:
            self.info = QOAInfo(filething.fileobj)
        except IOError as e:
            raise QOAError(e)

    def add_tags(self):
        raise QOAError("doesn't support tags")

    @staticmethod
    def score(filename, fileobj, header):
        filename = filename.lower()
        return header.startswith(b"qoaf") and (
            filename.endswith(".qoa"))
