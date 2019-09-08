# -*- coding: utf-8 -*-
#
# Copyright (C) 2014, 2019 Philipp Wolfer
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

from . import enzyme
from picard import log
from picard.file import File
from picard.metadata import Metadata


class EnzymeFile(File):

    def _load(self, filename):
        log.debug("Loading file %r", filename)
        metadata = Metadata()
        self._add_path_to_metadata(metadata)

        parser = enzyme.parse(filename)
        log.debug("Metadata for %s:\n%s", filename, str(parser))
        self._convertMetadata(parser, metadata)

        return metadata

    def _convertMetadata(self, parser, metadata):
        metadata['~format'] = parser.type

        if hasattr(parser, 'title') and parser.title:
            metadata["title"] = parser.title

        if hasattr(parser, 'artist') and parser.artist:
            metadata["artist"] = parser.artist

        if hasattr(parser, 'trackno') and parser.trackno:
            parts = parser.trackno.split("/")
            metadata["tracknumber"] = parts[0]
            if len(parts) > 1:
                metadata["totaltracks"] = parts[1]

        if hasattr(parser, 'encoder') and parser.encoder:
            metadata["encodedby"] = parser.encoder

        if len(parser.video) > 0:
            video = parser.video[0]
            metadata["~video"] = True

        if len(parser.audio) > 0:
            audio = parser.audio[0]
            if hasattr(audio, 'channels') and audio.channels:
                metadata["~channels"] = audio.channels

            if hasattr(audio, 'samplerate') and audio.samplerate:
                metadata["~sample_rate"] = audio.samplerate

            if hasattr(audio, 'language') and audio.language:
                metadata["language"] = audio.language

        if hasattr(parser, 'length') and parser.length:
            metadata.length = parser.length * 1000
        elif video and hasattr(video, 'length') and video.length:
            metadata.length = parser.video[0].length * 1000

    def _save(self, filename, metadata):
        log.debug("Saving file %r", filename)
        pass


class MatroskaFile(EnzymeFile):
    EXTENSIONS = [".mka", ".mkv", ".webm"]
    NAME = "Matroska"


class MpegFile(EnzymeFile):
    EXTENSIONS = [".mpg", ".mpeg"]
    NAME = "MPEG"


class RiffFile(EnzymeFile):
    EXTENSIONS = [".avi"]
    NAME = "RIFF"


class QuickTimeFile(EnzymeFile):
    EXTENSIONS = [".mov", ".qt"]
    NAME = "QuickTime"
