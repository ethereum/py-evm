import asyncio
from typing import AsyncIterator, Tuple

from async_generator import asynccontextmanager

from cancel_token import CancelToken

from eth_keys import keys

from p2p.abc import ConnectionAPI, NodeAPI
from p2p.connection import Connection
from p2p.constants import DEVP2P_V5
from p2p.handshake import (
    DevP2PReceipt,
    Handshaker,
    negotiate_protocol_handshakes,
)
from p2p.service import run_service

from .cancel_token import CancelTokenFactory
from .multiplexer import MultiplexerPairFactory
from .p2p_proto import DevP2PHandshakeParamsFactory
from .transport import MemoryTransportPairFactory


@asynccontextmanager
async def ConnectionPairFactory(*,
                                alice_handshakers: Tuple[Handshaker, ...] = (),
                                bob_handshakers: Tuple[Handshaker, ...] = (),
                                alice_remote: NodeAPI = None,
                                alice_private_key: keys.PrivateKey = None,
                                alice_client_version: str = 'alice',
                                alice_p2p_version: int = DEVP2P_V5,
                                bob_remote: NodeAPI = None,
                                bob_private_key: keys.PrivateKey = None,
                                bob_client_version: str = 'bob',
                                bob_p2p_version: int = DEVP2P_V5,
                                cancel_token: CancelToken = None,
                                start_streams: bool = True,
                                ) -> AsyncIterator[Tuple[ConnectionAPI, ConnectionAPI]]:

    if alice_handshakers or bob_handshakers:
        # We only leverage `negotiate_protocol_handshakes` if we have actual
        # protocol handshakers since it raises `NoMatchingPeerCapabilities` if
        # there are no matching capabilities.
        alice_transport, bob_transport = MemoryTransportPairFactory(
            alice_remote=alice_remote,
            alice_private_key=alice_private_key,
            bob_remote=bob_remote,
            bob_private_key=bob_private_key,
        )
        alice_devp2p_params = DevP2PHandshakeParamsFactory(
            client_version_string=alice_client_version,
            listen_port=alice_transport.remote.address.tcp_port,
            version=alice_p2p_version,
        )
        bob_devp2p_params = DevP2PHandshakeParamsFactory(
            client_version_string=bob_client_version,
            listen_port=bob_transport.remote.address.tcp_port,
            version=bob_p2p_version,
        )

        if cancel_token is None:
            cancel_token = CancelTokenFactory()

        (
            (alice_multiplexer, alice_p2p_receipt, alice_protocol_receipts),
            (bob_multiplexer, bob_p2p_receipt, bob_protocol_receipts),
        ) = await asyncio.gather(
            negotiate_protocol_handshakes(
                alice_transport,
                alice_devp2p_params,
                alice_handshakers,
                cancel_token,
            ),
            negotiate_protocol_handshakes(
                bob_transport,
                bob_devp2p_params,
                bob_handshakers,
                cancel_token,
            ),
        )
    else:
        # This path is just for testing to allow us to establish a `Connection`
        # without any protocols beyond the base p2p protocol.
        alice_multiplexer, bob_multiplexer = MultiplexerPairFactory(
            alice_remote=alice_remote,
            alice_private_key=alice_private_key,
            alice_p2p_version=alice_p2p_version,
            bob_remote=bob_remote,
            bob_private_key=bob_private_key,
            bob_p2p_version=bob_p2p_version,
            cancel_token=cancel_token,
        )
        alice_p2p_receipt = DevP2PReceipt(
            protocol=alice_multiplexer.get_base_protocol(),
            version=bob_p2p_version,
            client_version_string=bob_client_version,
            capabilities=(),
            listen_port=bob_multiplexer.remote.address.tcp_port,
            remote_public_key=bob_multiplexer.remote.pubkey,
        )
        bob_p2p_receipt = DevP2PReceipt(
            protocol=bob_multiplexer.get_base_protocol(),
            version=alice_p2p_version,
            client_version_string=alice_client_version,
            capabilities=(),
            listen_port=alice_multiplexer.remote.address.tcp_port,
            remote_public_key=alice_multiplexer.remote.pubkey,
        )
        alice_protocol_receipts = ()
        bob_protocol_receipts = ()

    alice_connection = Connection(
        multiplexer=alice_multiplexer,
        devp2p_receipt=alice_p2p_receipt,
        protocol_receipts=alice_protocol_receipts,
        is_dial_out=True,
    )
    bob_connection = Connection(
        multiplexer=bob_multiplexer,
        devp2p_receipt=bob_p2p_receipt,
        protocol_receipts=bob_protocol_receipts,
        is_dial_out=False,
    )

    async with run_service(alice_connection), run_service(bob_connection):
        if start_streams:
            alice_connection.start_protocol_streams()
            bob_connection.start_protocol_streams()
        yield alice_connection, bob_connection
