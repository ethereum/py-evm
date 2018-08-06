import asyncio
import collections
import contextlib
import datetime
import functools
import logging
import operator
import random
import struct
from abc import (
    ABC,
    abstractmethod
)

from typing import (
    Any,
    AsyncIterable,
    AsyncIterator,
    cast,
    Dict,
    Iterator,
    List,
    Set,
    TYPE_CHECKING,
    Tuple,
    Type,
)

import sha3

from cytoolz import groupby

import rlp

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.constant_time import bytes_eq

from eth_utils import (
    decode_hex,
    to_tuple,
)

from eth_typing import BlockNumber, Hash32

from eth_keys import (
    datatypes,
    keys,
)

from cancel_token import CancelToken, OperationCancelled

from eth.chains.mainnet import MAINNET_NETWORK_ID
from eth.chains.ropsten import ROPSTEN_NETWORK_ID
from eth.constants import GENESIS_BLOCK_NUMBER
from eth.exceptions import ValidationError as EthValidationError
from eth.rlp.headers import BlockHeader
from eth.vm.base import BaseVM
from eth.vm.forks import HomesteadVM

from p2p import auth
from p2p import ecies
from p2p import protocol
from p2p.kademlia import Address, Node
from p2p.exceptions import (
    BadAckMessage,
    DAOForkCheckFailure,
    DecryptionError,
    HandshakeFailure,
    MalformedMessage,
    NoConnectedPeers,
    NoMatchingPeerCapabilities,
    PeerConnectionLost,
    RemoteDisconnected,
    UnexpectedMessage,
    UnknownProtocolCommand,
    UnreachablePeer,
    ValidationError,
)
from p2p.service import BaseService
from p2p.utils import (
    get_devp2p_cmd_id,
    roundup_16,
    sxor,
    time_since,
)
from p2p.p2p_proto import (
    Disconnect,
    DisconnectReason,
    Hello,
    P2PProtocol,
    Ping,
    Pong,
)

from .constants import (
    CHAIN_SPLIT_CHECK_TIMEOUT,
    CONN_IDLE_TIMEOUT,
    DEFAULT_MAX_PEERS,
    HEADER_LEN,
    MAC_LEN,
)

if TYPE_CHECKING:
    from trinity.db.header import BaseAsyncHeaderDB  # noqa: F401
    from trinity.protocol.eth.requests import HeaderRequest  # noqa: F401
    from trinity.protocol.base_request import BaseRequest  # noqa: F401


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
        raise UnreachablePeer() from e
    peer = peer_class(
        remote=remote, privkey=privkey, reader=reader, writer=writer,
        aes_secret=aes_secret, mac_secret=mac_secret, egress_mac=egress_mac,
        ingress_mac=ingress_mac, headerdb=headerdb, network_id=network_id)
    await peer.do_p2p_handshake()
    await peer.do_sub_proto_handshake()
    return peer


class BasePeer(BaseService):
    conn_idle_timeout = CONN_IDLE_TIMEOUT
    # Must be defined in subclasses. All items here must be Protocol classes representing
    # different versions of the same P2P sub-protocol (e.g. ETH, LES, etc).
    _supported_sub_protocols: List[Type[protocol.Protocol]] = []
    # FIXME: Must be configurable.
    listen_port = 30303
    # Will be set upon the successful completion of a P2P handshake.
    sub_proto: protocol.Protocol = None
    head_td: int = None
    head_hash: Hash32 = None

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
                 inbound: bool = False,
                 ) -> None:
        super().__init__()
        self.remote = remote
        self.privkey = privkey
        self.reader = reader
        self.writer = writer
        self.base_protocol = P2PProtocol(self)
        self.headerdb = headerdb
        self.network_id = network_id
        self.inbound = inbound
        self._subscribers: List[PeerSubscriber] = []
        self.start_time = datetime.datetime.now()
        self.received_msgs: Dict[protocol.Command, int] = collections.defaultdict(int)

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
    async def send_sub_proto_handshake(self) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    async def process_sub_proto_handshake(
            self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    @contextlib.contextmanager
    def collect_sub_proto_messages(self) -> Iterator['MsgBuffer']:
        """
        Can be used to gather up all messages that are sent to the peer.
        """
        if not self.is_running:
            raise RuntimeError("Cannot collect messages if peer is not running")
        msg_buffer = MsgBuffer()

        with msg_buffer.subscribe_peer(self):
            yield msg_buffer

    @property
    def received_msgs_count(self) -> int:
        return sum(self.received_msgs.values())

    @property
    def uptime(self) -> str:
        return '%d:%02d:%02d:%02d' % time_since(self.start_time)

    def add_subscriber(self, subscriber: 'PeerSubscriber') -> None:
        self._subscribers.append(subscriber)

    def remove_subscriber(self, subscriber: 'PeerSubscriber') -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    async def do_sub_proto_handshake(self) -> None:
        """Perform the handshake for the sub-protocol agreed with the remote peer.

        Raises HandshakeFailure if the handshake is not successful.
        """
        await self.send_sub_proto_handshake()
        cmd, msg = await self.read_msg()
        if isinstance(cmd, Ping):
            # Parity sends a Ping before the sub-proto handshake, so respond to that and read the
            # next one, which hopefully will be the actual handshake.
            self.base_protocol.send_pong()
            cmd, msg = await self.read_msg()
        if isinstance(cmd, Disconnect):
            msg = cast(Dict[str, Any], msg)
            # Peers sometimes send a disconnect msg before they send the sub-proto handshake.
            raise HandshakeFailure(
                "{} disconnected before completing sub-proto handshake: {}".format(
                    self, msg['reason_name']))
        await self.process_sub_proto_handshake(cmd, msg)
        self.logger.debug("Finished %s handshake with %s", self.sub_proto, self.remote)

    async def do_p2p_handshake(self) -> None:
        """Perform the handshake for the P2P base protocol.

        Raises HandshakeFailure if the handshake is not successful.
        """
        self.base_protocol.send_handshake()

        try:
            cmd, msg = await self.read_msg()
        except rlp.DecodingError:
            raise HandshakeFailure("Got invalid rlp data during handshake")
        except MalformedMessage as e:
            raise HandshakeFailure("Got malformed message during handshake") from e

        if isinstance(cmd, Disconnect):
            msg = cast(Dict[str, Any], msg)
            # Peers sometimes send a disconnect msg before they send the initial P2P handshake.
            raise HandshakeFailure("{} disconnected before completing handshake: {}".format(
                self, msg['reason_name']))
        await self.process_p2p_handshake(cmd, msg)

    @property
    async def genesis(self) -> BlockHeader:
        genesis_hash = await self.wait(
            self.headerdb.coro_get_canonical_block_hash(BlockNumber(GENESIS_BLOCK_NUMBER)))
        return await self.wait(self.headerdb.coro_get_block_header_by_hash(genesis_hash))

    @property
    async def _local_chain_info(self) -> 'ChainInfo':
        genesis = await self.genesis
        head = await self.wait(self.headerdb.coro_get_canonical_head())
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
        self.logger.trace("Got msg with cmd_id: %s", cmd_id)
        if cmd_id < self.base_protocol.cmd_length:
            return self.base_protocol.cmd_by_id[cmd_id]
        elif cmd_id < self.sub_proto.cmd_id_offset + self.sub_proto.cmd_length:
            return self.sub_proto.cmd_by_id[cmd_id]
        else:
            raise UnknownProtocolCommand("No protocol found for cmd_id {}".format(cmd_id))

    async def read(self, n: int) -> bytes:
        self.logger.trace("Waiting for %s bytes from %s", n, self.remote)
        try:
            return await self.wait(self.reader.readexactly(n), timeout=self.conn_idle_timeout)
        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError) as e:
            raise PeerConnectionLost(repr(e))

    def close(self) -> None:
        """Close this peer's reader/writer streams.

        This will cause the peer to stop in case it is running.

        If the streams have already been closed, do nothing.
        """
        if self.reader.at_eof():
            return
        self.reader.feed_eof()
        self.writer.close()

    @property
    def is_closing(self) -> bool:
        return self.writer.transport.is_closing()

    async def _cleanup(self) -> None:
        self.close()

    async def _run(self) -> None:
        while True:
            try:
                cmd, msg = await self.read_msg()
            except (PeerConnectionLost, TimeoutError) as err:
                self.logger.debug(
                    "%s stopped responding (%r), disconnecting", self.remote, err)
                return
            except DecryptionError as err:
                self.logger.warn(
                    "Unable to decrypt message from %s, disconnecting: %r",
                    self, err,
                    exc_info=True,
                )
                return

            try:
                self.process_msg(cmd, msg)
            except RemoteDisconnected as e:
                self.logger.debug("%s disconnected: %s", self, e)
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
        # NOTE: This used to be a bottleneck but it doesn't seem to be so anymore. If we notice
        # too much time is being spent on this again, we need to consider running this in a
        # ProcessPoolExecutor(). Need to make sure we don't use all CPUs in the machine for that,
        # though, otherwise asyncio's event loop can't run and we can't keep up with other peers.
        try:
            decoded_msg = cast(Dict[str, Any], cmd.decode(msg))
        except MalformedMessage as err:
            self.logger.debug(
                "Malformed message from peer %s: CMD:%s Error: %r",
                self, type(cmd).__name__, err,
            )
            raise
        else:
            self.logger.trace("Successfully decoded %s msg: %s", cmd, decoded_msg)
            self.received_msgs[cmd] += 1
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
        cmd_type = type(cmd)

        if self._subscribers:
            was_added = tuple(
                subscriber.add_msg((self, cmd, msg))
                for subscriber
                in self._subscribers
            )
            if not any(was_added):
                self.logger.warn(
                    "Peer %s has no subscribers for msg type %s",
                    self,
                    cmd_type.__name__,
                )
        else:
            self.logger.warn("Peer %s has no subscribers, discarding %s msg", self, cmd)

    def process_msg(self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        if cmd.is_base_protocol:
            self.handle_p2p_msg(cmd, msg)
        else:
            self.handle_sub_proto_msg(cmd, msg)

    async def process_p2p_handshake(
            self, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        msg = cast(Dict[str, Any], msg)
        if not isinstance(cmd, Hello):
            await self.disconnect(DisconnectReason.bad_protocol)
            raise HandshakeFailure("Expected a Hello msg, got {}, disconnecting".format(cmd))
        remote_capabilities = msg['capabilities']
        try:
            self.sub_proto = self.select_sub_protocol(remote_capabilities)
        except NoMatchingPeerCapabilities:
            await self.disconnect(DisconnectReason.useless_peer)
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
            raise DecryptionError('Invalid header mac: expected %s, got %s'.format(
                expected_header_mac, header_mac))
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
            raise DecryptionError('Invalid frame mac: expected %s, got %s'.format(
                expected_frame_mac, frame_mac))
        return self.aes_dec.update(frame_ciphertext)[:body_size]

    def get_frame_size(self, header: bytes) -> int:
        # The frame size is encoded in the header as a 3-byte int, so before we unpack we need
        # to prefix it with an extra byte.
        encoded_size = b'\x00' + header[:3]
        (size,) = struct.unpack(b'>I', encoded_size)
        return size

    def send(self, header: bytes, body: bytes) -> None:
        cmd_id = rlp.decode(body[:1], sedes=rlp.sedes.big_endian_int)
        self.logger.trace("Sending msg with cmd id %d to %s", cmd_id, self)
        if self.is_closing:
            self.logger.error(
                "Attempted to send msg with cmd id %d to disconnected peer %s", cmd_id, self)
            return
        self.writer.write(self.encrypt(header, body))

    async def disconnect(self, reason: DisconnectReason) -> None:
        """Send a disconnect msg to the remote node and stop this Peer.

        Also awaits for self.cancel() to ensure any pending tasks are cleaned up.

        :param reason: An item from the DisconnectReason enum.
        """
        if not isinstance(reason, DisconnectReason):
            raise ValueError(
                "Reason must be an item of DisconnectReason, got {}".format(reason))
        self.logger.debug("Disconnecting from remote peer; reason: %s", reason.name)
        self.base_protocol.send_disconnect(reason.value)
        self.close()
        if self.is_running:
            await self.cancel()

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

    def __str__(self) -> str:
        return "{} {}".format(self.__class__.__name__, self.remote)

    def __repr__(self) -> str:
        return "{} {}".format(self.__class__.__name__, repr(self.remote))

    def __hash__(self) -> int:
        return hash(self.remote)


class PeerSubscriber(ABC):
    _msg_queue: 'asyncio.Queue[PEER_MSG_TYPE]' = None

    @property
    @abstractmethod
    def subscription_msg_types(self) -> Set[Type[protocol.Command]]:
        """
        The `p2p.protocol.Command` types that this class subscribes to.  Any
        command which is not in this set will not be passed to this subscriber.

        The base command class `p2p.protocol.Command` can be used to enable
        **all** command types.

        .. note: This API only applies to sub-protocol commands.  Base protocol
        commands are handled exclusively at the peer level and cannot be
        consumed with this API.
        """
        pass

    @functools.lru_cache(maxsize=64)
    def is_subscription_command(self, cmd_type: Type[protocol.Command]) -> bool:
        return bool(self.subscription_msg_types.intersection(
            {cmd_type, protocol.Command}
        ))

    @property
    @abstractmethod
    def msg_queue_maxsize(self) -> int:
        pass

    def register_peer(self, peer: BasePeer) -> None:
        """
        Notify about each registered peer in the :class:`~p2p.peer.PeerPool`. Is called upon
        subscription for each :class:`~p2p.peer.BasePeer` that exists in the pool at that time and
        then for each :class:`~p2p.peer.BasePeer` that joins the pool later on.

        A :class:`~p2p.peer.PeerSubscriber` that wants to act upon peer registration needs to
        overwrite this method to provide an implementation.
        """
        pass

    def deregister_peer(self, peer: BasePeer) -> None:
        """Called when a peer is removed from the pool."""
        pass

    @property
    def msg_queue(self) -> 'asyncio.Queue[PEER_MSG_TYPE]':
        if self._msg_queue is None:
            self._msg_queue = asyncio.Queue(maxsize=self.msg_queue_maxsize)
        return self._msg_queue

    @property
    def queue_size(self) -> int:
        return self.msg_queue.qsize()

    def add_msg(self, msg: 'PEER_MSG_TYPE') -> bool:
        peer, cmd, _ = msg

        if not self.is_subscription_command(type(cmd)):
            self.logger.trace(  # type: ignore
                "Discarding %s msg from %s; not subscribed to msg type; "
                "subscriptions: %s",
                cmd, peer, self.subscription_msg_types,
            )
            return False

        try:
            self.logger.trace(  # type: ignore
                "Adding %s msg from %s to queue; queue_size=%d", cmd, peer, self.queue_size)
            self.msg_queue.put_nowait(msg)
            return True
        except asyncio.queues.QueueFull:
            self.logger.warn(  # type: ignore
                "%s msg queue is full; discarding %s msg from %s",
                self.__class__.__name__, cmd, peer)
            return False

    @contextlib.contextmanager
    def subscribe(self, peer_pool: 'PeerPool') -> Iterator[None]:
        peer_pool.subscribe(self)
        try:
            yield
        finally:
            peer_pool.unsubscribe(self)

    @contextlib.contextmanager
    def subscribe_peer(self, peer: BasePeer) -> Iterator[None]:
        peer.add_subscriber(self)
        try:
            yield
        finally:
            peer.remove_subscriber(self)


class MsgBuffer(PeerSubscriber):
    logger = logging.getLogger('p2p.peer.MsgBuffer')
    msg_queue_maxsize = 500
    subscription_msg_types = {protocol.Command}

    @to_tuple
    def get_messages(self) -> Iterator['PEER_MSG_TYPE']:
        while not self.msg_queue.empty():
            yield self.msg_queue.get_nowait()


class PeerPool(BaseService, AsyncIterable[BasePeer]):
    """
    PeerPool maintains connections to up-to max_peers on a given network.
    """
    _report_interval = 60

    def __init__(self,
                 peer_class: Type[BasePeer],
                 headerdb: 'BaseAsyncHeaderDB',
                 network_id: int,
                 privkey: datatypes.PrivateKey,
                 vm_configuration: Tuple[Tuple[int, Type[BaseVM]], ...],
                 max_peers: int = DEFAULT_MAX_PEERS,
                 token: CancelToken = None,
                 ) -> None:
        super().__init__(token)
        self.peer_class = peer_class
        self.headerdb = headerdb
        self.network_id = network_id
        self.privkey = privkey
        self.vm_configuration = vm_configuration
        self.max_peers = max_peers
        self.connected_nodes: Dict[Node, BasePeer] = {}
        self._subscribers: List[PeerSubscriber] = []

    def __len__(self) -> int:
        return len(self.connected_nodes)

    @property
    def is_full(self) -> bool:
        return len(self) >= self.max_peers

    def is_valid_connection_candidate(self, candidate: Node) -> bool:
        # connect to no more then 2 nodes with the same IP
        nodes_by_ip = groupby(
            operator.attrgetter('remote.address.ip'),
            self.connected_nodes.values(),
        )
        matching_ip_nodes = nodes_by_ip.get(candidate.address.ip, [])
        return len(matching_ip_nodes) <= 2

    def subscribe(self, subscriber: PeerSubscriber) -> None:
        self._subscribers.append(subscriber)
        for peer in self.connected_nodes.values():
            subscriber.register_peer(peer)
            peer.add_subscriber(subscriber)

    def unsubscribe(self, subscriber: PeerSubscriber) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)
        for peer in self.connected_nodes.values():
            peer.remove_subscriber(subscriber)

    async def start_peer(self, peer: BasePeer) -> None:
        asyncio.ensure_future(peer.run())
        await self.wait(peer.events.started.wait(), timeout=1)
        try:
            # Although connect() may seem like a more appropriate place to perform the DAO fork
            # check, we do it here because we want to perform it for incoming peer connections as
            # well.
            with peer.collect_sub_proto_messages() as buffer:
                await self.ensure_same_side_on_dao_fork(peer)
        except DAOForkCheckFailure as err:
            self.logger.debug("DAO fork check with %s failed: %s", peer, err)
            await peer.disconnect(DisconnectReason.useless_peer)
            return
        else:
            msgs = tuple((cmd, msg) for _, cmd, msg in buffer.get_messages())
            self._add_peer(peer, msgs)

    def _add_peer(self,
                  peer: BasePeer,
                  msgs: Tuple[Tuple[protocol.Command, protocol._DecodedMsgType], ...]) -> None:
        """Add the given peer to the pool.

        Appart from adding it to our list of connected nodes and adding each of our subscriber's
        to the peer, we also add the given messages to our subscriber's queues.
        """
        self.logger.info('Adding %s to pool', peer)
        self.connected_nodes[peer.remote] = peer
        peer.add_finished_callback(self._peer_finished)
        for subscriber in self._subscribers:
            subscriber.register_peer(peer)
            peer.add_subscriber(subscriber)
            for cmd, msg in msgs:
                subscriber.add_msg((peer, cmd, msg))

    async def _run(self) -> None:
        # FIXME: PeerPool should probably no longer be a BaseService, but for now we're keeping it
        # so in order to ensure we cancel all peers when we terminate.
        asyncio.ensure_future(self._periodically_report_stats())
        await self.cancel_token.wait()

    async def stop_all_peers(self) -> None:
        self.logger.info("Stopping all peers ...")
        peers = self.connected_nodes.values()
        await asyncio.gather(*[peer.disconnect(DisconnectReason.client_quitting) for peer in peers])

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
        expected_exceptions = (
            HandshakeFailure,
            PeerConnectionLost,
            TimeoutError,
            UnreachablePeer,
        )
        try:
            self.logger.trace("Connecting to %s...", remote)
            # We use self.wait() as well as passing our CancelToken to handshake() as a workaround
            # for https://github.com/ethereum/py-evm/issues/670.
            peer = await self.wait(
                handshake(
                    remote, self.privkey, self.peer_class, self.headerdb, self.network_id,
                    self.cancel_token))

            return peer
        except OperationCancelled:
            # Pass it on to instruct our main loop to stop.
            raise
        except BadAckMessage:
            # This is kept separate from the `expected_exceptions` to be sure that we aren't
            # silencing an error in our authentication code.
            self.logger.info('Got bad auth ack from %r', remote)
        except expected_exceptions as e:
            self.logger.debug("Could not complete handshake with %r: %s", remote, repr(e))
        except Exception:
            self.logger.exception("Unexpected error during auth/p2p handshake with %r", remote)
        return None

    async def connect_to_nodes(self, nodes: Iterator[Node]) -> None:
        for node in nodes:
            if self.is_full:
                return

            # TODO: Consider changing connect() to raise an exception instead of returning None,
            # as discussed in
            # https://github.com/ethereum/py-evm/pull/139#discussion_r152067425
            peer = await self.connect(node)
            if peer is not None:
                await self.start_peer(peer)

    async def ensure_same_side_on_dao_fork(
            self, peer: BasePeer) -> None:
        """Ensure we're on the same side of the DAO fork as the given peer.

        In order to do that we have to request the DAO fork block and its parent, but while we
        wait for that we may receive other messages from the peer, which are returned so that they
        can be re-added to our subscribers' queues when the peer is finally added to the pool.
        """
        for start_block, vm_class in self.vm_configuration:
            if not issubclass(vm_class, HomesteadVM):
                continue
            elif not vm_class.support_dao_fork:
                break
            elif start_block > vm_class.dao_fork_block_number:
                # VM comes after the fork, so stop checking
                break

            start_block = vm_class.dao_fork_block_number - 1

            try:
                headers = await peer.requests.get_block_headers(  # type: ignore
                    start_block,
                    max_headers=2,
                    reverse=False,
                    timeout=CHAIN_SPLIT_CHECK_TIMEOUT,
                )

            except (TimeoutError, PeerConnectionLost) as err:
                raise DAOForkCheckFailure(
                    "Timed out waiting for DAO fork header from {}: {}".format(peer, err)
                ) from err
            except MalformedMessage as err:
                raise DAOForkCheckFailure(
                    "Malformed message while doing DAO fork check with {0}: {1}".format(
                        peer, err,
                    )
                ) from err
            except ValidationError as err:
                raise DAOForkCheckFailure(
                    "Invalid header response during DAO fork check: {}".format(err)
                ) from err

            if len(headers) != 2:
                raise DAOForkCheckFailure(
                    "Peer %s failed to return DAO fork check headers".format(peer)
                )
            else:
                parent, header = headers

            try:
                vm_class.validate_header(header, parent, check_seal=True)
            except EthValidationError as err:
                raise DAOForkCheckFailure("Peer failed DAO fork check validation: {}".format(err))

    def _peer_finished(self, peer: BaseService) -> None:
        """Remove the given peer from our list of connected nodes.
        This is passed as a callback to be called when a peer finishes.
        """
        peer = cast(BasePeer, peer)
        if peer.remote in self.connected_nodes:
            self.logger.info("%s finished, removing from pool", peer)
            self.connected_nodes.pop(peer.remote)
        else:
            self.logger.warn(
                "%s finished but was not found in connected_nodes (%s)", peer, self.connected_nodes)
        for subscriber in self._subscribers:
            subscriber.deregister_peer(peer)

    def __aiter__(self) -> AsyncIterator[BasePeer]:
        return ConnectedPeersIterator(tuple(self.connected_nodes.values()))

    @property
    def highest_td_peer(self) -> BasePeer:
        peers = tuple(self.connected_nodes.values())
        if not peers:
            raise NoConnectedPeers()
        peers_by_td = groupby(operator.attrgetter('head_td'), peers)
        max_td = max(peers_by_td.keys())
        return random.choice(peers_by_td[max_td])

    def get_peers(self, min_td: int) -> List[BasePeer]:
        # TODO: Consider turning this into a method that returns an AsyncIterator, to make it
        # harder for callsites to get a list of peers while making blocking calls, as those peers
        # might disconnect in the meantime.
        peers = tuple(self.connected_nodes.values())
        return [peer for peer in peers if peer.head_td >= min_td]

    async def _periodically_report_stats(self) -> None:
        while self.is_running:
            inbound_peers = len(
                [peer for peer in self.connected_nodes.values() if peer.inbound])
            self.logger.info("Connected peers: %d inbound, %d outbound",
                             inbound_peers, (len(self.connected_nodes) - inbound_peers))
            subscribers = len(self._subscribers)
            if subscribers:
                longest_queue = max(
                    self._subscribers, key=operator.attrgetter('queue_size'))
                self.logger.info(
                    "Peer subscribers: %d, longest queue: %s(%d)",
                    subscribers, longest_queue.__class__.__name__, longest_queue.queue_size)

            self.logger.debug("== Peer details == ")
            for peer in self.connected_nodes.values():
                most_received_type, count = max(
                    peer.received_msgs.items(), key=operator.itemgetter(1))
                self.logger.debug(
                    "%s: running=%s, uptime=%s, received_msgs=%d, most_received=%s(%d)",
                    peer, peer.is_running, peer.uptime, peer.received_msgs_count,
                    most_received_type, count)
            self.logger.debug("== End peer details == ")
            try:
                await self.wait(asyncio.sleep(self._report_interval))
            except OperationCancelled:
                break


class ConnectedPeersIterator(AsyncIterator[BasePeer]):

    def __init__(self, peers: Tuple[BasePeer, ...]) -> None:
        self.iter = iter(peers)

    async def __anext__(self) -> BasePeer:
        while True:
            # Yield control to ensure we process any disconnection requests from peers. Otherwise
            # we could return peers that should have been disconnected already.
            await asyncio.sleep(0)
            try:
                peer = next(self.iter)
                if not peer.is_closing:
                    return peer
            except StopIteration:
                raise StopAsyncIteration


DEFAULT_PREFERRED_NODES: Dict[int, Tuple[Node, ...]] = {
    MAINNET_NETWORK_ID: (
        Node(keys.PublicKey(decode_hex("1118980bf48b0a3640bdba04e0fe78b1add18e1cd99bf22d53daac1fd9972ad650df52176e7c7d89d1114cfef2bc23a2959aa54998a46afcf7d91809f0855082")),  # noqa: E501
             Address("52.74.57.123", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("78de8a0916848093c73790ead81d1928bec737d565119932b98c6b100d944b7a95e94f847f689fc723399d2e31129d182f7ef3863f2b4c820abbf3ab2722344d")),  # noqa: E501
             Address("191.235.84.50", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("ddd81193df80128880232fc1deb45f72746019839589eeb642d3d44efbb8b2dda2c1a46a348349964a6066f8afb016eb2a8c0f3c66f32fadf4370a236a4b5286")),  # noqa: E501
             Address("52.231.202.145", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("3f1d12044546b76342d59d4a05532c14b85aa669704bfe1f864fe079415aa2c02d743e03218e57a33fb94523adb54032871a6c51b2cc5514cb7c7e35b3ed0a99")),  # noqa: E501
             Address("13.93.211.84", 30303, 30303)),
    ),
    ROPSTEN_NETWORK_ID: (
        Node(keys.PublicKey(decode_hex("053d2f57829e5785d10697fa6c5333e4d98cc564dbadd87805fd4fedeb09cbcb642306e3a73bd4191b27f821fb442fcf964317d6a520b29651e7dd09d1beb0ec")),  # noqa: E501
             Address("79.98.29.154", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("94c15d1b9e2fe7ce56e458b9a3b672ef11894ddedd0c6f247e0f1d3487f52b66208fb4aeb8179fce6e3a749ea93ed147c37976d67af557508d199d9594c35f09")),  # noqa: E501
             Address("192.81.208.223", 30303, 30303)),
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
    ),
}


class ChainInfo:
    def __init__(self,
                 block_number: int,
                 block_hash: Hash32,
                 total_difficulty: int,
                 genesis_hash: Hash32) -> None:
        self.block_number = block_number
        self.block_hash = block_hash
        self.total_difficulty = total_difficulty
        self.genesis_hash = genesis_hash


PEER_MSG_TYPE = Tuple[BasePeer, protocol.Command, protocol._DecodedMsgType]


def _test() -> None:
    """
    Create a Peer instance connected to a local geth instance and log messages exchanged with it.

    Use the following command line to run geth:

        ./build/bin/geth -vmodule p2p=4,p2p/discv5=0,eth/*=0 \
          -nodekeyhex 45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8 \
          -testnet -lightserv 90
    """
    import argparse
    import signal
    from eth.utils.logging import TRACE_LEVEL_NUM
    from eth.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER, ROPSTEN_VM_CONFIGURATION
    from eth.db.backends.memory import MemoryDB
    from trinity.protocol.eth.peer import ETHPeer
    from trinity.protocol.eth.requests import HeaderRequest as ETHHeaderRequest
    from trinity.protocol.les.peer import LESPeer
    from trinity.protocol.les.requests import HeaderRequest as LESHeaderRequest
    from tests.p2p.integration_test_helpers import FakeAsyncHeaderDB, connect_to_peers_loop
    logging.basicConfig(level=TRACE_LEVEL_NUM, format='%(asctime)s %(levelname)s: %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('-enode', type=str, help="The enode we should connect to")
    parser.add_argument('-light', action='store_true', help="Connect as a light node")
    args = parser.parse_args()

    peer_class: Type[BasePeer] = ETHPeer
    if args.light:
        peer_class = LESPeer
    headerdb = FakeAsyncHeaderDB(MemoryDB())
    headerdb.persist_header(ROPSTEN_GENESIS_HEADER)
    network_id = RopstenChain.network_id
    loop = asyncio.get_event_loop()
    nodes = [Node.from_uri(args.enode)]
    peer_pool = PeerPool(
        peer_class, headerdb, network_id, ecies.generate_privkey(), ROPSTEN_VM_CONFIGURATION)
    asyncio.ensure_future(connect_to_peers_loop(peer_pool, nodes))

    async def request_stuff() -> None:
        # Request some stuff from ropsten's block 2440319
        # (https://ropsten.etherscan.io/block/2440319), just as a basic test.
        nonlocal peer_pool
        while not peer_pool.connected_nodes:
            peer_pool.logger.info("Waiting for peer connection...")
            await asyncio.sleep(0.2)
        peer = peer_pool.highest_td_peer
        block_hash = decode_hex(
            '0x59af08ab31822c992bb3dad92ddb68d820aa4c69e9560f07081fa53f1009b152')
        if peer_class == ETHPeer:
            peer = cast(ETHPeer, peer)
            peer.sub_proto.send_get_block_headers(ETHHeaderRequest(block_hash, 1, 0, False))
            peer.sub_proto.send_get_block_bodies([block_hash])
            peer.sub_proto.send_get_receipts([block_hash])
        else:
            peer = cast(LESPeer, peer)
            request_id = 1
            peer.sub_proto.send_get_block_headers(
                LESHeaderRequest(block_hash, 1, 0, False, request_id)
            )
            peer.sub_proto.send_get_block_bodies([block_hash], request_id + 1)
            peer.sub_proto.send_get_receipts(block_hash, request_id + 2)

    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, sigint_received.set)

    async def exit_on_sigint() -> None:
        await sigint_received.wait()
        await peer_pool.cancel()
        loop.stop()

    asyncio.ensure_future(exit_on_sigint())
    asyncio.ensure_future(request_stuff())
    asyncio.ensure_future(peer_pool.run())
    loop.set_debug(True)
    loop.run_forever()
    loop.close()


if __name__ == "__main__":
    _test()
