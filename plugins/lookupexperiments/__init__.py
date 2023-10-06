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
from picard.config import get_config
from picard.file import File
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



class ReleaseDetails:
    def __init__(self, mbid, title, rgid, tracks=None) -> None:
        self.mbid = mbid
        self.title = title
        self.rgid = rgid
        self.tracks = tracks or []

    @property
    def similarity(self):
        sim = min(1.0, self.matched_tracks_count / self.track_count)
        if self.tracks:
            sim *= sum(t.similarity for t in self.tracks) / len(self.tracks)
        return sim

    @property
    def track_count(self):
        return len(self.tracks)

    @property
    def matched_tracks_count(self):
        count = 0
        for track in self.tracks:
            if track.files:
                count += 1
        return count

    @property
    def file_count(self):
        count = 0
        for track in self.tracks:
            count += len(track.files)
        return count

    @property
    def files(self):
        for track in self.tracks:
            yield from track.files

    @property
    def data(self):
        return {
            'id': self.mbid,
            'title': self.title,
            'release-group': {
                'id': self.rgid
            },
            'artist-credits': [{
                # 'artist': self.artist
            }],
            'track-count': self.track_count,
            'media': list(self._medium_data())
        }

    def _medium_data(self):
        track_count = 0
        current_discnumber = 1
        for track in self.tracks:
            if track.discnumber != current_discnumber:
                yield {
                    'track-count': track_count
                }
                track_count = 0
            track_count += 1
        yield {
            'track-count': track_count
        }


    def __repr__(self) -> str:
        return (f"<ReleaseDetails {self.mbid}, similarity={self.similarity}, "
                f"track_count={self.track_count}, file_count={self.file_count}>")


class TrackDetails:
    def __init__(self, mbid, title, artist, duration, tracknumber, discnumber, release_data):
        self.mbid = mbid
        self.title = title
        self.artist = artist
        self.duration = duration
        self.tracknumber = tracknumber
        self.discnumber = discnumber
        self.release_data = release_data
        self.files = []

    @property
    def data(self):
        return {
            'title': self.title,
            'artist-credits': [{
                'artist': self.artist
            }],
            'releases': [self.release_data],
            'length': self.duration or 0,
        }

    @property
    def similarity(self):
        if not self.files:
            return 0.5  # Give it a penalty for missing file
        sim = 1.0
        sim *= sorted(self.get_file_similarities(), key=lambda s: s[0])[0][0]
        return sim

    def get_file_similarities(self):
        data = self.data
        return (
            (self.file_similarity(file, data), file)
            for file in self.files
        )

    def file_similarity(self, file, data=None):
        if not data:
            data = self.data
        return file.metadata.compare_to_track(data, File.comparison_weights).similarity

    def __repr__(self) -> str:
        return (f"<TrackDetails {self.mbid}, similarity={self.similarity}, "
                f"file_count={len(self.files)}>")

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

    MAPPING_BATCH_SIZE = 1000
    RELEASES_BATCH_SIZE = 1000
    AUTOTAG_SIMILARITY_THRESHOLD = 0.25

    def __init__(self):
        super().__init__()
        self.releases = {}

    @staticmethod
    def filter_files(files):
        for f in files:
            m = f.metadata
            if m['artist'] and m['title'] and m['album']:
                yield f

    def callback(self, objs):
        files = list(self.filter_files(iter_files_from_objects(objs, save=True)))
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
            "[artist_credit_name]": f.metadata["artist"] or f.metadata["albumartist"],
            "[recording_name]": f.metadata["title"],
            "[release_name]": f.metadata["album"],
        } for f in batch]
        self.webservice.post(
            LISTENBRAINZ_LABS_HOST,
            LISTENBRAINZ_LABS_PORT,
            '/mbid-mapping-release/json',
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
        if not mapped:
            log.warning('AutoTagLookup: could not map any files')
            return
        log.info(f'AutoTagLookup: mapped {len(mapped)}, unidentified {len(unidentified)}')
        self.load_releases(mapped, 0, unidentified, releases={})

    def load_releases(self, mapped, index, unidentified, releases):
        batch = mapped[index:index + self.RELEASES_BATCH_SIZE]
        if not batch:
            self.after_load_releases(mapped, unidentified, releases)
            return

        post_data = [{"[recording_mbid]": m['recording_mbid']} for f, m in batch]
        self.webservice.post(
            LISTENBRAINZ_DATASETS_HOST,
            LISTENBRAINZ_DATASETS_PORT,
            '/releases-from-recordings/json',
            json.dumps(post_data),
            partial(self.load_releases_finished, mapped, index, unidentified, releases),
            priority=True,
            important=False,
            parse_response_type='json',
            request_mimetype="application/json")

    def get_recording_details(self, recordings, release_data):
        for recording in recordings:
            yield TrackDetails(*recording, release_data)

    def get_release_details(self, data):
        for release_group in data:
            rgid = release_group.get('release_group_mbid')
            for mbid, release in release_group.get('releases', {}).items():
                title = release.get('release_name', '')
                release_details = ReleaseDetails(mbid, title, rgid)
                release_details.tracks = list(
                    self.get_recording_details(release.get('recordings', []), release_details.data)
                )
                yield release_details

    def load_releases_finished(self, mapped, index, unidentified, releases, data, reply, error):
        if error:
            log.error("AutoTagLookup: could not load releases: %s", error)
            self.after_load_releases(mapped, unidentified, None)
            self.clear_pending((f for f, m in mapped))
            return
        for release in self.get_release_details(data):
            if release.mbid not in releases:
                releases[release.mbid] = release
        self.load_releases(mapped, index + self.RELEASES_BATCH_SIZE, unidentified, releases)

    def after_load_releases(self, mapped, unidentified, releases):
        if not releases:
            log.warning('AutoTagLookup: could not load releases')
            return
        self.load_recordings_into_releases(mapped, unidentified, releases.values())

    def load_recordings_into_releases(self, mapped, unidentified, releases: list[ReleaseDetails]):
        release_index = defaultdict(list)
        for release in releases:
            for recording in release.tracks:
                release_index[recording.mbid].append((release, recording.tracknumber))

        for (file, recording) in mapped:
            recording_mbid = recording["recording_mbid"]
            for release, tnum in release_index[recording_mbid]:
                rel_recording = release.tracks[tnum - 1]
                if file not in rel_recording.files:
                    rel_recording.files.append(file)

        mapped_files = list(f for f, t in mapped)
        self.fill_holes(unidentified, releases, mapped_files)

        # self.print_matches(releases)
        matches = self.clean_matches(releases)
        self.print_matches(matches)
        while match := self.evaluate_match(matches):
            self.load_match(match)
            matches = self.clean_matches(matches, match)
            self.print_matches(matches)

        # Clear the pending here for all files
        self.clear_pending(mapped_files)

    def fill_holes(self, unidentified, releases, mapped_files):
        """Try to match unidentified files to tracks without matched files"""
        config = get_config()
        threshold = config.setting['track_matching_threshold']
        for file in list(unidentified):
            for release in releases:
                for track in release.tracks:
                    if track.file_similarity(file) > threshold:
                        log.info("AutoTagLookup: match previously unidentified file %r -> %r" % (file, track))
                        track.files.append(file)
                        mapped_files.append(file)
                        if file in unidentified:
                            unidentified.remove(file)

        # Still some left? Ignore
        if unidentified:
            self.clear_pending(unidentified)

    def print_matches(self, matches: list[ReleaseDetails]):
        print("===")
        print(f"MATCHES {len(matches)}:")
        for release in matches:
            print(release)
        print("===")

    def clean_matches(self, matches: list[ReleaseDetails], processed_match: ReleaseDetails=None):
        if processed_match:
            matches.remove(processed_match)
            self.clear_pending(processed_match.files)
            for f in processed_match.files:
                for m in matches:
                    for t in m.tracks:
                        if f in t.files:
                            t.files.remove(f)
        if not matches:
            return matches
        return sorted(
            (m for m in matches if m.similarity >= self.AUTOTAG_SIMILARITY_THRESHOLD),
            key=lambda r: r.similarity,
            reverse=True)

    def evaluate_match(self, matches: list[ReleaseDetails]):
        if matches:
            return matches[0]
        return None

    def load_match(self, release: ReleaseDetails):
        # Only use the best matching files
        for track in release.tracks:
            if track.files:
                sims = list(track.get_file_similarities())
                max_sim = max(sim[0] for sim in sims)
                for sim, file in sims:
                    if sim < max_sim:
                        track.files.remove(file)
        self.tagger.move_files_to_album(release.files, release.mbid)


autotag_lookup = AutoTagLookup()
register_cluster_action(autotag_lookup)
register_file_action(autotag_lookup)
