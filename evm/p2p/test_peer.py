import asyncio
import os

import pytest

import rlp
from rlp import sedes

from evm.chains.mainnet import MAINNET_GENESIS_HEADER
from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB
from evm.utils.keccak import keccak
from evm.p2p import auth
from evm.p2p import constants
from evm.p2p import ecies
from evm.p2p import kademlia
from evm.p2p.les import (
    LESProtocol,
    LESProtocolV2,
    StatusV2,
)
from evm.p2p.peer import LESPeer
from evm.p2p.protocol import Protocol
from evm.p2p.p2p_proto import P2PProtocol


async def get_directly_linked_peers(
        peer1_class=LESPeer, peer1_chaindb=None, peer1_received_msg_callback=None,
        peer2_class=LESPeer, peer2_chaindb=None, peer2_received_msg_callback=None):
    """Create two LESPeers with their readers/writers connected directly.

    The first peer's reader will write directly to the second's writer, and vice-versa.
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
            network_id=1, received_msg_callback=peer1_received_msg_callback)

        peer2 = peer2_class(
            remote=peer2_remote, privkey=peer2_private_key, reader=peer2_reader,
            writer=peer2_writer, aes_secret=aes_secret, mac_secret=mac_secret,
            egress_mac=peer2_egress, ingress_mac=peer2_ingress, chaindb=peer2_chaindb,
            network_id=1, received_msg_callback=peer2_received_msg_callback)

        handshake_finished.set()

    asyncio.ensure_future(do_handshake())

    responder = auth.HandshakeResponder(peer2_remote, peer2_private_key)
    auth_msg = await peer2_reader.read(constants.ENCRYPTED_AUTH_MSG_LEN)
    peer1_ephemeral_pubkey, peer1_nonce = responder.decode_authentication(auth_msg)

    peer2_nonce = keccak(os.urandom(constants.HASH_LEN))
    auth_ack_msg = responder.create_auth_ack_message(peer2_nonce)
    auth_ack_ciphertext = responder.encrypt_auth_ack_message(auth_ack_msg)
    peer2_writer.write(auth_ack_ciphertext)

    await handshake_finished.wait()

    # Perform the base protocol (P2P) handshake.
    peer1.base_protocol.send_handshake()
    peer2.base_protocol.send_handshake()
    msg1 = await peer1.read_msg()
    peer1.process_msg(msg1)
    msg2 = await peer2.read_msg()
    peer2.process_msg(msg2)

    # Now send the handshake msg for each enabled sub-protocol.
    for proto in peer1.enabled_sub_protocols:
        proto.send_handshake(peer1._local_chain_info)
    for proto in peer2.enabled_sub_protocols:
        proto.send_handshake(peer2._local_chain_info)

    return peer1, peer2


@pytest.mark.asyncio
async def test_directly_linked_peers():
    peer1, peer2 = await get_directly_linked_peers()
    assert len(peer1.enabled_sub_protocols) == 1
    assert peer1.les_proto is not None
    assert peer1.les_proto.name == LESProtocolV2.name
    assert peer1.les_proto.version == LESProtocolV2.version
    assert [(proto.name, proto.version) for proto in peer1.enabled_sub_protocols] == [
        (proto.name, proto.version) for proto in peer2.enabled_sub_protocols]


def get_fresh_mainnet_chaindb():
    chaindb = BaseChainDB(MemoryDB())
    chaindb.persist_header_to_db(MAINNET_GENESIS_HEADER)
    return chaindb


@pytest.mark.asyncio
async def test_les_handshake():
    peer1, peer2 = await get_directly_linked_peers()
    # The peers above have already performed the sub-protocol agreement, and sent the handshake
    # msg for each enabled sub protocol -- in this case that's the Status msg of the LES/2 protocol.
    msg = await peer1.read_msg()
    cmd_id = rlp.decode(msg[:1], sedes=sedes.big_endian_int)
    proto = peer1.get_protocol_for(cmd_id)
    assert cmd_id == proto.cmd_by_class[StatusV2].cmd_id


def test_sub_protocol_matching():
    peer = ProtoMatchingPeer([LESProtocol, LESProtocolV2, ETHProtocol63])

    peer.match_protocols([
        (LESProtocol.name, LESProtocol.version),
        (LESProtocolV2.name, LESProtocolV2.version),
        (LESProtocolV3.name, LESProtocolV3.version),
        (ETHProtocol63.name, ETHProtocol63.version),
        ('unknown', 1),
    ])

    assert len(peer.enabled_sub_protocols) == 2
    eth_proto, les_proto = peer.enabled_sub_protocols
    assert isinstance(eth_proto, ETHProtocol63)
    assert eth_proto.cmd_id_offset == peer.base_protocol.cmd_length

    assert isinstance(les_proto, LESProtocolV2)
    assert les_proto.cmd_id_offset == peer.base_protocol.cmd_length + eth_proto.cmd_length


class LESProtocolV3(LESProtocol):
    version = 3

    def send_handshake(self):
        pass


class ETHProtocol63(Protocol):
    name = b'eth'
    version = 63
    cmd_length = 15

    def send_handshake(self):
        pass


class ProtoMatchingPeer(LESPeer):

    def __init__(self, supported_sub_protocols):
        self._supported_sub_protocols = supported_sub_protocols
        self.base_protocol = MockP2PProtocol(self)
        self.enabled_sub_protocols = []


class MockP2PProtocol(P2PProtocol):

    def send_handshake(self):
        pass
