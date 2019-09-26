from typing import Union
from cached_property import cached_property

from eth_typing import BlockNumber, Hash32

from p2p.logic import Application
from p2p.qualifiers import HasProtocol

from trinity.protocol.eth.api import ETHAPI
from trinity.protocol.eth.proto import ETHProtocol
from trinity.protocol.les.api import LESAPI
from trinity.protocol.les.proto import LESProtocol, LESProtocolV2

from .abc import ChainInfoAPI, HeadInfoAPI

AnyETHLES = HasProtocol(ETHProtocol) | HasProtocol(LESProtocolV2) | HasProtocol(LESProtocol)


class ChainInfo(Application, ChainInfoAPI):
    name = 'eth1-chain-info'

    qualifier = AnyETHLES

    @cached_property
    def network_id(self) -> int:
        return self._get_logic().network_id

    @cached_property
    def genesis_hash(self) -> Hash32:
        return self._get_logic().genesis_hash

    def _get_logic(self) -> Union[ETHAPI, LESAPI]:
        if self.connection.has_protocol(ETHProtocol):
            return self.connection.get_logic(ETHAPI.name, ETHAPI)
        elif self.connection.has_protocol(LESProtocolV2) or self.connection.has_protocol(LESProtocol):  # noqa: E501
            return self.connection.get_logic(LESAPI.name, LESAPI)
        else:
            raise Exception("Unreachable code path")


class HeadInfo(Application, HeadInfoAPI):
    name = 'eth1-head-info'

    qualifier = AnyETHLES

    @cached_property
    def _tracker(self) -> HeadInfoAPI:
        if self.connection.has_protocol(ETHProtocol):
            eth_logic = self.connection.get_logic(ETHAPI.name, ETHAPI)
            return eth_logic.head_info
        elif self.connection.has_protocol(LESProtocolV2) or self.connection.has_protocol(LESProtocol):  # noqa: E501
            les_logic = self.connection.get_logic(LESAPI.name, LESAPI)
            return les_logic.head_info
        else:
            raise Exception("Unreachable code path")

    @property
    def head_td(self) -> int:
        return self._tracker.head_td

    @property
    def head_hash(self) -> Hash32:
        return self._tracker.head_hash

    @property
    def head_number(self) -> BlockNumber:
        return self._tracker.head_number
