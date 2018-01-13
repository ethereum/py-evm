from .backends.base import BaseDB


class AccessLogs(object):
    reads = None
    writes = None

    def __init__(self, reads=None, writes=None):
        if reads is None:
            self.reads = {}
        else:
            self.reads = reads
        if writes is None:
            self.writes = {}
        else:
            self.writes = writes


class TrackedDB(BaseDB):
    """
    The StateDB would be responsible for collecting all the touched keys.

    access_logs.reads: the dict of read key-value
    access_logs.writes: the dict of written key-value
    """

    wrapped_db = None
    access_logs = None

    def __init__(self, db):
        self.wrapped_db = db
        self.access_logs = AccessLogs()

    def get(self, key):
        """
        Return the value of specific key and update read dict.
        """
        current_value = self.wrapped_db.get(key)
        self.access_logs.reads[key] = current_value
        return current_value

    def set(self, key, value):
        """
        Set the key-value and update writes dict.
        """
        self.access_logs.writes[key] = value
        return self.wrapped_db.set(key, value)

    def exists(self, key):
        """
        Check if the key exsits.
        """
        result = self.wrapped_db.exists(key)
        self.access_logs.reads[key] = self.wrapped_db.get(key) if result else None
        return result

    def delete(self, key):
        """
        Delete the key and update writes dict.
        """
        result = self.wrapped_db.delete(key)
        self.access_logs.writes[key] = None
        return result
