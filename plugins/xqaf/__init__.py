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
    'Support for loading, tagging and renaming the XQAF audio file format.\n\n'
    'See [Introducing the Extended QOA Format for Audio](https://remilia.sdf.org/blog/2025-06-14-a.html).'

)
PLUGIN_VERSION = "0.1"
PLUGIN_API_VERSIONS = ["2.8"]
PLUGIN_LICENSE = "GPL-2.0"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"

from picard.formats import register_format
from picard.formats.vorbis import VCommentFile

from .xqaf import XQAF


class XQAFFile(VCommentFile):

    """Extended QOA Format file."""
    EXTENSIONS = [".xqa", ".xqaf"]
    NAME = "Extended QOA Format"
    _File = XQAF


register_format(XQAFFile)
