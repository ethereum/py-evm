import os

from evm.db import get_db_backend
from evm.db.chain import BaseChainDB


def get_chain_db_backend_class_path():
    return os.environ.get(
        'TRINITY_DB_BACKEND',
        'trinity.db.mp.MPDB',
    )


def get_chain_db(db_backend_class=None, init_kwargs=None):
    if db_backend_class is None:
        db_backend_class = get_chain_db_backend_class_path()

    if init_kwargs is None:
        init_kwargs = {}

    db = get_db_backend(db_backend_class, **init_kwargs)
    return BaseChainDB(db)
