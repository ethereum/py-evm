import asyncio
import os

import pytest

from eth_utils import (
    keccak,
)

from evm.chains.mainnet import MAINNET_GENESIS_HEADER
from evm.db.backends.memory import MemoryDB
from evm.p2p import auth
from evm.p2p import constants
from evm.p2p import ecies
from evm.p2p import kademlia
from evm.p2p.les import (
    LESProtocol,
    LESProtocolV2,
)
from evm.p2p.peer import LESPeer
from evm.p2p.p2p_proto import P2PProtocol

from trinity.db.chain import AsyncChainDB


async def _get_directly_linked_peers_without_handshake(
        peer1_class=LESPeer, peer1_chaindb=None,
        peer2_class=LESPeer, peer2_chaindb=None):
    """See get_directly_linked_peers().

    Neither the P2P handshake nor the sub-protocol handshake will be performed here.
    """
    if peer1_chaindb is None:
        peer1_chaindb = get_fresh_mainnet_chaindb()
    if peer2_chaindb is None:
        peer2_chaindb = get_fresh_mainnet_chaindb()
    peer1_private_key = ecies.generate_privkey()
    peer2_private_key = ecies.generate_privkey()
    peer1_remote = kademlia.Node(
        peer2_private_key.public_key, kademlia.Address('0.0.0.0', 0, 0))
    peer2_remote = kademlia.Node(
        peer1_private_key.public_key, kademlia.Address('0.0.0.0', 0, 0))
    initiator = auth.HandshakeInitiator(peer1_remote, peer1_private_key)
    peer2_reader = asyncio.StreamReader()
    peer1_reader = asyncio.StreamReader()
    # Link the peer1's writer to the peer2's reader, and the peer2's writer to the
    # peer1's reader.
    peer2_writer = type(
        "mock-streamwriter",
        (object,),
        {"write": peer1_reader.feed_data,
         "close": lambda: None}
    )
    peer1_writer = type(
        "mock-streamwriter",
        (object,),
        {"write": peer2_reader.feed_data,
         "close": lambda: None}
    )

    peer1, peer2 = None, None
    handshake_finished = asyncio.Event()

    async def do_handshake():
        nonlocal peer1, peer2
        aes_secret, mac_secret, egress_mac, ingress_mac = await auth._handshake(
            initiator, peer1_reader, peer1_writer)

        # Need to copy those before we pass them on to the Peer constructor because they're
        # mutable. Also, the 2nd peer's ingress/egress MACs are reversed from the first peer's.
        peer2_ingress = egress_mac.copy()
        peer2_egress = ingress_mac.copy()

        peer1 = peer1_class(
            remote=peer1_remote, privkey=peer1_private_key, reader=peer1_reader,
            writer=peer1_writer, aes_secret=aes_secret, mac_secret=mac_secret,
            egress_mac=egress_mac, ingress_mac=ingress_mac, chaindb=peer1_chaindb,
            network_id=1)

        peer2 = peer2_class(
            remote=peer2_remote, privkey=peer2_private_key, reader=peer2_reader,
            writer=peer2_writer, aes_secret=aes_secret, mac_secret=mac_secret,
            egress_mac=peer2_egress, ingress_mac=peer2_ingress, chaindb=peer2_chaindb,
            network_id=1)

        handshake_finished.set()

    asyncio.ensure_future(do_handshake())

    responder = auth.HandshakeResponder(peer2_remote, peer2_private_key)
    auth_msg = await peer2_reader.read(constants.ENCRYPTED_AUTH_MSG_LEN)

    # Can't assert return values, but checking that the decoder doesn't raise
    # any exceptions at least.
    _, _ = responder.decode_authentication(auth_msg)

    peer2_nonce = keccak(os.urandom(constants.HASH_LEN))
    auth_ack_msg = responder.create_auth_ack_message(peer2_nonce)
    auth_ack_ciphertext = responder.encrypt_auth_ack_message(auth_ack_msg)
    peer2_writer.write(auth_ack_ciphertext)

    await handshake_finished.wait()

    return peer1, peer2


async def get_directly_linked_peers(
        request, event_loop,
        peer1_class=LESPeer, peer1_chaindb=None,
        peer2_class=LESPeer, peer2_chaindb=None):
    """Create two peers with their readers/writers connected directly.

    The first peer's reader will write directly to the second's writer, and vice-versa.
    """
    peer1, peer2 = await _get_directly_linked_peers_without_handshake(
        peer1_class, peer1_chaindb,
        peer2_class, peer2_chaindb)
    # Perform the base protocol (P2P) handshake.
    await asyncio.gather(peer1.do_p2p_handshake(), peer2.do_p2p_handshake())

    assert peer1.sub_proto.name == peer2.sub_proto.name
    assert peer1.sub_proto.version == peer2.sub_proto.version
    assert peer1.sub_proto.cmd_id_offset == peer2.sub_proto.cmd_id_offset

    # Perform the handshake for the enabled sub-protocol.
    await asyncio.gather(peer1.do_sub_proto_handshake(), peer2.do_sub_proto_handshake())

    asyncio.ensure_future(peer1.run())
    asyncio.ensure_future(peer2.run())

    def finalizer():
        async def afinalizer():
            await peer1.stop()
            await peer2.stop()
        event_loop.run_until_complete(afinalizer())
    request.addfinalizer(finalizer)

    return peer1, peer2


@pytest.mark.asyncio
async def test_directly_linked_peers(request, event_loop):
    peer1, _ = await get_directly_linked_peers(request, event_loop)
    assert isinstance(peer1.sub_proto, LESProtocolV2)


def get_fresh_mainnet_chaindb():
    chaindb = AsyncChainDB(MemoryDB())
    chaindb.persist_header_to_db(MAINNET_GENESIS_HEADER)
    return chaindb


@pytest.mark.asyncio
async def test_les_handshake():
    peer1, peer2 = await _get_directly_linked_peers_without_handshake()

    # Perform the base protocol (P2P) handshake.
    await asyncio.gather(peer1.do_p2p_handshake(), peer2.do_p2p_handshake())
    # Perform the handshake for the enabled sub-protocol (LES).
    await asyncio.gather(peer1.do_sub_proto_handshake(), peer2.do_sub_proto_handshake())

    assert isinstance(peer1.sub_proto, LESProtocol)
    assert isinstance(peer2.sub_proto, LESProtocol)


def test_sub_protocol_selection():
    peer = ProtoMatchingPeer([LESProtocol, LESProtocolV2])

    proto = peer.select_sub_protocol([
        (LESProtocol.name, LESProtocol.version),
        (LESProtocolV2.name, LESProtocolV2.version),
        (LESProtocolV3.name, LESProtocolV3.version),
        ('unknown', 1),
    ])

    assert isinstance(proto, LESProtocolV2)
    assert proto.cmd_id_offset == peer.base_protocol.cmd_length


class LESProtocolV3(LESProtocol):
    version = 3


class ProtoMatchingPeer(LESPeer):

    def __init__(self, supported_sub_protocols):
        self._supported_sub_protocols = supported_sub_protocols
        self.base_protocol = P2PProtocol(self)
