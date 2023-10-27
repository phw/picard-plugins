# -*- coding: utf-8 -*-
#
# Copyright (c) 2020-2023 Philipp Wolfer
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

PLUGIN_NAME = 'Album Folder Cover'
PLUGIN_AUTHOR = 'Philipp Wolfer'
PLUGIN_DESCRIPTION = 'Set the folder icon to the album cover on macOS and Linux'
PLUGIN_VERSION = "0.3"
PLUGIN_API_VERSIONS = ["2.9"]
PLUGIN_LICENSE = "GPL-2.0-or-later"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"


from picard import (
    log,
)
from picard.const.sys import (
    IS_LINUX,
    IS_MACOS,
)
from picard.file import register_file_post_save_processor


if IS_MACOS:
    from .macos import MacosAlbumFolderProcessor
    processor = MacosAlbumFolderProcessor()

elif IS_LINUX:
    from .gio import GioAlbumFolderProcessor
    processor = GioAlbumFolderProcessor()

else:
    processor = None
    log.warning('albumfoldercover: this plugin is not supported on this operating system')

if processor and processor.available:
    def file_post_save(file):  # Function must be defined in main plugin module
        processor.process_file(file)

    register_file_post_save_processor(file_post_save)
