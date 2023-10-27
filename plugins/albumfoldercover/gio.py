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

from collections import defaultdict
import os
import shutil
import subprocess

from .processor import AbstractAlbumFolderProcessor

from picard import (
  config,
  log,
)
from picard.album import Album
from picard.coverart.image import CoverArtImage
from picard.file import File
from picard.metadata import Metadata
from picard.util import decode_filename


class GioAlbumFolderProcessor(AbstractAlbumFolderProcessor):
    """Sets the album folder as GIO attribute, as supported by GNOME.
    """

    def __init__(self):
        super().__init__()
        self.require_command('gio')

    def set_folder_icon(self, album: Album, file: File, album_folder: str, cover_image: CoverArtImage) -> bool:
        try:
            image_filepath = self._get_cover_image_path(album_folder, cover_image, album.metadata)
            log.debug("albumfoldercover: saving cover to %s", image_filepath)
            self._set_folder_icon(album_folder, image_filepath)
            return True
        except (subprocess.CalledProcessError) as err:
            log.error('albumfoldercover: setting folder icon for %s failed: %r',
                file.filename, err)
            return False

    def _get_cover_image_path(self, folder_path: str, image: CoverArtImage, metadata: Metadata):
        filename = config.setting["cover_image_filename"]
        win_compat = config.setting["windows_compatibility"]
        win_shorten_path = win_compat and not config.setting['windows_long_paths']
        image_filepath = decode_filename(image._make_image_filename(
            filename, folder_path, metadata, win_compat, win_shorten_path))
        image_filepath += image.extension
        if not os.path.exists(image_filepath) or not config.setting["save_images_to_files"]:
            image_filepath = os.path.join(folder_path, '.cover' + image.extension)
            shutil.copyfile(image.tempfile_filename, image_filepath)
        return image_filepath

    def _set_folder_icon(self, folder_path: str, image_filepath: str):
        log.debug('albumfoldercover: Setting cover for %r to %r',
            folder_path, image_filepath)
        # Set path to the image relative to folder
        image_filepath = os.path.relpath(image_filepath, folder_path)
        self.run_command(
            'gio',
            'set', folder_path,
            'metadata::custom-icon', image_filepath,
        )
