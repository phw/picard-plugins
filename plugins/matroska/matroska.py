from mutagen import (
    FileType,
    Metadata,
    StreamInfo,
)
from mutagen._util import (
    DictProxy,
    loadfile,
)

from .ebml.container import File
from .ebml.data_elements import ElementSimpleTag


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
        ebml_master = next(ebml_file.children_named('EBML'))
        self.doc_type = ebml_master.doc_type
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
    def load(self, filething):
        ebml_file = File(filething.fileobj)
        segment = next(ebml_file.children_named('Segment'))
        # print(ebml_file.summary())
        self.info = EbmlInfo(ebml_file, segment)
        tags_list = self._try_get_child(segment, 'Tags') or []
        tags = self._find_file_tags(tags_list)
        if tags:
            self._read_tags(tags)

    @loadfile(writable=True, create=True)
    def save(self, filething=None):
        ebml_file = File(filething.fileobj)
        segment = next(ebml_file.children_named('Segment'))
        tags_list = self._try_get_child(segment, 'Tags') or []
        tags = self._find_file_tags(tags_list)
        self._write_tags(tags)
        ebml_file.save_changes(filething.fileobj)

    def __setitem__(self, key, value):
        if not isinstance(value, ElementSimpleTag):
            value = ElementSimpleTag.new_with_value(key, value)
        super().__setitem__(key, value)

    @staticmethod
    def _find_file_tags(tags):
        for child in tags:
            # Search for a tag with target type 50 (album level)
            # without target elements (applies to entire file).
            # FIXME: Allow setting tags for other target types (e.g. track level)
            if child.target_type_value == 50 and len(child.targets) == 0:
                return child
        return None

    @staticmethod
    def _try_get_child(element, child_name):
        try:
            return next(element.children_named(child_name))
        except StopIteration:
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
