import asyncio
import logging
import operator
import random
import struct
import time
from abc import (
    ABCMeta,
    abstractmethod
)

from typing import (  # noqa: F401
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Type,
    TYPE_CHECKING,
    cast,
)

import sha3

import rlp
from rlp import sedes

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.constant_time import bytes_eq

from eth_utils import (
    decode_hex,
    encode_hex,
)

from eth_typing import BlockNumber, Hash32  # noqa: F401

from eth_keys import (
    datatypes,
    keys,
)

from eth_hash.auto import keccak

from trie import HexaryTrie

from evm.constants import GENESIS_BLOCK_NUMBER
from evm.exceptions import BlockNotFound
from evm.rlp.accounts import Account
from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt

from p2p import auth
from p2p import ecies
from p2p.discovery import DiscoveryProtocol
from p2p.kademlia import Address, Node
from p2p import protocol
from p2p.exceptions import (
    DecryptionError,
    EmptyGetBlockHeadersReply,
    HandshakeFailure,
    NoMatchingPeerCapabilities,
    OperationCancelled,
    PeerConnectionLost,
    RemoteDisconnected,
    UnexpectedMessage,
    UnknownProtocolCommand,
    UnreachablePeer,
)
from p2p.cancel_token import CancelToken, wait_with_token
from p2p.rlp import BlockBody
from p2p.service import BaseService
from p2p.utils import (
    gen_request_id,
    get_devp2p_cmd_id,
    roundup_16,
    sxor,
)
from p2p import eth
from p2p import les
from p2p.p2p_proto import (
    Disconnect,
    DisconnectReason,
    Hello,
    P2PProtocol,
    Ping,
    Pong,
)

from .constants import (
    CONN_IDLE_TIMEOUT,
    DEFAULT_MIN_PEERS,
    HEADER_LEN,
    MAC_LEN,
    REPLY_TIMEOUT,
)

if TYPE_CHECKING:
    from trinity.db.header import BaseAsyncHeaderDB  # noqa: F401


async def handshake(remote: Node,
                    privkey: datatypes.PrivateKey,
                    peer_class: 'Type[BasePeer]',
                    headerdb: 'BaseAsyncHeaderDB',
                    network_id: int,
                    token: CancelToken,
                    ) -> 'BasePeer':
    """Perform the auth and P2P handshakes with the given remote.

    Return an instance of the given peer_class (must be a subclass of BasePeer) connected to that
    remote in case both handshakes are successful and at least one of the sub-protocols supported
    by peer_class is also supported by the remote.

    Raises UnreachablePeer if we cannot connect to the peer or HandshakeFailure if the remote
    disconnects before completing the handshake or if none of the sub-protocols supported by us is
    also supported by the remote.
    """
    try:
        (aes_secret,
         mac_secret,
         egress_mac,
         ingress_mac,
         reader,
         writer
         ) = await auth.handshake(remote, privkey, token)
    except (ConnectionRefusedError, OSError) as e:
        raise UnreachablePeer(e)
    peer = peer_class(
        remote=remote, privkey=privkey, reader=reader, writer=writer,
        aes_secret=aes_secret, mac_secret=mac_secret, egress_mac=egress_mac,
        ingress_mac=ingress_mac, headerdb=headerdb, network_id=network_id)
    await peer.do_p2p_handshake()
    await peer.do_sub_proto_handshake()
    return peer


class BasePeer(BaseService):
    logger = logging.getLogger("p2p.peer.Peer")
    conn_idle_timeout = CONN_IDLE_TIMEOUT
    reply_timeout = REPLY_TIMEOUT
    # Must be defined in subclasses. All items here must be Protocol classes representing
    # different versions of the same P2P sub-protocol (e.g. ETH, LES, etc).
    _supported_sub_protocols = []  # type: List[Type[protocol.Protocol]]
    # FIXME: Must be configurable.
    listen_port = 30303
    # Will be set upon the successful completion of a P2P handshake.
    sub_proto = None  # type: protocol.Protocol

    def __init__(self,
                 remote: Node,
                 privkey: datatypes.PrivateKey,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 aes_secret: bytes,
                 mac_secret: bytes,
                 egress_mac: sha3.keccak_256,
                 ingress_mac: sha3.keccak_256,
                 headerdb: 'BaseAsyncHeaderDB',
                 network_id: int,
                 ) -> None:
        super().__init__()
        self.remote = remote
        self.privkey = privkey
        self.reader = reader
        self.writer = writer
        self.base_protocol = P2PProtocol(self)
        self.headerdb = headerdb
        self.network_id = network_id
        self.sub_proto_msg_queue = asyncio.Queue()  # type: asyncio.Queue[Tuple[protocol.Command, protocol._DecodedMsgType]]  # noqa: E501

        self.egress_mac = egress_mac
        self.ingress_mac = ingress_mac
        # FIXME: Yes, the encryption is insecure, see: https://github.com/ethereum/devp2p/issues/32
        iv = b"\x00" * 16
        aes_cipher = Cipher(algorithms.AES(aes_secret), modes.CTR(iv), default_backend())
        self.aes_enc = aes_cipher.encryptor()
        self.aes_dec = aes_cipher.decryptor()
        mac_cipher = Cipher(algorithms.AES(mac_secret), modes.ECB(), default_backend())
        self.mac_enc = mac_cipher.encryptor().update

    @abstractmethod
    async def send_sub_proto_handshake(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    async def process_sub_proto_handshake(
            self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    async def do_sub_proto_handshake(self):
        """Perform the handshake for the sub-protocol agreed with the remote peer.

        Raises HandshakeFailure if the handshake is not successful.
        """
        await self.send_sub_proto_handshake()
        cmd, msg = await self.read_msg()
        if isinstance(cmd, Disconnect):
            # Peers sometimes send a disconnect msg before they send the sub-proto handshake.
            raise HandshakeFailure(
                "{} disconnected before completing sub-proto handshake: {}".format(
                    self, msg['reason_name']))
        await self.process_sub_proto_handshake(cmd, msg)
        self.logger.debug("Finished %s handshake with %s", self.sub_proto, self.remote)

    async def do_p2p_handshake(self):
        """Perform the handshake for the P2P base protocol.

        Raises HandshakeFailure if the handshake is not successful.
        """
        self.base_protocol.send_handshake()
        cmd, msg = await self.read_msg()
        if isinstance(cmd, Disconnect):
            # Peers sometimes send a disconnect msg before they send the initial P2P handshake.
            raise HandshakeFailure("{} disconnected before completing handshake: {}".format(
                self, msg['reason_name']))
        self.process_p2p_handshake(cmd, msg)

    async def read_sub_proto_msg(
            self, cancel_token: CancelToken) -> Tuple[protocol.Command, protocol._DecodedMsgType]:
        """Read the next sub-protocol message from the queue.

        Raises OperationCancelled if the peer has been disconnected.
        """
        combined_token = self.cancel_token.chain(cancel_token)
        return await wait_with_token(self.sub_proto_msg_queue.get(), token=combined_token)

    @property
    async def genesis(self) -> BlockHeader:
        genesis_hash = await self.headerdb.coro_get_canonical_block_hash(
            BlockNumber(GENESIS_BLOCK_NUMBER),
        )
        return await self.headerdb.coro_get_block_header_by_hash(genesis_hash)

    @property
    async def _local_chain_info(self) -> 'ChainInfo':
        genesis = await self.genesis
        head = await self.headerdb.coro_get_canonical_head()
        total_difficulty = await self.headerdb.coro_get_score(head.hash)
        return ChainInfo(
            block_number=head.block_number,
            block_hash=head.hash,
            total_difficulty=total_difficulty,
            genesis_hash=genesis.hash,
        )

    @property
    def capabilities(self) -> List[Tuple[str, int]]:
        return [(klass.name, klass.version) for klass in self._supported_sub_protocols]

    def get_protocol_command_for(self, msg: bytes) -> protocol.Command:
        """Return the Command corresponding to the cmd_id encoded in the given msg."""
        cmd_id = get_devp2p_cmd_id(msg)
        self.logger.debug("Got msg with cmd_id: %s", cmd_id)
        if cmd_id < self.base_protocol.cmd_length:
            proto = self.base_protocol
        elif cmd_id < self.sub_proto.cmd_id_offset + self.sub_proto.cmd_length:
            proto = self.sub_proto  # type: ignore
        else:
            raise UnknownProtocolCommand("No protocol found for cmd_id {}".format(cmd_id))
        return proto.cmd_by_id[cmd_id]

    async def read(self, n: int) -> bytes:
        self.logger.debug("Waiting for %s bytes from %s", n, self.remote)
        try:
            return await wait_with_token(
                self.reader.readexactly(n), token=self.cancel_token, timeout=self.conn_idle_timeout)
        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError) as e:
            raise PeerConnectionLost(repr(e))

    def close(self):
        """Close this peer's reader/writer streams.

        This will cause the peer to stop in case it is running.

        If the streams have already been closed, do nothing.
        """
        if self.reader.at_eof():
            return
        self.reader.feed_eof()
        self.writer.close()

    async def _cleanup(self):
        self.close()

    async def _run(self):
        while True:
            try:
                cmd, msg = await self.read_msg()
            except (PeerConnectionLost, TimeoutError) as e:
                self.logger.info(
                    "%s stopped responding (%s), disconnecting", self.remote, repr(e))
                return

            try:
                self.process_msg(cmd, msg)
            except RemoteDisconnected as e:
                self.logger.info("%s disconnected: %s", self, e)
                return

    async def read_msg(self) -> Tuple[protocol.Command, protocol._DecodedMsgType]:
        header_data = await self.read(HEADER_LEN + MAC_LEN)
        header = self.decrypt_header(header_data)
        frame_size = self.get_frame_size(header)
        # The frame_size specified in the header does not include the padding to 16-byte boundary,
        # so need to do this here to ensure we read all the frame's data.
        read_size = roundup_16(frame_size)
        frame_data = await self.read(read_size + MAC_LEN)
        msg = self.decrypt_body(frame_data, frame_size)
        cmd = self.get_protocol_command_for(msg)
        loop = asyncio.get_event_loop()
        decoded_msg = await wait_with_token(
            loop.run_in_executor(None, cmd.decode, msg),
            token=self.cancel_token)
        self.logger.debug("Successfully decoded %s msg: %s", cmd, decoded_msg)
        return cmd, decoded_msg

    def handle_p2p_msg(self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        """Handle the base protocol (P2P) messages."""
        if isinstance(cmd, Disconnect):
            msg = cast(Dict[str, Any], msg)
            raise RemoteDisconnected(msg['reason_name'])
        elif isinstance(cmd, Ping):
            self.base_protocol.send_pong()
        elif isinstance(cmd, Pong):
            # Currently we don't do anything when we get a pong, but eventually we should
            # update the last time we heard from a peer in our DB (which doesn't exist yet).
            pass
        else:
            raise UnexpectedMessage("Unexpected msg: {} ({})".format(cmd, msg))

    def handle_sub_proto_msg(self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        self.sub_proto_msg_queue.put_nowait((cmd, msg))

    def process_msg(self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        if cmd.is_base_protocol:
            self.handle_p2p_msg(cmd, msg)
        else:
            self.handle_sub_proto_msg(cmd, msg)

    def process_p2p_handshake(self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        msg = cast(Dict[str, Any], msg)
        if not isinstance(cmd, Hello):
            self.disconnect(DisconnectReason.other)
            raise HandshakeFailure("Expected a Hello msg, got {}, disconnecting".format(cmd))
        remote_capabilities = msg['capabilities']
        try:
            self.sub_proto = self.select_sub_protocol(remote_capabilities)
        except NoMatchingPeerCapabilities:
            self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                "No matching capabilities between us ({}) and {} ({}), disconnecting".format(
                    self.capabilities, self.remote, remote_capabilities))
        self.logger.debug(
            "Finished P2P handshake with %s, using sub-protocol %s",
            self.remote, self.sub_proto)

    def encrypt(self, header: bytes, frame: bytes) -> bytes:
        if len(header) != HEADER_LEN:
            raise ValueError("Unexpected header length: {}".format(len(header)))

        header_ciphertext = self.aes_enc.update(header)
        mac_secret = self.egress_mac.digest()[:HEADER_LEN]
        self.egress_mac.update(sxor(self.mac_enc(mac_secret), header_ciphertext))
        header_mac = self.egress_mac.digest()[:HEADER_LEN]

        frame_ciphertext = self.aes_enc.update(frame)
        self.egress_mac.update(frame_ciphertext)
        fmac_seed = self.egress_mac.digest()[:HEADER_LEN]

        mac_secret = self.egress_mac.digest()[:HEADER_LEN]
        self.egress_mac.update(sxor(self.mac_enc(mac_secret), fmac_seed))
        frame_mac = self.egress_mac.digest()[:HEADER_LEN]

        return header_ciphertext + header_mac + frame_ciphertext + frame_mac

    def decrypt_header(self, data: bytes) -> bytes:
        if len(data) != HEADER_LEN + MAC_LEN:
            raise ValueError("Unexpected header length: {}".format(len(data)))

        header_ciphertext = data[:HEADER_LEN]
        header_mac = data[HEADER_LEN:]
        mac_secret = self.ingress_mac.digest()[:HEADER_LEN]
        aes = self.mac_enc(mac_secret)[:HEADER_LEN]
        self.ingress_mac.update(sxor(aes, header_ciphertext))
        expected_header_mac = self.ingress_mac.digest()[:HEADER_LEN]
        if not bytes_eq(expected_header_mac, header_mac):
            raise DecryptionError('Invalid header mac')
        return self.aes_dec.update(header_ciphertext)

    def decrypt_body(self, data: bytes, body_size: int) -> bytes:
        read_size = roundup_16(body_size)
        if len(data) < read_size + MAC_LEN:
            raise ValueError('Insufficient body length; Got {}, wanted {}'.format(
                len(data), (read_size + MAC_LEN)))

        frame_ciphertext = data[:read_size]
        frame_mac = data[read_size:read_size + MAC_LEN]

        self.ingress_mac.update(frame_ciphertext)
        fmac_seed = self.ingress_mac.digest()[:MAC_LEN]
        self.ingress_mac.update(sxor(self.mac_enc(fmac_seed), fmac_seed))
        expected_frame_mac = self.ingress_mac.digest()[:MAC_LEN]
        if not bytes_eq(expected_frame_mac, frame_mac):
            raise DecryptionError('Invalid frame mac')
        return self.aes_dec.update(frame_ciphertext)[:body_size]

    def get_frame_size(self, header: bytes) -> int:
        # The frame size is encoded in the header as a 3-byte int, so before we unpack we need
        # to prefix it with an extra byte.
        encoded_size = b'\x00' + header[:3]
        (size,) = struct.unpack(b'>I', encoded_size)
        return size

    def send(self, header: bytes, body: bytes) -> None:
        cmd_id = rlp.decode(body[:1], sedes=sedes.big_endian_int)
        self.logger.debug("Sending msg with cmd_id: %s", cmd_id)
        self.writer.write(self.encrypt(header, body))

    def disconnect(self, reason: DisconnectReason) -> None:
        """Send a disconnect msg to the remote node and stop this Peer.

        :param reason: An item from the DisconnectReason enum.
        """
        if not isinstance(reason, DisconnectReason):
            self.logger.debug("Disconnecting from remote peer; reason: %s", reason.value)
            raise ValueError(
                "Reason must be an item of DisconnectReason, got {}".format(reason))
        self.base_protocol.send_disconnect(reason.value)
        self.close()

    def select_sub_protocol(self, remote_capabilities: List[Tuple[bytes, int]]
                            ) -> protocol.Protocol:
        """Select the sub-protocol to use when talking to the remote.

        Find the highest version of our supported sub-protocols that is also supported by the
        remote and stores an instance of it (with the appropriate cmd_id offset) in
        self.sub_proto.

        Raises NoMatchingPeerCapabilities if none of our supported protocols match one of the
        remote's protocols.
        """
        matching_capabilities = set(self.capabilities).intersection(remote_capabilities)
        if not matching_capabilities:
            raise NoMatchingPeerCapabilities()
        _, highest_matching_version = max(matching_capabilities, key=operator.itemgetter(1))
        offset = self.base_protocol.cmd_length
        for proto_class in self._supported_sub_protocols:
            if proto_class.version == highest_matching_version:
                return proto_class(self, offset)
        raise NoMatchingPeerCapabilities()

    def __str__(self):
        return "{} {}".format(self.__class__.__name__, self.remote)


class LESPeer(BasePeer):
    max_headers_fetch = les.MAX_HEADERS_FETCH
    _supported_sub_protocols = [les.LESProtocol, les.LESProtocolV2]
    sub_proto = None  # type: les.LESProtocol
    head_info = None  # type: les.HeadInfo

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending_replies = {}  # type: Dict[int, Callable[[protocol._DecodedMsgType], None]]

    async def send_sub_proto_handshake(self):
        self.sub_proto.send_handshake(await self._local_chain_info)

    async def process_sub_proto_handshake(
            self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        if not isinstance(cmd, (les.Status, les.StatusV2)):
            self.disconnect(DisconnectReason.other)
            raise HandshakeFailure(
                "Expected a LES Status msg, got {}, disconnecting".format(cmd))
        msg = cast(Dict[str, Any], msg)
        if msg['networkId'] != self.network_id:
            self.disconnect(DisconnectReason.other)
            raise HandshakeFailure(
                "{} network ({}) does not match ours ({}), disconnecting".format(
                    self, msg['networkId'], self.network_id))
        genesis = await self.genesis
        if msg['genesisHash'] != genesis.hash:
            self.disconnect(DisconnectReason.other)
            raise HandshakeFailure(
                "{} genesis ({}) does not match ours ({}), disconnecting".format(
                    self, encode_hex(msg['genesisHash']), genesis.hex_hash))
        # TODO: Disconnect if the remote doesn't serve headers.
        self.head_info = cmd.as_head_info(msg)

    def handle_sub_proto_msg(self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        if isinstance(msg, dict):
            request_id = msg.get('request_id')
            if request_id is not None and request_id in self._pending_replies:
                # This is a reply we're waiting for, so we consume it by passing it to the
                # registered callback.
                callback = self._pending_replies.pop(request_id)
                callback(msg)
                return
        super().handle_sub_proto_msg(cmd, msg)

    async def _wait_for_reply(self, request_id: int, cancel_token: CancelToken) -> Dict[str, Any]:
        reply = None
        got_reply = asyncio.Event()

        def callback(r):
            nonlocal reply
            reply = r
            got_reply.set()

        self._pending_replies[request_id] = callback
        combined_token = self.cancel_token.chain(cancel_token)
        await wait_with_token(got_reply.wait(), token=combined_token, timeout=self.reply_timeout)
        return reply

    async def get_block_header_by_hash(
            self, block_hash: bytes, cancel_token: CancelToken) -> BlockHeader:
        request_id = gen_request_id()
        max_headers = 1
        self.sub_proto.send_get_block_headers(block_hash, max_headers, request_id)
        reply = await self._wait_for_reply(request_id, cancel_token)
        if not reply['headers']:
            raise BlockNotFound("Peer {} has no block with hash {}".format(self, block_hash))
        return reply['headers'][0]

    async def get_block_by_hash(
            self, block_hash: bytes, cancel_token: CancelToken) -> BlockBody:
        request_id = gen_request_id()
        self.sub_proto.send_get_block_bodies([block_hash], request_id)
        reply = await self._wait_for_reply(request_id, cancel_token)
        if not reply['bodies']:
            raise BlockNotFound("Peer {} has no block with hash {}".format(self, block_hash))
        return reply['bodies'][0]

    async def get_receipts(self, block_hash: bytes, cancel_token: CancelToken) -> List[Receipt]:
        request_id = gen_request_id()
        self.sub_proto.send_get_receipts(block_hash, request_id)
        reply = await self._wait_for_reply(request_id, cancel_token)
        if not reply['receipts']:
            raise BlockNotFound("No block with hash {} found".format(block_hash))
        return reply['receipts'][0]

    async def get_account(
            self, block_hash: bytes, address: bytes, cancel_token: CancelToken) -> Account:
        key = keccak(address)
        proof = await self._get_proof(cancel_token, block_hash, account_key=b'', key=key)
        header = await self.get_block_header_by_hash(block_hash, cancel_token)
        rlp_account = HexaryTrie.get_from_proof(header.state_root, key, proof)
        return rlp.decode(rlp_account, sedes=Account)

    async def _get_proof(self,
                         cancel_token: CancelToken,
                         block_hash: bytes,
                         account_key: bytes,
                         key: bytes,
                         from_level: int = 0) -> List[bytes]:
        request_id = gen_request_id()
        self.sub_proto.send_get_proof(block_hash, account_key, key, from_level, request_id)
        reply = await self._wait_for_reply(request_id, cancel_token)
        return reply['proof']

    async def get_contract_code(
            self, block_hash: bytes, key: bytes, cancel_token: CancelToken) -> bytes:
        request_id = gen_request_id()
        self.sub_proto.send_get_contract_code(block_hash, key, request_id)
        reply = await self._wait_for_reply(request_id, cancel_token)
        if not reply['codes']:
            return b''
        return reply['codes'][0]

    async def fetch_headers_starting_at(
            self, start_block: int, cancel_token: CancelToken) -> List[BlockHeader]:
        """Fetches up to self.max_headers_fetch starting at start_block.

        Returns a list containing those headers in ascending order of block number.
        """
        request_id = gen_request_id()
        self.sub_proto.send_get_block_headers(
            start_block, self.max_headers_fetch, request_id, reverse=False)
        reply = await self._wait_for_reply(request_id, cancel_token)
        if not reply['headers']:
            raise EmptyGetBlockHeadersReply(
                "No headers in reply. start_block=={}".format(start_block))
        self.logger.info(
            "fetched headers from %s to %s", reply['headers'][0].block_number,
            reply['headers'][-1].block_number)
        return reply['headers']


class ETHPeer(BasePeer):
    _supported_sub_protocols = [eth.ETHProtocol]
    sub_proto = None  # type: eth.ETHProtocol
    head_td = None  # type: int
    head_hash = None  # type: Hash32

    async def send_sub_proto_handshake(self):
        self.sub_proto.send_handshake(await self._local_chain_info)

    async def process_sub_proto_handshake(
            self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        if not isinstance(cmd, eth.Status):
            self.disconnect(DisconnectReason.other)
            raise HandshakeFailure(
                "Expected a ETH Status msg, got {}, disconnecting".format(cmd))
        msg = cast(Dict[str, Any], msg)
        if msg['network_id'] != self.network_id:
            self.disconnect(DisconnectReason.other)
            raise HandshakeFailure(
                "{} network ({}) does not match ours ({}), disconnecting".format(
                    self, msg['network_id'], self.network_id))
        genesis = await self.genesis
        if msg['genesis_hash'] != genesis.hash:
            self.disconnect(DisconnectReason.other)
            raise HandshakeFailure(
                "{} genesis ({}) does not match ours ({}), disconnecting".format(
                    self, encode_hex(msg['genesis_hash']), genesis.hex_hash))
        self.head_td = msg['td']
        self.head_hash = msg['best_hash']


class PeerPoolSubscriber(metaclass=ABCMeta):

    @abstractmethod
    def register_peer(self, peer: BasePeer) -> None:
        raise NotImplementedError("Must be implemented by subclasses")


class PeerPool(BaseService):
    """PeerPool attempts to keep connections to at least min_peers on the given network."""
    logger = logging.getLogger("p2p.peer.PeerPool")
    _connect_loop_sleep = 2
    _last_lookup = 0  # type: float
    _lookup_interval = 20  # type: int

    def __init__(self,
                 peer_class: Type[BasePeer],
                 headerdb: 'BaseAsyncHeaderDB',
                 network_id: int,
                 privkey: datatypes.PrivateKey,
                 discovery: DiscoveryProtocol,
                 min_peers: int = DEFAULT_MIN_PEERS,
                 ) -> None:
        super().__init__()
        self.peer_class = peer_class
        self.headerdb = headerdb
        self.network_id = network_id
        self.privkey = privkey
        self.discovery = discovery
        self.min_peers = min_peers
        self.connected_nodes = {}  # type: Dict[Node, BasePeer]
        self._subscribers = []  # type: List[PeerPoolSubscriber]

    def get_nodes_to_connect(self) -> Generator[Node, None, None]:
        return self.discovery.get_random_nodes(self.min_peers)

    def subscribe(self, subscriber: PeerPoolSubscriber) -> None:
        self._subscribers.append(subscriber)
        for peer in self.connected_nodes.values():
            subscriber.register_peer(peer)

    def unsubscribe(self, subscriber: PeerPoolSubscriber) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def start_peer(self, peer):
        asyncio.ensure_future(peer.run(finished_callback=self._peer_finished))
        self.add_peer(peer)

    def add_peer(self, peer):
        self.logger.debug('Adding peer (%s) ...', str(peer))
        self.connected_nodes[peer.remote] = peer
        self.logger.debug('Number of peers: %d', len(self.connected_nodes))
        for subscriber in self._subscribers:
            subscriber.register_peer(peer)

    async def _run(self) -> None:
        self.logger.info("Running PeerPool...")
        while not self.cancel_token.triggered:
            await self.maybe_connect_to_more_peers()
            # Wait self._connect_loop_sleep seconds, unless we're asked to stop.
            await wait_with_token(
                asyncio.sleep(self._connect_loop_sleep), token=self.cancel_token)

    async def stop_all_peers(self) -> None:
        self.logger.info("Stopping all peers ...")
        await asyncio.gather(
            *[peer.cancel() for peer in self.connected_nodes.values()])

    async def _cleanup(self) -> None:
        await self.stop_all_peers()

    async def connect(self, remote: Node) -> BasePeer:
        """
        Connect to the given remote and return a Peer instance when successful.
        Returns None if the remote is unreachable, times out or is useless.
        """
        if remote in self.connected_nodes:
            self.logger.debug("Skipping %s; already connected to it", remote)
            return None
        expected_exceptions = (UnreachablePeer, TimeoutError, PeerConnectionLost, HandshakeFailure)
        try:
            self.logger.debug("Connecting to %s...", remote)
            peer = await handshake(
                remote, self.privkey, self.peer_class, self.headerdb, self.network_id,
                self.cancel_token)
            return peer
        except OperationCancelled:
            # Pass it on to instruct our main loop to stop.
            raise
        except expected_exceptions as e:
            self.logger.debug("Could not complete handshake with %s: %s", remote, repr(e))
        except Exception:
            self.logger.exception("Unexpected error during auth/p2p handshake with %s", remote)
        return None

    async def lookup_random_node(self) -> None:
        # This method runs in the background, so we must catch OperationCancelled here otherwise
        # asyncio will warn that its exception was never retrieved.
        try:
            await self.discovery.lookup_random(self.cancel_token)
        except OperationCancelled:
            pass
        self._last_lookup = time.time()

    async def maybe_connect_to_more_peers(self) -> None:
        """Connect to more peers if we're not yet connected to at least self.min_peers."""
        if len(self.connected_nodes) >= self.min_peers:
            self.logger.debug(
                "Already connected to %s peers: %s; sleeping",
                len(self.connected_nodes),
                [remote for remote in self.connected_nodes])
            return

        if self._last_lookup + self._lookup_interval < time.time():
            self.logger.debug("Last node discovery lookup too long ago, triggering another")
            asyncio.ensure_future(self.lookup_random_node())

        await self._connect_to_nodes(self.get_nodes_to_connect())

        # In some cases (e.g ROPSTEN or private testnets), the discovery table might be full of
        # bad peers so if we can't connect to any peers we try a random bootstrap node as well.
        if not self.peers:
            await self._connect_to_nodes(self._get_random_bootnode())

    def _get_random_bootnode(self) -> Generator[Node, None, None]:
        if self.discovery.bootstrap_nodes:
            yield random.choice(self.discovery.bootstrap_nodes)
        else:
            self.logger.warning('No bootstrap_nodes')

    async def _connect_to_nodes(self, nodes: Generator[Node, None, None]) -> None:
        for node in nodes:
            # TODO: Consider changing connect() to raise an exception instead of returning None,
            # as discussed in
            # https://github.com/ethereum/py-evm/pull/139#discussion_r152067425
            peer = await self.connect(node)
            if peer is not None:
                self.logger.info("Successfully connected to %s", peer)
                self.start_peer(peer)
                if len(self.connected_nodes) >= self.min_peers:
                    return

    def _peer_finished(self, peer: BaseService) -> None:
        """Remove the given peer from our list of connected nodes.
        This is passed as a callback to be called when a peer finishes.
        """
        peer = cast(BasePeer, peer)
        if peer.remote in self.connected_nodes:
            self.connected_nodes.pop(peer.remote)

    @property
    def peers(self) -> List[BasePeer]:
        peers = list(self.connected_nodes.values())
        # Shuffle the list of peers so that dumb callsites are less likely to send all requests to
        # a single peer even if they always pick the first one from the list.
        random.shuffle(peers)
        return peers

    async def get_random_peer(self) -> BasePeer:
        while not self.peers:
            self.logger.debug("No connected peers, sleeping a bit")
            await asyncio.sleep(0.5)
        return random.choice(self.peers)


class HardCodedNodesPeerPool(PeerPool):
    """A PeerPool that uses a hard-coded list of remote nodes to connect to.

    The node discovery v4 protocol is terrible at finding LES nodes, so for now we hard-code some
    nodes that seem to have a good uptime.
    """

    def _get_random_bootnode(self) -> Generator[Node, None, None]:
        # We don't have a DiscoveryProtocol with bootnodes, so just return one of our regular
        # hardcoded nodes.
        yield random.choice(list(self.get_nodes_to_connect()))

    async def lookup_random_node(self) -> None:
        # Do nothing as we don't have a DiscoveryProtocol
        pass

    def get_nodes_to_connect(self) -> Generator[Node, None, None]:
        from evm.chains.ropsten import RopstenChain
        from evm.chains.mainnet import MainnetChain
        if self.network_id == MainnetChain.network_id:
            nodes = [
                Node(keys.PublicKey(decode_hex("1118980bf48b0a3640bdba04e0fe78b1add18e1cd99bf22d53daac1fd9972ad650df52176e7c7d89d1114cfef2bc23a2959aa54998a46afcf7d91809f0855082")),  # noqa: E501
                     Address("52.74.57.123", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("78de8a0916848093c73790ead81d1928bec737d565119932b98c6b100d944b7a95e94f847f689fc723399d2e31129d182f7ef3863f2b4c820abbf3ab2722344d")),  # noqa: E501
                     Address("191.235.84.50", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("ddd81193df80128880232fc1deb45f72746019839589eeb642d3d44efbb8b2dda2c1a46a348349964a6066f8afb016eb2a8c0f3c66f32fadf4370a236a4b5286")),  # noqa: E501
                     Address("52.231.202.145", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("3f1d12044546b76342d59d4a05532c14b85aa669704bfe1f864fe079415aa2c02d743e03218e57a33fb94523adb54032871a6c51b2cc5514cb7c7e35b3ed0a99")),  # noqa: E501
                     Address("13.93.211.84", 30303, 30303)),
            ]
        elif self.network_id == RopstenChain.network_id:
            nodes = [
                Node(keys.PublicKey(decode_hex("60ce95dc5b6873e1c53897815496c28132fa50a1227935c58fbffc30a25bf9df68594f7bdc63b1d33c2911c96013b5b058dcfc9184a78082e9af5ace05fe5486")),  # noqa: E501
                     Address("79.98.29.93", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("a147a3adde1daddc0d86f44f1a76404914e44cee018c26d49248142d4dc8a9fb0e7dd14b5153df7e60f23b037922ae1f33b8f318844ef8d2b0453b9ab614d70d")),  # noqa: E501
                     Address("72.36.89.11", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("d8714127db3c10560a2463c557bbe509c99969078159c69f9ce4f71c2cd1837bcd33db3b9c3c3e88c971b4604bbffa390a0a7f53fc37f122e2e6e0022c059dfd")),  # noqa: E501
                     Address("51.15.217.106", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("efc75f109d91cdebc62f33be992ca86fce2637044d49a954a8bdceb439b1239afda32e642456e9dfd759af5b440ef4d8761b9bda887e2200001c5f3ab2614043")),  # noqa: E501
                     Address("34.228.166.142", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("c8b9ec645cd7fe570bc73740579064c528771338c31610f44d160d2ae63fd00699caa163f84359ab268d4a0aed8ead66d7295be5e9c08b0ec85b0198273bae1f")),  # noqa: E501
                     Address("178.62.246.6", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("7a34c02d5ef9de43475580cbb88fb492afb2858cfc45f58cf5c7088ceeded5f58e65be769b79c31c5ae1f012c99b3e9f2ea9ef11764d553544171237a691493b")),  # noqa: E501
                     Address("35.227.38.243", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("bbb3ad8be9684fa1d67ac057d18f7357dd236dc01a806fef6977ac9a259b352c00169d092c50475b80aed9e28eff12d2038e97971e0be3b934b366e86b59a723")),  # noqa: E501
                     Address("81.169.153.213", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("30b7ab30a01c124a6cceca36863ece12c4f5fa68e3ba9b0b51407ccc002eeed3b3102d20a88f1c1d3c3154e2449317b8ef95090e77b312d5cc39354f86d5d606")),  # noqa: E501
                     Address("52.176.7.10", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("02508da84b37a1b7f19f77268e5b69acc9e9ab6989f8e5f2f8440e025e633e4277019b91884e46821414724e790994a502892144fc1333487ceb5a6ce7866a46")),  # noqa: E501
                     Address("54.175.255.230", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("0eec3472a46f0b637045e41f923ce1d4a585cd83c1c7418b183c46443a0df7405d020f0a61891b2deef9de35284a0ad7d609db6d30d487dbfef72f7728d09ca9")),  # noqa: E501
                     Address("181.168.193.197", 30303, 30303)),
                Node(keys.PublicKey(decode_hex("643c31104d497e3d4cd2460ff0dbb1fb9a6140c8bb0fca66159bbf177d41aefd477091c866494efd3f1f59a0652c93ab2f7bb09034ed5ab9f2c5c6841aef8d94")),  # noqa: E501
                     Address("34.198.237.7", 30303, 30303)),
            ]
        else:
            raise ValueError("Unknown network_id: {}".format(self.network_id))

        random.shuffle(nodes)
        for node in nodes:
            yield node


class ChainInfo:
    def __init__(self, block_number, block_hash, total_difficulty, genesis_hash):
        self.block_number = block_number
        self.block_hash = block_hash
        self.total_difficulty = total_difficulty
        self.genesis_hash = genesis_hash


def _test():
    """
    Create a Peer instance connected to a local geth instance and log messages exchanged with it.

    Use the following command line to run geth:

        ./build/bin/geth -vmodule p2p=4,p2p/discv5=0,eth/*=0 \
          -nodekeyhex 45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8 \
          -testnet -lightserv 90
    """
    import argparse
    import signal
    from evm.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER
    from evm.db.backends.memory import MemoryDB
    from tests.p2p.integration_test_helpers import FakeAsyncHeaderDB
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

    # The default remoteid can be used if you pass nodekeyhex as above to geth.
    nodekey = keys.PrivateKey(decode_hex(
        "45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8"))
    remoteid = nodekey.public_key.to_hex()
    parser = argparse.ArgumentParser()
    parser.add_argument('-remoteid', type=str, default=remoteid)
    parser.add_argument('-light', action='store_true', help="Connect as a light node")
    args = parser.parse_args()

    peer_class = ETHPeer  # type: ignore
    if args.light:
        peer_class = LESPeer  # type: ignore
    remote = Node(
        keys.PublicKey(decode_hex(args.remoteid)),
        Address('127.0.0.1', 30303, 30303))
    headerdb = FakeAsyncHeaderDB(MemoryDB())
    headerdb.persist_header(ROPSTEN_GENESIS_HEADER)
    network_id = RopstenChain.network_id
    loop = asyncio.get_event_loop()
    peer = loop.run_until_complete(
        handshake(remote, ecies.generate_privkey(), peer_class, headerdb, network_id,
                  CancelToken("Peer test")))

    async def request_stuff():
        # Request some stuff from ropsten's block 2440319
        # (https://ropsten.etherscan.io/block/2440319), just as a basic test.
        nonlocal peer
        block_hash = decode_hex(
            '0x59af08ab31822c992bb3dad92ddb68d820aa4c69e9560f07081fa53f1009b152')
        if peer_class == ETHPeer:
            peer = cast(ETHPeer, peer)
            peer.sub_proto.send_get_block_headers(block_hash, 1)
            peer.sub_proto.send_get_block_bodies([block_hash])
            peer.sub_proto.send_get_receipts([block_hash])
        else:
            peer = cast(LESPeer, peer)
            request_id = 1
            peer.sub_proto.send_get_block_headers(block_hash, 1, request_id)
            peer.sub_proto.send_get_block_bodies([block_hash], request_id + 1)
            peer.sub_proto.send_get_receipts(block_hash, request_id + 2)

    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, sigint_received.set)

    async def exit_on_sigint():
        await sigint_received.wait()
        await peer.cancel()
        loop.stop()

    asyncio.ensure_future(exit_on_sigint())
    asyncio.ensure_future(request_stuff())
    asyncio.ensure_future(peer.run())
    loop.run_forever()
    loop.close()


if __name__ == "__main__":
    _test()
