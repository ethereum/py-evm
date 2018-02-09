from evm.db.backends.base import (
    BaseDB,
)

from trinity.utils.ipc import (
    ObjectOverIPC,
    IPCMethod,
)


class PipeDB(ObjectOverIPC, BaseDB):
    get = IPCMethod('get')
    set = IPCMethod('set')
    exists = IPCMethod('exists')
    delete = IPCMethod('delete')
