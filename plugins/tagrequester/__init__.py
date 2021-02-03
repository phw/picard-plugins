# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Philipp Wolfer
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

PLUGIN_NAME = "TagRequester"
PLUGIN_AUTHOR = "Philipp Wolfer"
PLUGIN_DESCRIPTION = (
    'Use the TagRequester audio fingerprinting to fill basic tags.<br><br>'
    'Requires installing and running <a href="http://www.peter-ebe.com/TagRequester/info/tagrequester_download_en.php">TagRequester</a>.'
)
PLUGIN_VERSION = '0.1'
PLUGIN_API_VERSIONS = ['2.5', '2.6']
PLUGIN_LICENSE = "GPL-2.0-or-later"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"

from functools import partial
from io import FileIO
from typing import Tuple

from PyQt5.QtCore import QThreadPool

from picard import log
from picard.file import File
from picard.metadata import Metadata
from picard.util import (
    htmlescape,
    iter_files_from_objects,
    thread,
)
from picard.util.xml import (
    XmlNode,
    parse_xml,
)

from picard.ui.itemviews import (
    BaseAction,
    register_album_action,
    register_cluster_action,
    register_clusterlist_action,
    register_file_action,
    register_track_action,
)

TAG_REQUESTER_PIPE = r'\\.\pipe\TagRequester'
TAG_MAPPING = {
    'TITLE': 'title',
    'ARTIST': 'artist',
    'ALBUM': 'album',
    'TRACK': 'tracknumber',
    'YEAR': 'date',
    'GENRE': 'genre',
    'BPM': 'bpm',
    # 'SYNPOS': '?',  # FIXME: What's this?
}


class TagRequesterAction(BaseAction):
    NAME = 'TagRequester fingerprinting...'

    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(1)  # Avoid parallel access to the named PIPE

    def callback(self, objs):
        thread.run_task(
            partial(self.tag_request, objs),
            self.finish_callback,
            thread_pool=self.thread_pool)

    def finish_callback(self, result=None, error=None):
        if error:
            log.error('[TagRequester] Error: %s', error)
            self.tagger.window.set_statusbar_message(
                "TagRequester failed: %s", error)
            return

    def tag_request(self, objs):
        with open(TAG_REQUESTER_PIPE, 'rb+', buffering=0) as pipe:
            for file in iter_files_from_objects(objs):
                response = self.query(pipe, file.filename)
                self.handle_response(file, response)

    def query(self, pipe: FileIO, filename: str) -> XmlNode:
        request = self.build_request(filename)
        log.debug('[TagRequester] Request %s', request)
        pipe.write(request)
        response = b''
        for line in pipe:
            response += line
            if line.rstrip().endswith(b'</clientapi>'):
                break
        log.info('[TagRequester] Query response %s', response)
        return parse_xml(response)

    @staticmethod
    def build_request(filename: str) -> bytes:
        return (b'<?xml version="1.0" encoding="UTF-8"?>\n'
                b'<clientapi><FILENAME>%s</FILENAME></clientapi>') % htmlescape(filename).encode('utf-8')

    def handle_response(self, file: File, response: XmlNode):
        success, error = self.check_response(response)
        if not success:
            log.error('[TagRequester] Error: %s', error)
            return
        metadata = self.xml_to_metadata(response)
        thread.to_main(partial(self.update_metadata, file, metadata))

    def update_metadata(self, file: File, metadata: Metadata):
        self.tagger.window.set_statusbar_message(
            "TagRequester found metadata for %s", file.filename)
        file.metadata.update(metadata)
        file.update()

    @staticmethod
    def check_response(node: XmlNode) -> Tuple[bool, str]:
        if 'clientapi' not in node.children:
            return False, '<clientapi> not found in response'
        clientapi = node.children['clientapi'][0]
        if 'ERROR' in clientapi.children:
            return False, clientapi.children['ERROR'][0].text
        return True, None

    @staticmethod
    def xml_to_metadata(node: XmlNode) -> Metadata:
        metadata = Metadata()
        for name, children in node.children['clientapi'][0].children.items():
            if name in TAG_MAPPING:
                values = [child.text for child in children if child.text]
                if values:
                    metadata[TAG_MAPPING[name]] = values
        return metadata


register_album_action(TagRequesterAction())
register_cluster_action(TagRequesterAction())
register_clusterlist_action(TagRequesterAction())
register_file_action(TagRequesterAction())
register_track_action(TagRequesterAction())
