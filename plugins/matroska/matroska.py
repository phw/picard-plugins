# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Philipp Wolfer
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from mutagen import (
    FileType,
    Metadata,
    StreamInfo,
)
from mutagen._util import (
    DictProxy,
    MutagenError,
    convert_error,
    loadfile,
)

from .ebml.container import File
from .ebml.data_elements import (
    ElementMaster,
    ElementSimpleTag,
    ElementTag,
)


class error(MutagenError):
    pass


class EbmlInfo(StreamInfo):
    """EbmlInfo()
    Ebml audio stream information.
    Information is parsed from the COMM chunk of the Ebml file
    Attributes:
        length (`float`): audio length, in seconds
        bitrate (`int`): audio bitrate, in bits per second
        channels (`int`): The number of audio channels
        bits_per_sample (`int`): bits per sample
        doc_type (`str`): EBML doc type (e.g. matroska or webm)
    """

    length = 0
    bitrate = 0
    channels = 0
    sample_rate = 0
    bits_per_sample = 0
    doc_type = None

    def __init__(self, ebml_file, segment):
        self.length = segment.duration
        ebml = ebml_file.child_named('EBML')
        self.doc_type = ebml.doc_type
        tracks = segment.tracks_bytype
        if 'audio' in tracks:
            first_audio = tracks['audio'][0].audio
            self.bits_per_sample = first_audio.bit_depth or 0
            self.channels = first_audio.channels or 0
            self.sample_rate = first_audio.sampling_frequency or 0

    def pprint(self):
        return u"%d channel EBML (%s) @ %d bits, %d Hz, %.2f seconds" % (
            self.channels, self.doc_type, self.bits_per_sample,
            self.sample_rate, self.length)


class EbmlTags(DictProxy, Metadata):
    @loadfile()
    @convert_error(IOError, error)
    def load(self, filething):
        ebml_file = File(filething.fileobj)
        segment = ebml_file.child_named('Segment')
        # print(ebml_file.summary())
        self.info = EbmlInfo(ebml_file, segment)
        tags_list = segment.child_named('Tags')
        tags = self._find_file_tags(tags_list)
        if tags:
            self._read_tags(tags)

    @loadfile(writable=True, create=True)
    @convert_error(IOError, error)
    def save(self, filething=None):
        ebml_file = File(filething.fileobj)
        ebml = ebml_file.child_named('EBML')
        segment = ebml_file.child_named('Segment')
        tags_list = segment.child_named('Tags')
        if not tags_list:
            tags_list = ElementMaster.new('Tags', segment, 0)
        tags = self._find_file_tags(tags_list)
        if not tags:
            tags = ElementTag.new_with_value(50, 'ALBUM', parent=tags_list)
        self._write_tags(tags)
        segment.normalize()
        ebml_file.rearrange()
        ebml_file.save_changes(filething.fileobj)

    def __setitem__(self, key, value):
        if not isinstance(value, ElementSimpleTag):
            value = ElementSimpleTag.new_with_value(key, value)
        super().__setitem__(key, value)

    @staticmethod
    def _find_file_tags(tags):
        if not tags:
            return None
        for child in tags.children_named('Tag'):
            # Search for a tag with target type 50 (album level)
            # without target elements (applies to entire file).
            # FIXME: Allow setting tags for other target types
            # (e.g. track level)
            if child.target_type_value == 50 and len(child.targets) == 0:
                return child
        return None

    def _read_tags(self, element_tag):
        for simple_tag in element_tag.simple_tags:
            if simple_tag.string_val:
                self[simple_tag.tag_name] = simple_tag

    def _write_tags(self, element_tag):
        existing_keys = set()
        # Update existing tags
        for simple_tag in element_tag.simple_tags:
            name = simple_tag.tag_name
            if name in self:
                existing_keys.add(name)
                if self[name].binary_val:
                    simple_tag.binary_val = self[name].binary_val
                else:
                    simple_tag.string_val = self[name].string_val
                simple_tag.language = self[name].language
        # Add new tags
        new_keys = set(self.keys()).difference(existing_keys)
        for name in new_keys:
            element_tag.add_child(self[name])


class EbmlFile(FileType):
    """EbmlFile(filething)
    An EBML file.
    Arguments:
        filething (filething)
    Attributes:
        tags (`EbmlTags`)
        info (`EbmlInfo`)
    """

    def load(self, filething):
        self.tags = EbmlTags(filething)
        self.info = self.tags.info

    @staticmethod
    def score(filename, fileobj, header):
        return header.startswith(b'\x1a\x45\xdf\xa3')
