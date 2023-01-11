# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 Philipp Wolfer
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

# "Persistent variables display" context is based on the code from
# the "View Script Variables" plugin.

PLUGIN_NAME = 'Lookup Experiments'
PLUGIN_AUTHOR = 'Philipp Wolfer'
PLUGIN_DESCRIPTION = '''
Provides alternative experimental lookup methods.

- ListenBrainz: Uses ListenBrainz API for lookup single files by track title and arist name
'''
PLUGIN_VERSION = '0.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2', '2.3', '2.4', '2.6', '2.7', '2.8', '2.9']
PLUGIN_LICENSE = 'GPL-2.0-or-later'
PLUGIN_LICENSE_URL = 'https://www.gnu.org/licenses/gpl-2.0.html'

from functools import partial

from picard import log
from picard.util import iter_files_from_objects
from picard.webservice import ratecontrol

from picard.ui.itemviews import (
    BaseAction,
    register_cluster_action,
    register_file_action,
)

LISTENBRAINZ_HOST = 'api.listenbrainz.org'
LISTENBRAINZ_PORT = 443

ratecontrol.set_minimum_delay((LISTENBRAINZ_HOST, LISTENBRAINZ_PORT), 250)

class ListenBrainzLookup(BaseAction):
    """
    Implements lookup by artist and track title using the ListenBrainz API.
    
    See https://listenbrainz.readthedocs.io/en/latest/users/api/metadata.html#get--1-metadata-lookup-
    """
    NAME = 'ListenBrainz Lookup...'

    @property
    def webservice(self):
        return self.tagger.webservice

    def callback(self, objs):
        for file in iter_files_from_objects(objs, save=True):
            file.set_pending()
            self.lookup(file)

    def lookup(self, file):
        # https://api.listenbrainz.org/1/metadata/lookup/?artist_name=Paradise%20Lost&recording_name=Say%20Just%20Words
        metadata = file.metadata
        queryargs = {
            'artist_name': metadata['artist'] or metadata['albumartist'],
            'recording_name': metadata['title'],
        }
        self.webservice.get(
            LISTENBRAINZ_HOST,
            LISTENBRAINZ_PORT,
            '/1/metadata/lookup/',
            partial(self.lookup_finished, file),
            priority=True,
            important=False,
            parse_response_type='json',
            queryargs=queryargs)

    def lookup_finished(self, file, data, reply, error):
        if error:
            log.error("LB lookup failed for %r: %s", file, error)
            file._set_error(error)
            return
        log.info("LB lookup for %r: %s", file, data)
        albumid = data.get('release_mbid')
        recordingid = data.get('recording_mbid')
        if albumid:
            self.tagger.move_file_to_track(file, albumid, recordingid)
        elif recordingid:
            self.tagger.move_file_to_nat(file, recordingid)
        else:
            file.clear_pending()


register_cluster_action(ListenBrainzLookup())
register_file_action(ListenBrainzLookup())
