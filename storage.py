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

from mediagoblin.storage import (
    clean_listy_filepath,
    NoWebServing)
from mediagoblin.storage.filestorage import BasicFileStorage

import os
import shutil
import logging
import urlparse

_log = logging.getLogger(__name__)

def _is_cachefile(filepath):
    if not isinstance(filepath, basestring):
        filepath = filepath[-1]
    return any(k in filepath for k in ['thumbnail', 'medium'])

class PersistentFileStorage(BasicFileStorage):
    """
    Local filesystem implementation of storage API that doesn't delete files
    """

    def _resolve_filepath(self, filepath, force_cache=False):
        """
        Transform the given filepath into a local filesystem filepath.
        """
        if _is_cachefile(filepath) or force_cache:
            filepath = clean_listy_filepath(list(filepath))
            filepath.insert(0, "mg_cache")

        return os.path.join(
            self.base_dir, *filepath)

    def file_url(self, filepath):
        if not self.base_url:
            raise NoWebServing(
                "base_url not set, cannot provide file urls")

        if _is_cachefile(filepath):
            filepath = clean_listy_filepath(list(filepath))
            filepath.insert(0, "mg_cache")

        return urlparse.urljoin(
            self.base_url,
            '/'.join(filepath))

    def get_file(self, filepath, mode='r'):
        if _is_cachefile(filepath):
            return super(PersistentFileStorage, self).get_file(filepath, mode)
        if not os.path.exists(self._resolve_filepath(filepath)):
            return PersistentStorageObjectWrapper(None, self._resolve_filepath(filepath))

        mode = mode.replace("w", "r")
        # Grab and return the file in the mode specified
        return PersistentStorageObjectWrapper(
                open(self._resolve_filepath(filepath), mode))

    def delete_file(self, filepath):
        #os.remove(self._resolve_filepath(filepath))
        _log.info(u'Not removing {0} as requested.'.format(self._resolve_filepath(filepath)))

    def delete_dir(self, dirpath, recursive=False):
        return False

    def copy_local_to_storage(self, filename, filepath):
        """
        Copy this file from locally to the storage system.
        """
        # Make directories if necessary
        if len(filepath) > 1:
            directory = self._resolve_filepath(filepath[:-1], force_cache=True)
            if not os.path.exists(directory):
                os.makedirs(directory)

        shutil.copy(filename, self.get_local_path(filepath))

class PersistentStorageObjectWrapper():
    def __init__(self, storage_object, name=None, *args, **kwargs):
        self.storage_object = storage_object
        self.name = name
        if storage_object:
            self.name = storage_object.name

    def read(self, *args, **kwargs):
        _log.debug(u'Reading {0}'.format(
            self.name).encode("utf-8"))
        return self.storage_object.read(*args, **kwargs)

    def write(self, data, *args, **kwargs):
        _log.debug(u'Not writing {0}'.format(
            self.name).encode("utf-8"))

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
