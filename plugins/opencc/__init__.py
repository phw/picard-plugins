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
PLUGIN_VERSION = "1.1.1"
PLUGIN_API_VERSIONS = ["2.0", "2.1", "2.2", "2.3"]
PLUGIN_LICENSE = "MIT"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"


from picard.album import Album
from picard.cluster import Cluster
from picard.plugins.opencc.opencc import OpenCC
from picard.script import register_script_function
from picard.track import Track
from picard.ui.itemviews import (
    BaseAction,
    register_album_action,
    register_cluster_action,
    register_file_action,
    register_track_action,
)


class ConvertChineseAction(BaseAction):
    def __init__(self, config):
        super().__init__()
        self.converter = OpenCC(config=config)

    def callback(self, objs):
        for obj in objs:
            self.convert_object_metadata(obj)

    def convert(self, text):
        return self.converter.convert(text)

    def convert_metadata(self, m):
        for key, value in m.items():
            m[key] = self.convert(value)

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


class SimplifiedChineseConverter(ConvertChineseAction):
    NAME = "Convert to Simplified Chinese"

    def __init__(self):
        super().__init__('t2s.json')


class TraditionalChineseConverter(ConvertChineseAction):
    NAME = "Convert to Traditional Chinese"

    def __init__(self):
        super().__init__('s2t.json')


simplified_converter = SimplifiedChineseConverter()
traditional_converter = TraditionalChineseConverter()


def convert_to_simplified_chinese(parser, text):
    if not text:
        return ""
    return simplified_converter.convert(text)


def convert_to_traditional_chinese(parser, text):
    if not text:
        return ""
    return traditional_converter.convert(text)


register_album_action(simplified_converter)
register_cluster_action(simplified_converter)
register_file_action(simplified_converter)
register_track_action(simplified_converter)

register_album_action(traditional_converter)
register_cluster_action(traditional_converter)
register_file_action(traditional_converter)
register_track_action(traditional_converter)

register_script_function(convert_to_simplified_chinese)
register_script_function(convert_to_traditional_chinese)
