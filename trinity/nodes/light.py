from typing import Type

from p2p.lightchain import LightPeerChain

from trinity.chains.light import (
    LightDispatchChain,
)

from trinity.nodes.base import Node


class LightNode(Node):
    peer_chain_class = LightPeerChain
    chain_class: Type[LightDispatchChain] = None

    _chain: LightDispatchChain = None

    def get_chain(self) -> LightDispatchChain:
        if self._chain is None:
            if self.chain_class is None:
                raise AttributeError("LightNode subclass must set chain_class")
            peer_chain = self._peer_chain
            self._chain = self.chain_class(self._headerdb, peer_chain=peer_chain)

        return self._chain
