#!/usr/bin/env python
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

import codecs
import os
import sys
import uuid

# This is here early because of a race
import mediagoblin
from mediagoblin.app import MediaGoblinApp
from mediagoblin import mg_globals

if __name__ == "__main__":
    mg_dir = os.path.dirname(mediagoblin.__path__[0])
    if os.path.exists(mg_dir + "/mediagoblin_local.ini"):
        config_file = mg_dir + "/mediagoblin_local.ini"
    elif os.path.exists(mg_dir + "/mediagoblin.ini"):
        config_file = mg_dir + "/mediagoblin.ini"
    else:
        raise Exception("Couldn't find mediagoblin.ini")

    mg_app = MediaGoblinApp(config_file, setup_celery=True)

    from mediagoblin.init.celery import setup_celery_app
    setup_celery_app(
        mg_globals.app_config,
        mg_globals.global_config,
        force_celery_always_eager=True)

import sqlalchemy.exc
from mediagoblin.db.base import Session
from mediagoblin.media_types import FileTypeNotSupported
from mediagoblin.media_types import get_media_type_and_manager
from mediagoblin.submit.lib import run_process_media
from mediagoblin.tools.text import convert_to_tag_list_of_dicts
from mediagoblin.user_pages.lib import add_media_to_collection

from . import ratings


CACHE_DIR = 'mg_cache'


class MockMedia():
    filename = ""
    stream = None

    def __init__(self, filename, stream):
        self.filename = filename
        self.stream = stream

    def read(self, *args, **kwargs):
        return self.stream.read(*args, **kwargs)


class ImportCommand(object):
    help = 'Find new photos and add to database'

    def __init__(self, db, base_dir, **kwargs):
        self.db = db
        self.base_dir = base_dir

    def handle(self):
        #Photo.objects.all().delete()

        os.chdir(self.base_dir)

        for top, dirs, files in os.walk('.', followlinks=True):
            dirs.sort()
            # Skip hidden folders
            if '/.' in top:
                continue
            # Skip cache folders
            if CACHE_DIR + '/' in top:
                continue
            if top == '.':
                top = u''

            #folder, new_folder = Folder.objects.select_related("photos") \
            #        .get_or_create(path=os.path.normpath(top) + "/",
            #                defaults={'name': os.path.basename(top)})
            folder_path = os.path.normpath(top.decode('utf8'))
            new_folder = not os.path.exists(
                os.path.join(CACHE_DIR, folder_path))

            if new_folder:
                print u"Processing folder {0}".format(folder_path)
            else:
                print u"Existing folder {0}".format(folder_path)
                continue

            added_entries = []
            for new_filename in sorted(files, reverse=True):
                fn, ext = os.path.splitext(new_filename)
                if fn.lower().endswith('.nef'):
                    # If the file name *without the extensions* ends with .nef,
                    # we are probably dealing with some product of the nef.
                    # Either the .nef.xmp, or the extracted .nef.jpg.
                    # Let's just ignore it.
                    continue
                if ext.lower() == '.nef' and fn + '.jpg' in files:
                    # If we're a nef file, and we have a similar named
                    # jpg in the same place.  We'll prefer the jpg, because
                    # it might be a processed raw image.
                    print "Skipping {}, found jpeg candidate.".format(new_filename)
                    continue
                path = os.path.join(folder_path, new_filename.decode('utf8'))
                second_exception = False

                while True:
                    try:
                        entry = self.import_file(MockMedia(
                            filename=path, stream=open(path, 'r')))
                        break
                    except (sqlalchemy.exc.InvalidRequestError,
                            sqlalchemy.exc.OperationalError) as exc:
                        if not second_exception:
                            print (u"[imp] Exception while importing file "
                                   "'{0}': {1}. Trying again."
                                   "".format(path, repr(exc)))
                            second_exception = True
                        else:
                            print u"[imp] Giving up on {0}.".format(path)
                            print u"Entries is this folder {0}: {1}".format(
                                folder_path, [e.id for e in added_entries])
                            raise
                    except Exception as exc:
                        print(u"[imp] Exception while importing "
                              "file '{0}': {1}.".format(path, repr(exc)))
                        break
                if not entry:
                    continue
                added_entries.append(entry)
                rating = ratings.get_rating(path)
                if rating:
                    self.add_to_collection('rating:{}'.format(rating),
                                           [entry])
            self.add_to_collection(u'roll:{}'.format(folder_path),
                                   added_entries)

    def add_to_collection(self, collection_title, entries):
        if not entries:
            return
        collection = (self.db.Collection.query
                      .filter_by(creator=1, title=collection_title)
                      .first())
        if not collection:
            collection = self.db.Collection()
            collection.title = collection_title
            collection.creator = 1
            collection.generate_slug()
            collection.save()
            Session.commit()
        for entry in entries:
            add_media_to_collection(collection, entry, commit=False)
        try:
            Session.commit()
        except Exception as exc:
            print (u"Could add media to collection {}: {}"
                   "".format(collection_title, exc))
            Session.rollback()

    def import_file(self, media):
        try:
            media_type, media_manager = (
                get_media_type_and_manager(media.filename))
        except FileTypeNotSupported:
            print u"File type not supported: {0}".format(media.filename)
            return
        entry = self.db.MediaEntry()
        entry.media_type = unicode(media_type)
        entry.title = unicode(
            os.path.basename(os.path.splitext(media.filename)[0]))

        entry.uploader = 1
        # Process the user's folksonomy "tags"
        entry.tags = convert_to_tag_list_of_dicts("")
        # Generate a slug from the title
        entry.generate_slug()

        task_id = unicode(uuid.uuid4())
        entry.queued_media_file = media.filename.split("/")
        entry.queued_task_id = task_id

        try:
            entry.save()
            run_process_media(entry)
            Session.commit()
        except Exception:
            Session.rollback()
            raise
        return entry


if __name__ == "__main__":
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)

    ic = ImportCommand(
        mg_app.db,
        mg_globals.global_config['storage:publicstore']['base_dir'])
    ic.handle()

    print
    print "Import finished"
