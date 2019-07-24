from typing import (
    Tuple,
    Type,
)

from eth.vm.base import BaseVM

from p2p.peer import BasePeerContext

from trinity.db.eth1.header import BaseAsyncHeaderDB


class ChainContext(BasePeerContext):
    def __init__(self,
                 headerdb: BaseAsyncHeaderDB,
                 network_id: int,
                 vm_configuration: Tuple[Tuple[int, Type[BaseVM]], ...],
                 client_version_string: str,
                 listen_port: int,
                 ) -> None:
        super().__init__(client_version_string, listen_port)
        self.headerdb = headerdb
        self.network_id = network_id
        self.vm_configuration = vm_configuration
