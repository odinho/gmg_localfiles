#from sqlalchemy import event
#
#from mediagoblin.db.models import MediaEntry
#
#@event.listens_for(MediaEntry.collections, 'append')
#def test(target, value, initiator):
#    print "RECV event"
#    import ipdb; ipdb.set_trace()

import re

from mediagoblin import mg_globals as mgg

from .metadata import Metadata


def collection_to_rating(collection):
    m = re.match(r'rating:(\d+)', collection.title)
    if not m:
        return
    try:
        return int(m.group(1))
    except ValueError:
        return


def media_added_to_collection(collection, media_entry, note):
    rating = collection_to_rating(collection)
    if rating is None:
        return
    set_rating_from_media_entry(media_entry, rating)


def media_removed_from_collection(collection, media_entry):
    removed_rating = collection_to_rating(collection)
    if removed_rating is None:
        return
    for col in media_entry.collections:
        fallback_rating = collection_to_rating(col)
        if fallback_rating is not None:
            set_rating_from_media_entry(media_entry, fallback_rating,
                                        expect_rating=removed_rating)
            return
    set_rating_from_media_entry(media_entry, 0,
                                expect_rating=removed_rating)


def set_rating_from_media_entry(media_entry, rating, expect_rating=None):
    filepath = (mgg.public_store
                ._cachefile_to_original_filepath(
                    media_entry.media_files['original']))
    path = mgg.public_store._resolve_filepath(filepath)
    if expect_rating is not None:
        actual_rating = get_rating(path)
        if actual_rating != expect_rating:
            return False
    set_rating(path, rating)
    return True


def set_rating(path, rating):
    md = Metadata.from_potential_sidecar(path)
    md.rating = rating
    md.save()


def get_rating(path):
    md = Metadata.from_potential_sidecar(path)
    return md.rating
