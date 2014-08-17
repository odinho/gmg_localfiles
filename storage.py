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

import logging
import os
import re
import urlparse

from mediagoblin.storage import NoWebServing
from mediagoblin.storage.filestorage import BasicFileStorage


CACHE_DIR = 'mg_cache'
_log = logging.getLogger(__name__)


def _is_cachefile(filepath):
    if filepath and filepath[0] == CACHE_DIR:
        return True
    fn = filepath[-1].lower()
    return any(k in fn for k in ['.thumbnail.', '.medium.',
                                 '.nef.jpg', '.cr2.jpg'])


def _ensure_in_cache_dir(filepath):
    if filepath and filepath[0] == CACHE_DIR:
        return filepath
    return [CACHE_DIR] + list(filepath)


class PersistentFileStorage(BasicFileStorage):
    """
    Local filesystem implementation of storage API that doesn't delete files
    """

    def _resolve_filepath(self, filepath):
        """
        Transform the given filepath into a local filesystem path.

        Differences from filestorage:
          - If filename looks like a cache file, it will ensure
            that the path returned is in cache directory.
          - Check if the file exists, if it doesn't it will
            try using an uppercase extension.
        """
        if _is_cachefile(filepath):
            filepath = _ensure_in_cache_dir(filepath)
            path = os.path.join(self.base_dir, *filepath)
            return path

        # Sadly, since MediaGoblin always expect the file extension
        # to be lower case (it renames MyPic.JPG to MyPic.jpg),
        # we cannot be sure about what path we should return.
        #
        # So we have to check if the file exists on disk,
        # if it does not we should use the upper case
        # version of the name (if it's neither, you are
        # on your own).
        path = os.path.join(self.base_dir, *filepath)
        if os.path.exists(path):
            return path

        # The expected file didn't exist. GMG probably gave
        # us ".jpg", so let's return ".JPG"
        fn, ext = os.path.splitext(filepath[-1])
        filepath = list(filepath[:-1]) + [fn + ext.upper()]
        path = os.path.join(self.base_dir, *filepath)
        return path

    def file_url(self, filepath):
        """
        Takes filepath returns URL

        Differences from filestorage are two:
          - If the filepath looks like a cachefile, it'll use cache dir
          - It won't "clean" the filename of non-ascii letters
        """
        if not self.base_url:
            raise NoWebServing(
                "base_url not set, cannot provide file urls")
        if _is_cachefile(filepath):
            filepath = _ensure_in_cache_dir(filepath)

        return urlparse.urljoin(self.base_url, '/'.join(filepath))

    def get_file(self, filepath, mode='r'):
        if _is_cachefile(filepath):
            return super(PersistentFileStorage, self).get_file(filepath, mode)
        if not os.path.exists(self._resolve_filepath(filepath)):
            return PersistentStorageObjectWrapper(
                None, self._resolve_filepath(filepath))

        mode = mode.replace("w", "r")
        # Grab and return the file in the mode specified
        return PersistentStorageObjectWrapper(
                open(self._resolve_filepath(filepath), mode))

    def delete_file(self, filepath):
        _log.info(u'Not removing {0} as requested.'.format(
            self._resolve_filepath(filepath)))

    def delete_dir(self, dirpath, recursive=False):
        return False

    def copy_local_to_storage(self, filename, filepath):
        """
        Copy this file from locally to the storage system.
        """
        # Everything that mediagoblin possibly wants to create
        # should go in the cache dir.
        if _is_cachefile(filepath):
            filepath = _ensure_in_cache_dir(filepath)
            super(type(self), self).copy_local_to_storage(filename, filepath)
        else:
            _log.debug('Refusing to copy non-cache file path {}.'
                       ''.format(filepath))


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
