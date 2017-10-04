import asyncio
import os

import pytest

from evm.utils.keccak import (
    keccak,
)
from evm.p2p import auth
from evm.p2p import constants
from evm.p2p import ecies
from evm.p2p import kademlia
from evm.p2p.les import LESProtocol
from evm.p2p.peer import Peer
from evm.p2p.protocol import Protocol
from evm.p2p.p2p_proto import P2PProtocol


@pytest.fixture
@asyncio.coroutine
def directly_linked_peers():
    """Create two Peers with their readers/writers connected directly.

    The first peer's reader will write directly to the second's writer, and vice-versa.
    """
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
        {"write": lambda data: peer1_reader.feed_data(data)}
    )
    peer1_writer = type(
        "mock-streamwriter",
        (object,),
        {"write": lambda data: peer2_reader.feed_data(data)}
    )

    peer1, peer2 = None, None
    handshake_finished = asyncio.Event()

    @asyncio.coroutine
    def do_handshake():
        nonlocal peer1, peer2
        aes_secret, mac_secret, egress_mac, ingress_mac = yield from auth._handshake(
            initiator, peer1_reader, peer1_writer)

        # Need to copy those before we pass them on to the Peer constructor because they're
        # mutable. Also, the 2nd peer's ingress/egress MACs are reversed from the first peer's.
        peer2_ingress = egress_mac.copy()
        peer2_egress = ingress_mac.copy()

        peer1 = Peer(
            remote=peer1_remote, privkey=peer1_private_key, reader=peer1_reader,
            writer=peer1_writer, aes_secret=aes_secret, mac_secret=mac_secret,
            egress_mac=egress_mac, ingress_mac=ingress_mac)

        peer2 = Peer(
            remote=peer2_remote, privkey=peer2_private_key, reader=peer2_reader,
            writer=peer2_writer, aes_secret=aes_secret, mac_secret=mac_secret,
            egress_mac=peer2_egress, ingress_mac=peer2_ingress)

        peer1.send_hello()
        peer2.send_hello()
        handshake_finished.set()

    asyncio.ensure_future(do_handshake())

    responder = auth.HandshakeResponder(peer2_remote, peer2_private_key)
    auth_msg = yield from peer2_reader.read(constants.ENCRYPTED_AUTH_MSG_LEN)
    peer1_ephemeral_pubkey, peer1_nonce = responder.decode_authentication(auth_msg)

    peer2_nonce = keccak(os.urandom(constants.HASH_LEN))
    auth_ack_msg = responder.create_auth_ack_message(peer2_nonce)
    auth_ack_ciphertext = responder.encrypt_auth_ack_message(auth_ack_msg)
    peer2_writer.write(auth_ack_ciphertext)

    yield from handshake_finished.wait()

    msg1 = yield from peer1.read_msg()
    peer1.process_msg(msg1)
    msg2 = yield from peer2.read_msg()
    peer2.process_msg(msg2)
    return peer1, peer2


@pytest.mark.asyncio
def test_directly_linked_peers(directly_linked_peers):
    peer1, peer2 = yield from directly_linked_peers
    assert len(peer1.enabled_sub_protocols) == 1
    assert peer1.enabled_sub_protocols[0].name == b'les'
    assert peer1.enabled_sub_protocols[0].version == 1
    assert [(proto.name, proto.version) for proto in peer1.enabled_sub_protocols] == [
        (proto.name, proto.version) for proto in peer2.enabled_sub_protocols]


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


class LESProtocolV2(LESProtocol):
    version = 2


class LESProtocolV3(LESProtocol):
    version = 3


class ETHProtocol63(Protocol):
    name = b'eth'
    version = 63
    cmd_length = 15


class ProtoMatchingPeer(Peer):

    def __init__(self, supported_sub_protocols):
        self._supported_sub_protocols = supported_sub_protocols
        self.base_protocol = P2PProtocol(self)
        self.enabled_sub_protocols = []
