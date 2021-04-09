# -*- coding: utf-8 -*-
#
# Copyright 2019, 2021 Philipp Wolfer < ph.wolfer@gmail.com >
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

PLUGIN_NAME = 'Chinese script conversion'
PLUGIN_AUTHOR = 'Philipp Wolfer'
PLUGIN_DESCRIPTION = ('Convert track listings between Traditional Chinese and '
                      'Simplified Chinese script.<br><br>'
                      'The conversion can be done manually or with scripting. '
                      'For manual use right click on album, tracks, clusters '
                      'or files and choose the "Convert to Simplified Chinese" '
                      'or "Convert to Simplified Chinese" action.<br><br>'
                      'For scripting you can use the following tagger functions:'
                      '<ul><li><code>$convert_to_simplified_chinese(text)</code></li>'
                      '<li><code>$convert_to_traditional_chinese(text)</code></li></ul>'
                      )
PLUGIN_VERSION = "1.2"
PLUGIN_API_VERSIONS = ["2.0", "2.1", "2.2", "2.3", "2.4", "2.5", "2.6"]
PLUGIN_LICENSE = "MIT"
PLUGIN_LICENSE_URL = "https://opensource.org/licenses/MIT"


from opencc import OpenCC

from picard import log
from picard.album import Album
from picard.cluster import Cluster
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
        try:
            return self.converter.convert(text)
        except Exception as e:
            log.exception('opencc: %r', e)
            return text

    def convert_metadata(self, m):
        for key, value in list(m.items()):
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
