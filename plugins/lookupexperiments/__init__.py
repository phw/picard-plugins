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
- AutoTag: Experimental clustering and lookup algorithm using ListenBrainz mappings to
  match a list of files against releases
'''
PLUGIN_VERSION = '0.2'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2', '2.3', '2.4', '2.6', '2.7', '2.8', '2.9']
PLUGIN_LICENSE = 'GPL-2.0-or-later'
PLUGIN_LICENSE_URL = 'https://www.gnu.org/licenses/gpl-2.0.html'

from collections import defaultdict
from functools import partial
import json

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

LISTENBRAINZ_LABS_HOST = 'labs.api.listenbrainz.org'
LISTENBRAINZ_LABS_PORT = 443
ratecontrol.set_minimum_delay((LISTENBRAINZ_LABS_HOST, LISTENBRAINZ_LABS_PORT), 250)

LISTENBRAINZ_DATASETS_HOST = 'datasets.listenbrainz.org'
LISTENBRAINZ_DATASETS_PORT = 443
ratecontrol.set_minimum_delay((LISTENBRAINZ_DATASETS_HOST, LISTENBRAINZ_DATASETS_PORT), 250)



class BaseLookupAction(BaseAction):
    @property
    def webservice(self):
        return self.tagger.webservice


class ListenBrainzLookup(BaseLookupAction):
    """
    Implements lookup by artist and track title using the ListenBrainz API.

    See https://listenbrainz.readthedocs.io/en/latest/users/api/metadata.html#get--1-metadata-lookup-
    """
    NAME = 'ListenBrainz Lookup...'

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

listenbrainz_lookup = ListenBrainzLookup()
register_cluster_action(listenbrainz_lookup)
register_file_action(listenbrainz_lookup)


class AutoTagLookup(BaseLookupAction):
    """
    Using the MBID Mapping from ListenBrainz, it does the following:

    - Scan you music collection (mp3 and flac supported), ignore any MBID tags
    - Map each of the tracks using the mapper
    - Load all of the releases the mapped track could appear on
    - For each track in the collection, add them to the loaded releases, based on MBID.
    - Evaluate the mapped files/releases.

    See https://github.com/metabrainz/auto-tag
    """
    NAME = 'AutoTag Lookup...'

    MAPPING_BATCH_SIZE = 50
    RELEASES_BATCH_SIZE = 20

    def __init__(self):
        super().__init__()
        self.releases = {}

    def callback(self, objs):
        files = list(iter_files_from_objects(objs, save=True))
        for f in files:
            f.set_pending()
        self.request_batch(files, 0, mapped=[], unidentified=[])

    def clear_pending(self, files):
        for f in files:
            f.clear_pending()

    def request_batch(self, files, index, mapped, unidentified):
        batch = files[index:index + self.MAPPING_BATCH_SIZE]
        if not batch:
            self.after_mapping(mapped, unidentified)
            return
        post_data = [{
            "[artist_credit_name]": f.metadata["artist"],
            "[recording_name]": f.metadata["title"]
        } for f in batch]
        self.webservice.post(
            LISTENBRAINZ_LABS_HOST,
            LISTENBRAINZ_LABS_PORT,
            '/mbid-mapping/json',
            json.dumps(post_data),
            partial(self.request_batch_finished, files, index, batch, mapped, unidentified),
            priority=True,
            important=False,
            parse_response_type='json',
            request_mimetype="application/json")

    def request_batch_finished(self, files, index, batch, mapped, unidentified, data, reply, error):
        if error:
            log.error("AutoTagLookup: could not map tracks: %s", error)
            self.after_mapping(None, None)
            self.clear_pending(files)
            return

        recording_index = {}
        for result in data:
            recording_index[result["index"]] = result

        for i, file in enumerate(batch):
            if i not in recording_index:
                unidentified.append(file)
                continue
            mapped.append((file, recording_index[i]))

        self.request_batch(files, index + self.MAPPING_BATCH_SIZE, mapped, unidentified)

    def after_mapping(self, mapped, unidentified):
        self.clear_pending(unidentified)
        if not mapped:
            log.warn('AutoTagLookup: could not map any files')
            return
        log.info(f'AutoTagLookup: mapped {len(mapped)}, unidentified {len(unidentified)}')
        self.load_releases(mapped, 0, releases={})

    def load_releases(self, mapped, index, releases):
        batch = mapped[index:index + self.RELEASES_BATCH_SIZE]
        if not batch:
            self.after_load_releases(mapped, releases)
            return

        post_data = [{"[recording_mbid]": m['recording_mbid']} for f, m in batch]
        self.webservice.post(
            LISTENBRAINZ_DATASETS_HOST,
            LISTENBRAINZ_DATASETS_PORT,
            '/releases-from-recordings/json',
            json.dumps(post_data),
            partial(self.load_releases_finished, mapped, index, releases),
            priority=True,
            important=False,
            parse_response_type='json',
            request_mimetype="application/json")

    def load_releases_finished(self, mapped, index, releases, data, reply, error):
        if error:
            log.error("AutoTagLookup: could not load releases: %s", error)
            self.after_load_releases(mapped, None)
            return
        for result in data:
            if result["release_mbid"] not in releases:
                releases[result["release_mbid"]] = result
        self.load_releases(mapped, index + self.RELEASES_BATCH_SIZE, releases)

    def after_load_releases(self, mapped, releases):
        # We clear the pending here for all files to simplify the process
        # FIXME: Run clear pending once files have been processed (matched or not)
        self.clear_pending((f for f, m in mapped))
        if not releases:
            log.warn('AutoTagLookup: could not load releases')
            return
        self.load_recordings_into_releases(mapped, releases)

    def load_recordings_into_releases(self, mapped, releases):
        release_index = defaultdict(list)
        for release_mbid in releases:
            release = releases[release_mbid]
            for tnum, recording in enumerate(release["release"]):
                release_index[recording["recording_mbid"]].append((release, tnum))

        for (file, recording) in mapped:
            recording_mbid = recording["recording_mbid"]
            for release, tnum in release_index[recording_mbid]:
                rel_recording = release["release"][tnum]
                if "files" not in rel_recording:
                    rel_recording["files"] = []
                rel_recording["files"].append(file)

        stats = []
        for release_mbid in releases:
            total = 0
            file_count = 0
            for recording in releases[release_mbid]["release"]:
                if "files" in recording:
                    file_count += 1
                total += 1

            if file_count == 1:
                continue

            stats.append({
                "release": releases[release_mbid],
                "file_count": file_count,
                "total": total,
                "match": file_count / total,
            })

        last_rg = ""
        group = []
        for entry in sorted(stats, key=lambda i: (i["release"]["release_group_mbid"], i["release"]["release_mbid"], i["match"])):
            if last_rg != entry["release"]["release_group_mbid"]:
                self.evaluate_match(group)
                group = []

            group.append(entry)
            last_rg = entry["release"]["release_group_mbid"]

        if len(group) != 0:
            self.evaluate_match(group)

    def evaluate_match(self, release_candidates):
        release_candidates.sort(key=lambda i: i["release"]["release_group_mbid"])
        # Check for perfect matches
        for i, c in enumerate(release_candidates):
            if c["file_count"] == c["total"]:
                log.debug("FULL MATCH! (release group %s '%s')" %
                      (c["release"]["release_group_mbid"][:6], c["release"]["release_name"]))
                self.print_match(c)
                self.load_match(c)
                release_candidates.pop(i)
                return

    def print_match(self, release_candidate):
        for r in release_candidate["release"]["release"]:
            try:
                files = ",".join([str(f) for f in r["files"]])
            except KeyError:
                files = ""
            log.debug("%3d %3d %-40s %s" % (r["medium_position"], r["position"], r["recording_name"][:39], files))

    def load_match(self, release_candidate):
        release_mbid = release_candidate["release"]["release_mbid"]
        for track in release_candidate["release"]["release"]:
            for file in track["files"]:
                self.tagger.move_file_to_track(file,release_mbid, track["recording_mbid"])


autotag_lookup = AutoTagLookup()
register_cluster_action(autotag_lookup)
register_file_action(autotag_lookup)
