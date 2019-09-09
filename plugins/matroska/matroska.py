from mutagen import (
    FileType,
    Metadata,
)
from mutagen._util import (
    DictProxy,
    loadfile,
)

from .ebml.container import File
from .ebml.data_elements import ElementSimpleTag


class EbmlTags(DictProxy, Metadata):
    @loadfile()
    def load(self, filething):
        ebml_file = File(filething.fileobj)
        # print(ebml_file.summary())
        tags = self._find_tags(ebml_file)
        if tags:
            self._read_tags(tags)

    @loadfile(writable=True, create=True)
    def save(self, filething=None):
        ebml_file = File(filething.fileobj)
        tags = self._find_tags(ebml_file)
        if tags:
            self._write_tags(tags)
            ebml_file.save_changes(filething.fileobj)

    def __setitem__(self, key, value):
        if not isinstance(value, ElementSimpleTag):
            value = ElementSimpleTag.new_with_value(key, value)
        super().__setitem__(key, value)

    @staticmethod
    def _find_tags(ebml_file):
        segment = next(ebml_file.children_named('Segment'))
        tags = next(segment.children_named('Tags'))
        for child in tags:
            # Search for a tag with target type 50 (album level)
            # without target elements (applies to entire file).
            # FIXME: Allow setting tags for other target types (e.g. track level)
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

    @staticmethod
    def score(filename, fileobj, header):
        return header.startswith(b'\x1a\x45\xdf\xa3')
