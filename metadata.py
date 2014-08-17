import os

import pyexiv2


class Metadata(object):
    lookups = {
        'rating': ('Xmp.xmp.Rating', ),
    }

    def __init__(self, path):
        self.path = path
        self.md = pyexiv2.ImageMetadata(path)
        self.dirty = False

        self.read()

    def read(self):
        self.md.read()

    def save(self):
        if self.dirty:
            self.md.write()
            self.dirty = False

    def _get_metadata_item(self, lookup):
        existing_keys = self.md.keys()
        for key in self.lookups[lookup]:
            if key in existing_keys:
                return self.md.get(key)

    @property
    def rating(self):
        tag = self._get_metadata_item('rating')
        return tag.value if tag else None

    @rating.setter
    def rating(self, value):
        tag = self._get_metadata_item('rating')
        if tag is None:
            tag_key = self.lookups['rating'][0]
            tag = pyexiv2.XmpTag(tag_key, value)
            self.md[tag_key] = tag
        else:
            tag.value = value
        self.dirty = True

    @classmethod
    def from_potential_sidecar(self, filepath):
        xmp_filepath = u'{}.xmp'.format(filepath)
        if os.path.exists(xmp_filepath):
            return Metadata(xmp_filepath)
        return Metadata(filepath)


if __name__ == '__main__':
    import sys
    path = sys.argv[1].decode('utf8')
    md = Metadata.from_potential_sidecar(path)
    print md.path
    print u"  rating:", md.rating
    if len(sys.argv) > 2:
        md.rating = int(sys.argv[2])
        md.save()
        print u"  set rating to:", md.rating
