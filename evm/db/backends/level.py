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
