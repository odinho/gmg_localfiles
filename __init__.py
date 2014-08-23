# -*- coding: utf-8 -*-
#
# GMG localfiles plugin -- local file import
# Copyright (C) 2012 Odin Hørthe Omdal
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import logging

from mediagoblin import processing

from . import ratings
from .storage import _is_cachefile, _ensure_in_cache_dir


_log = logging.getLogger(__name__)


# Monkeypatch create_pub_filepath to not clean the original files, and to
# rather use queued_media_file instead of hardcoded path.
def monkey_create_pub_filepath(entry, filename):
    filepath = list(entry.queued_media_file)
    if _is_cachefile([filename]):
        filepath[-1] = filename
        filepath = _ensure_in_cache_dir(filepath)

    return filepath
processing.create_pub_filepath = monkey_create_pub_filepath


# TODO This does not work as written with raw files since
#      that media type creates its own FilenameBuilder.
class PreservingFilenameBuilder(processing.FilenameBuilder):
    def __init__(self, path):
        """Initialize a builder from an original file path."""
        self.dirpath, self.basename = os.path.split(path)
        self.basename, self.ext = os.path.splitext(self.basename)

    def fill(self, fmtstr):
        basename_len = (self.MAX_FILENAME_LENGTH -
                        len(fmtstr.format(basename='', ext=self.ext)))
        ext = self.ext
        if _is_cachefile([fmtstr]):
            ext = ext.lower()
        return fmtstr.format(basename=self.basename[:basename_len],
                             ext=ext)
processing.FilenameBuilder = PreservingFilenameBuilder


def setup_plugin():
    _log.info('LocalFiles plugin set up!')


hooks = {
    'add_media_to_collection': ratings.media_added_to_collection,
    'remove_media_from_collection': ratings.media_removed_from_collection,
    'setup': setup_plugin,
    }
