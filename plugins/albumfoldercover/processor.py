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

import os.path
import shutil
import subprocess

from picard.album import Album
from picard.file import File
from picard.coverart.image import CoverArtImage
from picard import log


class AbstractAlbumFolderProcessor:

    def __init__(self) -> None:
        self._commands = {}

    @property
    def available(self) -> bool:
        """True if this processor is available"""
        for command_name, cmd in self._commands.items():
            if not cmd:
                log.warning(
                    'albumfoldercover: this plugin requires "%s" to be '
                    'available in PATH, command not found', command_name)
                return False
        else:
            return True

    def process_file(self, file: File) -> None:
        """Process the file and apply the cover art to the file's parent folder"""
        if not file.parent or not hasattr(file.parent, 'album') or not file.parent.album:
            return

        album = file.parent.album
        cover_image = (album.metadata.images.get_front_image()
                        or file.parent.metadata.images.get_front_image()
                        or file.metadata.images.get_front_image()
                        or file.orig_metadata.images.get_front_image())
        if not cover_image:
            log.debug('albumfoldercover: no cover image for %r', album)
            return

        image_hash = hash(cover_image)
        log.debug("albumfoldercover: image hash: %r, saved hash: %r",
            image_hash, album.metadata['~albumfoldercoverhash'])
        if image_hash and album.metadata['~albumfoldercoverhash'] == str(image_hash):
            return

        album_folder = os.path.dirname(file.filename)
        if self.set_folder_icon(album, file, album_folder, cover_image):
            album.metadata['~albumfoldercoverhash'] = image_hash

    def set_folder_icon(self, album: Album, file: File, album_folder: str, cover_image: CoverArtImage) -> bool:
        """Implementation of applying cover_image to album_folder"""
        raise NotImplementedError()

    def require_command(self, command_name: str) -> None:
        """Prepare a command for use and search it in PATH"""
        self._commands[command_name] = shutil.which(command_name)

    def run_command(self, command_name: str, *args) -> None:
        """Run a previously required command"""
        cmd = self._commands[command_name]
        if not cmd:
            raise ValueError('albumfoldercover: Command "%s" not found' % command_name)
        subprocess.check_call((cmd,) + args)
