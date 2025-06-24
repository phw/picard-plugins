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

PLUGIN_NAME = 'XQAF'
PLUGIN_AUTHOR = 'Philipp Wolfer'
PLUGIN_DESCRIPTION = (
    'Support for the XQAF and QOA audio file formats.\n\n'
    'XQAF files support full tagging. QOA files do not store tags, but can '
    'be loaded and renamed.\n\n'
    'For more details about both formats see '
    '[Introducing the Extended QOA Format for Audio](https://remilia.sdf.org/blog/2025-06-14-a.html) '
    'and [The Quite OK Audio Format](https://qoaformat.org/).'

)
PLUGIN_VERSION = "0.1"
PLUGIN_API_VERSIONS = ["2.8"]
PLUGIN_LICENSE = "GPL-2.0"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"


from picard.formats import register_format
from picard.file import File
from picard.formats.vorbis import VCommentFile
from picard import log
from picard.metadata import Metadata

from .qoa import QOA
from .xqaf import XQAF


class QOAFile(File):

    """Quite OK Audio file."""
    EXTENSIONS = [".qoa"]
    NAME = "Quite OK Audio"
    _File = QOA

    def _load(self, filename):
        log.debug("Loading file %r", filename)
        f = QOA(filename)
        metadata = Metadata()
        self._info(metadata, f)
        return metadata

    def _save(self, filename, metadata):
        log.debug("Saving file %r", filename)

    @classmethod
    def supports_tag(cls, name):
        return False


class XQAFFile(VCommentFile):

    """Extended QOA Format file."""
    EXTENSIONS = [".xqa", ".xqaf"]
    NAME = "Extended QOA Format"
    _File = XQAF

    def _save(self, filename, metadata):
        # Do not store the gapless tag in the metadata.
        # XQAF files do have this information in the header,
        # and for now this tag is considered readonly.
        del metadata["gapless"]
        super()._save(filename, metadata)

    def _info(self, metadata, file):
        super()._info(metadata, file)
        if file.info.gapless:
            metadata.set("gapless", 1)


register_format(QOAFile)
register_format(XQAFFile)
