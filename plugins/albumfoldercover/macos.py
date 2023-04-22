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
import subprocess
import tempfile

from .processor import AbstractAlbumFolderProcessor

from picard import log
from picard.album import Album
from picard.coverart.image import CoverArtImage
from picard.file import File


class MacosAlbumFolderProcessor(AbstractAlbumFolderProcessor):
    """Generates an icon set from the cover art and sets it as the folder icon.

    Requires the iconutil CLI utility, which is provided as part of Xcode. The
    Xcode "Command Line Tools" need to be installed. If those are not installed
    run the following command to install them:

        xcode-select –install
    """

    ICON_SIZES = [
        (1024, 1),
        (512, 1),
        (512, 2),
        (256, 1),
        (256, 2),
        (128, 1),
        (64, 1),
        (32, 1),
        (32, 2),
        (16, 1),
    ]

    def __init__(self):
        super().__init__()
        self.require_command('iconutil')
        self.require_command('Rez')
        self.require_command('SetFile')
        self.require_command('sips')

    def set_folder_icon(self, album: Album, file: File, album_folder: str, cover_image: CoverArtImage) -> bool:
        """Implementation of applying cover_image to album_folder"""
        try:
            with tempfile.TemporaryDirectory() as tempdir:
                icns_filepath = self._generate_icns(tempdir, cover_image)
                rsrc_filepath = self._generate_rsrc(tempdir, icns_filepath)
                self._set_folder_icon(album_folder, rsrc_filepath)
                return True
        except (FileNotFoundError, subprocess.CalledProcessError) as err:
            log.error('albumfoldercover: setting folder icon for %s failed: %r',
                file.filename, err)
            return False

    def _generate_icns(self, tempdir: str, image: CoverArtImage) -> str:
        """Generates a macOS icon set using iconutil"""
        iconset_dir = os.path.join(tempdir, 'Icon.iconset')
        os.mkdir(iconset_dir)
        for size, scale in self.ICON_SIZES:
            if size > image.width:
                continue
            if scale == 1:
                icon_filename = "icon_%dx%d.png" % (size, size)
            else:
                icon_filename = "icon_%dx%d@%dx.png" % (size, size, scale)
            self.run_command(
                'sips',
                '--setProperty', 'format', 'png',
                '--resampleHeightWidth', str(size), str(size),
                image.tempfile_filename,
                '--out', os.path.join(iconset_dir, icon_filename)
            )
        icns_filepath = os.path.join(tempdir, 'Icon.icns')
        self.run_command(
            'iconutil',
            '--convert', 'icns',
            '--output', icns_filepath,
            iconset_dir,
        )
        return icns_filepath

    def _generate_rsrc(self, tempdir: str, icns_filepath: str) -> str:
        """Generate icon resource"""
        rsrc_filepath = os.path.join(tempdir, 'Icon.rsrc')
        with open(rsrc_filepath, 'w') as file:
            file.write("read 'icns' (-16455) \"%s\";" % os.path.basename(icns_filepath))
        return rsrc_filepath

    def _set_folder_icon(folder_path: str, rsrc_filepath: str):
        # See also https://stackoverflow.com/questions/8371790/how-to-set-icon-on-file-or-directory-using-cli-on-os-x
        icon_filepath = os.path.join(folder_path, "Icon\r")
        if os.path.isfile(icon_filepath):
            os.unlink(icon_filepath)
        # Append the icon data as extended attribute "com.apple.ResourceFork"
        # to a special icon file
        self.run_command(
            'Rez',
            '-append', rsrc_filepath,
            '-o', icon_filepath,
        )
        # Mark the folder to show the custom icon
        self.run_command(
            'SetFile', '-a', 'C', folder_path,
        )
        # Hide the special icon file
        self.run_command(
            'SetFile', '-a', 'V', icon_filepath,
        )
