from .base import (
    BaseDB,
)


class LevelDB(BaseDB):

    # Creates db as a class variable to avoid level db lock error
    def __init__(self, db_path=None):
        if not db_path:
            raise TypeError("Please specifiy a valid path for your database.")
        try:
            import plyvel
        except ImportError:
            raise ImportError("LevelDB requires the plyvel \
                               library which is not available for import.")
        self.db_path = db_path
        self.db = plyvel.DB(db_path, create_if_missing=True, error_if_exists=False)

    def get(self, key):
        v = self.db.get(key)
        if v is None:
            raise KeyError(key)
        return v

    def set(self, key, value):
        self.db.put(key, value)

    def exists(self, key):
        return self.db.get(key) is not None

    def delete(self, key):
        self.db.delete(key)
