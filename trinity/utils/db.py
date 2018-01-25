import os

from evm.db import get_db_backend
from evm.db.chain import BaseChainDB

from .chains import (
    get_data_dir,
)


def get_chain_db_backend_class_path():
    return os.environ.get(
        'TRINITY_DB_BACKEND',
        'evm.db.backends.level.LevelDB',
    )


def get_chain_db(chain_identifier, db_backend_class=None):
    db_path = get_data_dir(chain_identifier)
    if db_backend_class is None:
        db_backend_class = get_chain_db_backend_class_path()

    db = get_db_backend(db_backend_class, db_path=db_path)
    return BaseChainDB(db)
