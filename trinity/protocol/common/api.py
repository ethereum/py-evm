from typing import Union
from cached_property import cached_property

from eth_typing import BlockNumber, Hash32

from p2p.logic import Application
from p2p.qualifiers import HasProtocol

from trinity.protocol.eth.api import ETHAPI
from trinity.protocol.eth.proto import ETHProtocol
from trinity.protocol.les.api import LESV1API, LESV2API
from trinity.protocol.les.proto import LESProtocolV1, LESProtocolV2

from .abc import ChainInfoAPI, HeadInfoAPI

AnyETHLES = HasProtocol(ETHProtocol) | HasProtocol(LESProtocolV2) | HasProtocol(LESProtocolV1)


class ChainInfo(Application, ChainInfoAPI):
    name = 'eth1-chain-info'

    qualifier = AnyETHLES

    @cached_property
    def network_id(self) -> int:
        return self._get_logic().network_id

    @cached_property
    def genesis_hash(self) -> Hash32:
        return self._get_logic().genesis_hash

    def _get_logic(self) -> Union[ETHAPI, LESV1API, LESV2API]:
        if self.connection.has_protocol(ETHProtocol):
            return self.connection.get_logic(ETHAPI.name, ETHAPI)
        elif self.connection.has_protocol(LESProtocolV2):
            return self.connection.get_logic(LESV2API.name, LESV2API)
        elif self.connection.has_protocol(LESProtocolV1):
            return self.connection.get_logic(LESV1API.name, LESV1API)
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
        elif self.connection.has_protocol(LESProtocolV2):
            les_v2_logic = self.connection.get_logic(LESV2API.name, LESV2API)
            return les_v2_logic.head_info
        elif self.connection.has_protocol(LESProtocolV1):
            les_v1_logic = self.connection.get_logic(LESV1API.name, LESV1API)
            return les_v1_logic.head_info
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
