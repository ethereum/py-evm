import shutil
from .base import (
    BaseDB,
)


class LevelDB(BaseDB):

    # Creates db as a class variable to avoid level db lock error
    def __init__(self, db_path=None):
        if not db_path:
            raise TypeError("Please specifiy a valid path for your database.")
        try:
            import leveldb
        except ImportError:
            raise ImportError("LevelDB requires the leveldb \
                               library which is not available for import.")
        self.db_path = db_path
        self.db = leveldb.LevelDB(db_path, create_if_missing=True, error_if_exists=False)

    def get(self, key):
        # 'Get' Returns a bytearray which needs to be converted to straight bytes
        return bytes(self.db.Get(key))

    def set(self, key, value):
        self.db.Put(key, value)

    # Returns False instead of KeyError if key doesn't exist
    def exists(self, key):
        return bool(self.db.Get(key, default=False))

    def delete(self, key):
        self.db.Delete(key)

    #
    # Snapshot API
    #
    def snapshot(self):
        return Snapshot(self.db.CreateSnapshot())

    def revert(self, snapshot):
        for item in self.db.RangeIter(include_value=False):
            self.db.Delete(item)
        for key, val in snapshot.items():
            self.db.Put(key, val)

    # Clears the leveldb
    def __del__(self):
        shutil.rmtree(self.db_path, ignore_errors=True)


class Snapshot(object):
    def __init__(self, snapshot):
        self.db = snapshot

    def get(self, key):
        return self.db.Get(key)

    def items(self):
        return self.db.RangeIter(include_value=True, reverse=True)
