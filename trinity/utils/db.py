import os

from evm.db import get_db_backend
from evm.db.chain import BaseChainDB


def get_chain_db_backend_class_path():
    return os.environ.get(
        'TRINITY_DB_BACKEND',
        'evm.db.backends.level.LevelDB',
    )


def get_chain_db(data_dir, db_backend_class=None):
    if db_backend_class is None:
        db_backend_class = get_chain_db_backend_class_path()

    db = get_db_backend(db_backend_class, db_path=data_dir)
    return BaseChainDB(db)
