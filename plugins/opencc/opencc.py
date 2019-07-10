# coding: utf-8
# Copyright 2014-2015 Hsiaoming Yang <me@lepture.com>
# Copyright 2019 Philipp Wolfer <ph.wolfer@gmail.com>
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
# * Neither the name of the creator nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; # OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import absolute_import, unicode_literals
import os
import sys
from ctypes.util import find_library
from ctypes import CDLL, cast, c_char_p, c_size_t, c_void_p

if sys.version_info[0] == 3:
    text_type = str
else:
    text_type = unicode

__all__ = ['CONFIGS', 'convert', 'OpenCC']
__version__ = '0.2'
__author__ = 'Hsiaoming Yang <me@lepture.com>'

_libopenccfile = ''
if sys.platform == 'win32':
    moddir = os.path.dirname(__file__)
    parentdir = os.path.dirname(moddir)
    # Extract DLL from ZIP file
    if parentdir.endswith('.zip'):
        import tempfile
        import zipfile
        archive = zipfile.ZipFile(parentdir)
        with archive.open('opencc/opencc.dll') as openccdll:
            (fd, _libopenccfile) = tempfile.mkstemp(suffix='.dll')
            with os.fdopen(fd, 'wb') as tempdll:
                tempdll.write(openccdll.read())
    else:
        _libopenccfile = os.path.join(moddir, 'opencc')
else:
    _libopenccfile = os.getenv('LIBOPENCC') or find_library('opencc')
    if not _libopenccfile:
        _libopenccfile = 'libopencc.so.1'

libopencc = CDLL(_libopenccfile, use_errno=True)

libopencc.opencc_open.restype = c_void_p
libopencc.opencc_convert_utf8.argtypes = [c_void_p, c_char_p, c_size_t]
libopencc.opencc_convert_utf8.restype = c_void_p
libopencc.opencc_close.argtypes = [c_void_p]

CONFIGS = [
    'hk2s.json', 's2hk.json',
    's2t.json', 's2tw.json', 's2twp.json',
    't2s.json', 'tw2s.json', 'tw2sp.json',
    't2tw.json', 't2hk.json',
]


class OpenCC(object):

    def __init__(self, config='t2s.json'):
        self._od = libopencc.opencc_open(c_char_p(config.encode('utf-8')))

    def convert(self, text):
        if isinstance(text, text_type):
            # use bytes
            text = text.encode('utf-8')

        retv_i = libopencc.opencc_convert_utf8(self._od, text, len(text))
        if retv_i == -1:
            raise Exception('OpenCC Convert Error')
        retv_c = cast(retv_i, c_char_p)
        value = retv_c.value
        libopencc.opencc_convert_utf8_free(retv_c)
        return value.decode('utf-8')

    def __del__(self):
        libopencc.opencc_close(self._od)


def convert(text, config='t2s.json'):
    cc = OpenCC(config)
    return cc.convert(text)
