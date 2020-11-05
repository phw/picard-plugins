# -*- coding: utf-8 -*-
#
# Copyright (c) 2020 Philipp Wolfer
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
PLUGIN_VERSION = "0.1.0"
PLUGIN_API_VERSIONS = ["2.2", "2.3", "2.4", "2.5"]
PLUGIN_LICENSE = "GPL-2.0-or-later"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"


from collections import defaultdict
import os
import shutil
import subprocess
import tempfile
from functools import partial

from picard import (
    config,
    log,
)
from picard.const.sys import (
    IS_LINUX,
    IS_MACOS,
)
from picard.file import register_file_post_save_processor
from picard.util import (
    decode_filename,
    encode_filename,
)

if IS_MACOS:
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

    def generate_icns(tempdir, image):
        iconset_dir = os.path.join(tempdir, 'Icon.iconset')
        os.mkdir(iconset_dir)
        for size, scale in ICON_SIZES:
            if size > image.width:
                continue
            if scale == 1:
                icon_filename = "icon_%dx%d.png" % (size, size)
            else:
                icon_filename = "icon_%dx%d@%dx.png" % (size, size, scale)
            subprocess.check_call([
                'sips', '--setProperty', 'format', 'png',
                '--resampleHeightWidth', str(size), str(size),
                image.tempfile_filename,
                '--out', os.path.join(iconset_dir, icon_filename)
            ])
        icns_filepath = os.path.join(tempdir, 'Icon.icns')
        subprocess.check_call([
            'iconutil', '--convert', 'icns', '--output', icns_filepath, iconset_dir
        ])
        return icns_filepath

    def generate_rsrc(tempdir, icns_filepath):
        rsrc_filepath = os.path.join(tempdir, 'Icon.rsrc')
        with open(rsrc_filepath, 'w') as file:
            file.write("read 'icns' (-16455) \"%s\";" % os.path.basename(icns_filepath))
        return rsrc_filepath

    def set_folder_icon(folder_path, rsrc_filepath):
        # See also https://stackoverflow.com/questions/8371790/how-to-set-icon-on-file-or-directory-using-cli-on-os-x
        icon_filepath = os.path.join(folder_path, "Icon\r")
        if os.path.isfile(icon_filepath):
            os.unlink(icon_filepath)
        # Append the icon data as extended attribute "com.apple.ResourceFork"
        # to a special icon file
        subprocess.check_call(['Rez', '-append', rsrc_filepath, '-o', icon_filepath])
        # Mark the folder to show the custom icon
        subprocess.check_call(['SetFile', '-a', 'C', folder_path])
        # Hide the special icon file
        subprocess.check_call(['SetFile', '-a', 'V', icon_filepath])

    def on_file_save_processor(file):
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

        try:
            with tempfile.TemporaryDirectory() as tempdir:
                icns_filepath = generate_icns(tempdir, cover_image)
                rsrc_filepath = generate_rsrc(tempdir, icns_filepath)
                set_folder_icon(os.path.dirname(file.filename), rsrc_filepath)
                album.metadata['~albumfoldercoverhash'] = image_hash
        except (FileNotFoundError, subprocess.CalledProcessError) as err:
            log.error('albumfoldercover: setting folder icon for %s failed: %r',
                file.filename, err)


    register_file_post_save_processor(on_file_save_processor)

elif IS_LINUX:
    # gio set Medusa metadata::custom-icon file:///home/phw/Musik/Library/Paradise%20Lost/Medusa/AlbumArt.jpg
    gio = shutil.which('gio')

    if not gio:
        log.warning('albumfoldercover: this plugin requires gio')

    def get_cover_image_path(folder_path, image, metadata):
        filename = config.setting["cover_image_filename"]
        image_filepath = decode_filename(image._make_image_filename(filename, folder_path, metadata))
        image_filepath += image.extension
        if not os.path.exists(image_filepath) or not config.setting["save_images_to_files"]:
            counters = defaultdict(lambda: 0)
            image.save(folder_path, metadata, counters)
            saved_filepath = image_filepath
            image_filepath = os.path.join(folder_path, '.cover' + image.extension)
            shutil.move(saved_filepath, image_filepath)
        return image_filepath

    def set_folder_icon(folder_path, image_filepath):
        log.debug('albumfoldercover: Setting cover for %r to %r',
            folder_path, image_filepath)
        image_filepath = 'file://' + image_filepath
        subprocess.check_call([gio, 'set', folder_path, 'metadata::custom-icon', image_filepath])

    def on_file_save_processor(file):
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

        try:
            album_folder = os.path.dirname(file.filename)
            image_filepath = get_cover_image_path(album_folder, cover_image, album.metadata)
            set_folder_icon(album_folder, image_filepath)
            album.metadata['~albumfoldercoverhash'] = image_hash
        except (subprocess.CalledProcessError) as err:
            log.error('albumfoldercover: setting folder icon for %s failed: %r',
                file.filename, err)

    if gio:
        register_file_post_save_processor(on_file_save_processor)

else:
    log.warning('albumfoldercover: this plugin is not supported on this operating system')
