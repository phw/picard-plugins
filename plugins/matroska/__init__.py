# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Philipp Wolfer
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

PLUGIN_NAME = 'Matroska/WebM file support'
PLUGIN_AUTHOR = 'Philipp Wolfer'
PLUGIN_DESCRIPTION = ('Adds support for tagging Matroska/WebM files')
PLUGIN_VERSION = "0.1"
PLUGIN_API_VERSIONS = ["2.0", "2.1", "2.2"]
PLUGIN_LICENSE = "GPL-3.0-or-later"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.html"

import re

from picard import log
from picard.file import File
from picard.formats import register_format
from picard.metadata import Metadata
from picard.util import encode_filename
from .matroska import EbmlFile


def parse_parts(value):
    parts = value.split('/', 1)
    if len(parts) > 1:
        return (parts[0], parts[1])
    else:
        return (parts[0], None)


class MatroskaFile(File):
    EXTENSIONS = [".mka", ".mkv", ".webm"]
    NAME = "Matroska"
    _File = EbmlFile

    # See https://www.matroska.org/technical/specs/tagging/index.html
    __TRANS = {
        'album_artist': 'albumartist',
        'encoder': 'encodedby',
        'musicbrainz_album_artist_id': 'musicbrainz_albumartistid',
        'musicbrainz_album_id': 'musicbrainz_albumid',
        'musicbrainz_album_release_country': 'releasecountry',
        'musicbrainz_album_status': 'releasestatus',
        'musicbrainz_album_type': 'releasetype',
        'musicbrainz_artist_id': 'musicbrainz_artistid',
        'musicbrainz_release_group_id': 'musicbrainz_releasegroupid',
        'musicbrainz_release_track_id': 'musicbrainz_trackid',
        'musicbrainz_track_id': 'musicbrainz_recordingid',
        'musicbrainz_work_id': 'musicbrainz_workid',
    }
    __RTRANS = dict([(b, a) for a, b in __TRANS.items()])

    def _load(self, filename):
        log.debug("Loading file %r", filename)
        f = self._File(encode_filename(filename))
        metadata = Metadata()

        for name, tag in f.tags.items():
            if tag.string_val:
                name_lower = tag.tag_name.lower()
                if name_lower == 'disc':
                    (discnumber, totaldiscs) = parse_parts(tag.string_val)
                    metadata['discnumber'] = discnumber
                    if totaldiscs:
                        metadata['totaldiscs'] = totaldiscs
                elif name_lower == 'part_number':
                    (tracknumber, totaltracks) = parse_parts(tag.string_val)
                    metadata['tracknumber'] = tracknumber
                    if totaltracks:
                        metadata['totaltracks'] = totaltracks
                elif name_lower in self.__TRANS:
                    metadata[self.__TRANS[name_lower]] = tag.string_val
                else:
                    metadata[name_lower] = tag.string_val

        return metadata

    def _save(self, filename, metadata):
        log.debug("Saving file %r", filename)
        filename = encode_filename(filename)
        f = self._File(filename)
        tags = f.tags

        for name, values in metadata.rawitems():
            if name in self.__RTRANS:
                name = self.__RTRANS[name]
            else:
                # Names must not contain whitespace
                name = re.sub(r'\s+', '_', name)
            # Tags are always stored uppercase, see
            # https://www.matroska.org/technical/specs/tagging/index.html
            # FIXME: Support multiple tags
            tags[name.upper()] = values[0]

        f.save(filename)

register_format(MatroskaFile)
