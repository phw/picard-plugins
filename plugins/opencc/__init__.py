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

PLUGIN_NAME = 'Chinese script conversion'
PLUGIN_AUTHOR = 'Philipp Wolfer'
PLUGIN_DESCRIPTION = ('Convert track listings between Traditional Chinese and'
                      'Simplified Chinese script.')
PLUGIN_VERSION = "1.0.0"
PLUGIN_API_VERSIONS = ["2.0", "2.1", "2.2"]
PLUGIN_LICENSE = "GPL-2.0-or-later"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"


import opencc

from picard.album import Album
from picard.cluster import Cluster
from picard.track import Track
from picard.ui.itemviews import (
    BaseAction,
    register_album_action,
    register_cluster_action,
    register_track_action,
)


class ConvertChineseAction(BaseAction):
    def __init__(self, config):
        super().__init__()
        self.converter = opencc.OpenCC(config=config)

    def callback(self, objs):
        for obj in objs:
            self.convert_object_metadata(obj)

    def convert_metadata(self, m):
        for key, value in m.items():
            m[key] = self.converter.convert(value)

    def convert_object_metadata(self, obj):
        if hasattr(obj, 'metadata'):
            self.convert_metadata(obj.metadata)
            obj.update()

        if isinstance(obj, Album):
            for track in obj.tracks:
                self.convert_object_metadata(track)
        elif isinstance(obj, Cluster):
            for file in obj.files:
                self.convert_object_metadata(file)
        elif isinstance(obj, Track):
            for file in obj.linked_files:
                self.convert_object_metadata(file)


class ConvertToSimplifiedChinese(ConvertChineseAction):
    NAME = "Convert to Simplified Chinese"

    def __init__(self):
        super().__init__('t2s.json')


class ConvertToTraditionalChinese(ConvertChineseAction):
    NAME = "Convert to Traditional Chinese"

    def __init__(self):
        super().__init__('s2t.json')


convert_to_simplified = ConvertToSimplifiedChinese()
convert_to_traditional = ConvertToTraditionalChinese()

register_album_action(convert_to_simplified)
register_cluster_action(convert_to_simplified)
register_track_action(convert_to_simplified)

register_album_action(convert_to_traditional)
register_cluster_action(convert_to_traditional)
register_track_action(convert_to_traditional)
