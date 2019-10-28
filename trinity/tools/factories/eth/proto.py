try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")

from typing import (
    cast,
    Any,
    AsyncContextManager,
    Tuple,
)

from lahja import EndpointAPI

from cancel_token import CancelToken

from eth_typing import BlockNumber
from eth_utils import to_bytes

from eth_keys import keys
from eth.abc import HeaderDatabaseAPI
from eth.constants import GENESIS_DIFFICULTY, GENESIS_BLOCK_NUMBER

from p2p import kademlia
from p2p.tools.factories import PeerPairFactory

from trinity.constants import MAINNET_NETWORK_ID

from trinity.protocol.common.context import ChainContext

from trinity.protocol.eth.handshaker import ETHHandshaker
from trinity.protocol.eth.peer import ETHPeer, ETHPeerFactory
from trinity.protocol.eth.proto import ETHHandshakeParams, ETHProtocol

from trinity.tools.factories.chain_context import ChainContextFactory


MAINNET_GENESIS_HASH = to_bytes(hexstr='0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3')  # noqa: E501


class ETHHandshakeParamsFactory(factory.Factory):
    class Meta:
        model = ETHHandshakeParams

    head_hash = MAINNET_GENESIS_HASH
    genesis_hash = MAINNET_GENESIS_HASH
    network_id = MAINNET_NETWORK_ID
    total_difficulty = GENESIS_DIFFICULTY
    version = ETHProtocol.version

    @classmethod
    def from_headerdb(cls, headerdb: HeaderDatabaseAPI, **kwargs: Any) -> ETHHandshakeParams:
        head = headerdb.get_canonical_head()
        head_score = headerdb.get_score(head.hash)
        # TODO: https://github.com/ethereum/py-evm/issues/1847
        genesis = headerdb.get_canonical_block_header_by_number(BlockNumber(GENESIS_BLOCK_NUMBER))
        return cls(
            head_hash=head.hash,
            genesis_hash=genesis.hash,
            total_difficulty=head_score,
            **kwargs
        )


class ETHHandshakerFactory(factory.Factory):
    class Meta:
        model = ETHHandshaker

    handshake_params = factory.SubFactory(ETHHandshakeParamsFactory)


def ETHPeerPairFactory(*,
                       alice_peer_context: ChainContext = None,
                       alice_remote: kademlia.Node = None,
                       alice_private_key: keys.PrivateKey = None,
                       alice_client_version: str = 'bob',
                       bob_peer_context: ChainContext = None,
                       bob_remote: kademlia.Node = None,
                       bob_private_key: keys.PrivateKey = None,
                       bob_client_version: str = 'bob',
                       cancel_token: CancelToken = None,
                       event_bus: EndpointAPI = None,
                       ) -> AsyncContextManager[Tuple[ETHPeer, ETHPeer]]:
    if alice_peer_context is None:
        alice_peer_context = ChainContextFactory()

    if bob_peer_context is None:
        alice_genesis = alice_peer_context.headerdb.get_canonical_block_header_by_number(
            BlockNumber(GENESIS_BLOCK_NUMBER),
        )
        bob_peer_context = ChainContextFactory(
            headerdb__genesis_params={'timestamp': alice_genesis.timestamp},
        )

    return cast(AsyncContextManager[Tuple[ETHPeer, ETHPeer]], PeerPairFactory(
        alice_peer_context=alice_peer_context,
        alice_peer_factory_class=ETHPeerFactory,
        bob_peer_context=bob_peer_context,
        bob_peer_factory_class=ETHPeerFactory,
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        alice_client_version=alice_client_version,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
        bob_client_version=bob_client_version,
        cancel_token=cancel_token,
        event_bus=event_bus,
    ))
