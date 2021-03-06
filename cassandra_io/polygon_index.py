import re
import json

from rtree import index
from shapely import geometry

import hashlib


def hash_string(string):
    h = hashlib.md5()
    h.update(string.encode('utf-8'))
    return int(h.hexdigest(), 16)


class Polygon_File_Index:

    def __init__(self):
        """A spatial file index for polygon areas boosted by an R-Tree

        The index contains unique 'file' fields.

        """
        self._polygons = dict()
        self._rtree = index.Index()


    def _check_data(self, data):
        if 'file' not in data:
            raise RuntimeError("'file' not in data")
        if 'polygon' not in data:
            raise RuntimeError("'polygon' not in data")


    def insert(self, data):
        """Insert a polygon area to the index

        :data: a dictionary containing at least 'file' and 'polygon'
        fields. polygon is a list of tuple coordinates. A polygon
        definition is given here:
        https://shapely.readthedocs.io/en/latest/manual.html#polygons

        """
        self._check_data(data)

        if data['file'] in self._polygons:
            return

        pl = geometry.Polygon(data['polygon'])
        self._polygons[data['file']] = pl
        self._rtree.insert(hash_string(data['file']),
                           pl.bounds,
                           obj = data)


    def update(self, data):
        """Update index with a new data

        :data: same as in self.insert

        """
        self._check_data(data)

        if data['file'] not in self._polygons:
            self.insert(data)
            return True

        pl = self._polygons[data['file']]
        if pl.almost_equals(geometry.Polygon(data['polygon'])):
            return False

        self._rtree.delete(hash_string(data['file']), pl.bounds)
        del self._polygons[data['file']]
        self.insert(data)
        return True


    def nearest(self, point):
        """Yield index data that contain a given point

        :point: a tuple with the same coordinate convention as used in
        .insert method for polygon tuples.
        A point definition is given here:
        https://shapely.readthedocs.io/en/latest/manual.html#points

        """
        for data in self._rtree.nearest(point, 1, objects='raw'):
            if self._polygons[data['file']]\
                   .intersects(geometry.Point(point)):
                yield data


    def intersect(self, polygon):
        """Intersect index with a polygon

        :polygon: list of tuple coordinates

        :return: smaller Polygon_File_Index
        """
        res = Polygon_File_Index()
        polygon = geometry.Polygon(polygon)

        if not self._rtree.get_size():
            return res

        for data in self._rtree.intersection(polygon.bounds,
                                             objects='raw'):
            schnitt = polygon.intersection\
                (self._polygons[data['file']])

            if schnitt.is_empty \
               or not isinstance(schnitt, geometry.Polygon):
                continue

            new_data = data
            new_data.update({'polygon': \
                             list(schnitt.exterior.coords)})
            res.insert(new_data)

        return res


    def filter(self, how = lambda x: True):
        res = Polygon_File_Index()

        if not self._rtree.get_size():
            return res

        for data in self._rtree.intersection\
            (self._rtree.bounds, objects='raw'):
            if how(data):
                res.insert(data)

        return res


    def size(self):
        return self._rtree.get_size()


    def save(self, fn):
        """Save index to a json file

        :fn: path to a file

        """
        data = []
        for x in self._rtree.intersection(self._rtree.bounds,
                                          objects = True):
            data += [{'id': x.id,
                      'bbox': x.bbox,
                      'object': x.object}]

        with open(fn, 'w') as f:
            json.dump(data, f)


    def load(self, fn):
        """Load index from a json file

        :fn: path to a file

        """
        with open(fn, 'r') as f:
            for x in json.load(f):
                try:
                    self._check_data(x['object'])
                except:
                    continue

                self._rtree.insert\
                    (x['id'], x['bbox'],
                     obj = x['object'])
                self._polygons[x['object']['file']] = \
                    geometry.Polygon(x['object']['polygon'])


    def files(self, what = 'file'):
        """Generator for files

        """
        if not self._rtree.get_size():
            yield from ()

        for data in self._rtree.intersection(self._rtree.bounds,
                                             objects = 'raw'):
            if what in data:
                yield data[what]
            else:
                yield None


    def iterate(self):
        if not self._rtree.get_size():
            yield from ()

        for data in self._rtree.intersection(self._rtree.bounds,
                                             objects = 'raw'):
            yield data
