from trinity.db.rpc import BaseRPCDB


class RPCModule:
    _db: BaseRPCDB = None

    def __init__(self, db: BaseRPCDB=None) -> None:
        self._db = db

    def set_db(self, db: BaseRPCDB) -> None:
        self._db = db
