# -*- coding: utf-8 -*-

PLUGIN_NAME = 'Standardise Performers'
PLUGIN_AUTHOR = 'Sophist'
PLUGIN_DESCRIPTION = '''Splits multi-instrument performer tags into single
instruments and combines names so e.g. (from 10cc by 10cc track 1):
<pre>
Performer [acoustic guitar, bass, dobro, electric guitar and tambourine]: Graham Gouldman
Performer [acoustic guitar, electric guitar, grand piano and synthesizer]: Lol Creme
Performer [electric guitar, moog and slide guitar]: Eric Stewart
</pre>
becomes:
<pre>
Performer [acoustic guitar]: Graham Gouldman; Lol Creme
Performer [bass]: Graham Gouldman
Performer [dobro]: Graham Gouldman
Performer [electric guitar]: Eric Stewart; Graham Gouldman; Lol Creme
Performer [grand piano]: Lol Creme
Performer [moog]: Eric Stewart
Performer [slide guitar]: Eric Stewart
Performer [synthesizer]: Lol Creme
Performer [tambourine]: Graham Gouldman
</pre>
Update: This version now sorts the performer tags in order to maintain a consistent value and avoid tags appearing to change even though the base data is equivalent.
'''
PLUGIN_VERSION = '1.0'
PLUGIN_API_VERSIONS = ["2.0"]
PLUGIN_LICENSE = "GPL-2.0"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"

import re
from picard import log
from picard.metadata import register_track_metadata_processor

standardise_performers_split = re.compile(r", | and ").split


def standardise_performers(album, metadata, *args):
    for key, values in list(metadata.rawitems()):
        if not key.startswith('performer:') \
                and not key.startswith('~performersort:'):
            continue
        mainkey, subkey = key.split(':', 1)
        if not subkey:
            continue
        instruments = standardise_performers_split(subkey)
        if len(instruments) == 1:
            continue
        log.debug("%s: Splitting Performer [%s] into separate performers",
                  PLUGIN_NAME,
                  subkey,
                  )
        prefixes = []
        words = instruments[0].split()
        for word in words[:]:
            if not word in ['guest', 'solo', 'additional', 'minor']:
                break
            prefixes.append(word)
            words.remove(word)
        instruments[0] = " ".join(words)
        prefix = " ".join(prefixes) + " " if prefixes else ""
        for instrument in instruments:
            newkey = '%s:%s%s' % (mainkey, prefix, instrument)
            for value in values:
                metadata.add_unique(newkey, value)
        del metadata[key]

    # Sort performer metdata to avoid changes in processing sequence creating false changes in metadata
    for key, values in list(metadata.rawitems()):
        if key.startswith('performer:') or key.startswith('~performersort:'):
            metadata[key] = sorted(values)


from picard.plugin import PluginPriority
register_track_metadata_processor(standardise_performers,
                                  priority=PluginPriority.HIGH)
