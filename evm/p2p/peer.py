import asyncio
import logging
import operator
import struct
import traceback

from cytoolz import reduceby

import rlp
from rlp import sedes

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.constant_time import bytes_eq

from eth_utils import (
    decode_hex,
)

from eth_keys import keys

from evm.constants import GENESIS_BLOCK_NUMBER
from evm.exceptions import CanonicalHeadNotFound
from evm.p2p import auth
from evm.p2p import ecies
from evm.p2p.constants import (
    CONN_IDLE_TIMEOUT,
    HANDSHAKE_TIMEOUT,
    HEADER_LEN,
    MAC_LEN,
    MAX_HEADERS_FETCH,
    REPLY_TIMEOUT,
)
from evm.p2p.exceptions import (
    AuthenticationError,
    PeerDisconnected,
    UnknownProtocolCommand,
    UnreachablePeer,
    UselessPeer,
)
from evm.p2p.utils import (
    gen_request_id,
    roundup_16,
    sxor,
)
from evm.p2p.les import LESProtocol
from evm.p2p.p2p_proto import (
    DisconnectReason,
    P2PProtocol,
)


@asyncio.coroutine
def handshake(remote, privkey, peer_class, chaindb, network_id):
    """Perform the auth and P2P handshakes with the given remote.

    Return an instance of the given peer_class (must be a subclass of BasePeer) connected to that
    remote in case both handshakes are successful and at least one of the sub-protocols supported
    by peer_class is also supported by the remote.

    Raises UnreachablePeer if we cannot connect to the peer or UselessPeer if none of the
    sub-protocols supported by us is also supported by the remote.
    """
    try:
        (aes_secret,
         mac_secret,
         egress_mac,
         ingress_mac,
         reader,
         writer
         ) = yield from auth.handshake(remote, privkey)
    except (ConnectionRefusedError, OSError) as e:
        raise UnreachablePeer(e)
    peer = peer_class(
        remote=remote, privkey=privkey, reader=reader, writer=writer,
        aes_secret=aes_secret, mac_secret=mac_secret, egress_mac=egress_mac,
        ingress_mac=ingress_mac, chaindb=chaindb, network_id=network_id)
    peer.base_protocol.send_handshake()
    msg = yield from peer.read_msg()
    peer.process_msg(msg)
    if len(peer.enabled_sub_protocols) == 0:
        raise UselessPeer("No matching sub-protocols with {}".format(peer))
    for proto in peer.enabled_sub_protocols:
        proto.send_handshake(peer.head_info)
    return peer


class BasePeer:
    logger = logging.getLogger("evm.p2p.peer.Peer")
    # Must be defined in subclasses.
    _supported_sub_protocols = []
    # FIXME: Must be configurable.
    listen_port = 30303

    def __init__(self, remote, privkey, reader, writer, aes_secret, mac_secret,
                 egress_mac, ingress_mac, chaindb, network_id):
        self._finished = asyncio.Event()
        self._pending_replies = {}
        self.remote = remote
        self.privkey = privkey
        self.reader = reader
        self.writer = writer
        self.base_protocol = P2PProtocol(self)
        self.chaindb = chaindb
        self.network_id = network_id
        # The sub protocols that have been enabled for this peer; will be populated when
        # we receive the initial hello msg.
        self.enabled_sub_protocols = []

        self.egress_mac = egress_mac
        self.ingress_mac = ingress_mac
        # FIXME: Yes, the encryption is insecure, see: https://github.com/ethereum/devp2p/issues/32
        iv = b"\x00" * 16
        aes_cipher = Cipher(algorithms.AES(aes_secret), modes.CTR(iv), default_backend())
        self.aes_enc = aes_cipher.encryptor()
        self.aes_dec = aes_cipher.decryptor()
        mac_cipher = Cipher(algorithms.AES(mac_secret), modes.ECB(), default_backend())
        self.mac_enc = mac_cipher.encryptor().update

    @property
    def head_info(self):
        genesis_hash = self.chaindb.lookup_block_hash(GENESIS_BLOCK_NUMBER)
        genesis_header = self.chaindb.get_block_header_by_hash(genesis_hash)
        head = self.chaindb.get_canonical_head()
        return HeadInfo(
            block_number=head.block_number,
            block_hash=head.hash,
            total_difficulty=self.chaindb.get_score(head.hash),
            genesis_hash=genesis_header.hash,
        )

    @property
    def capabilities(self):
        return [(klass.name, klass.version) for klass in self._supported_sub_protocols]

    @asyncio.coroutine
    def wait_for_reply(self, request_id):
        reply = None
        got_reply = asyncio.Event()

        def callback(r):
            nonlocal reply
            reply = r
            got_reply.set()

        self._pending_replies[request_id] = callback
        yield from asyncio.wait_for(got_reply.wait(), REPLY_TIMEOUT)
        return reply

    def get_protocol_for(self, cmd_id):
        """Return the protocol to which the cmd_id belongs.

        Every sub-protocol enabled for a peer defines a cmd ID offset, which is agreed on by both
        sides during the base protocol's handshake. Here we use that to look up the protocol to
        which cmd_id belongs. See the match_protocols() method for the details on how the peers
        agree on which sub protocols to enable and what cmd ID offsets to use for them.
        """
        if cmd_id < self.base_protocol.cmd_length:
            return self.base_protocol
        for proto in self.enabled_sub_protocols:
            if cmd_id >= proto.cmd_id_offset and cmd_id < (proto.cmd_id_offset + proto.cmd_length):
                return proto
        return None

    @asyncio.coroutine
    def read(self, n):
        self.logger.debug("Waiting for {} bytes from {}".format(n, self.remote))
        try:
            data = yield from asyncio.wait_for(self.reader.readexactly(n), CONN_IDLE_TIMEOUT)
        except (asyncio.IncompleteReadError, ConnectionResetError):
            self.logger.debug("EOF reading from {}'s stream".format(self.remote))
            raise PeerDisconnected()
        return data

    @asyncio.coroutine
    def start(self):
        try:
            yield from self.read_loop()
        except Exception as e:
            self.logger.error(
                "Unexpected error when handling remote msg: {}".format(traceback.format_exc()))
        finally:
            self._finished.set()

    @asyncio.coroutine
    def stop(self):
        self.reader.feed_eof()
        self.writer.close()
        yield from self._finished.wait()

    @property
    def is_finished(self):
        return self._finished.is_set()

    @asyncio.coroutine
    def read_loop(self):
        while True:
            try:
                msg = yield from self.read_msg()
            except (PeerDisconnected, asyncio.TimeoutError):
                self.logger.debug("Peer {} stopped responding, disconnecting".format(self.remote))
                return
            self.process_msg(msg)

    @asyncio.coroutine
    def read_msg(self):
        header_data = yield from self.read(HEADER_LEN + MAC_LEN)
        header = self.decrypt_header(header_data)
        frame_size = self.get_frame_size(header)
        # The frame_size specified in the header does not include the padding to 16-byte boundary,
        # so need to do this here to ensure we read all the frame's data.
        read_size = roundup_16(frame_size)
        frame_data = yield from self.read(read_size + MAC_LEN)
        return self.decrypt_body(frame_data, frame_size)

    def process_msg(self, msg):
        cmd_id = rlp.decode(msg[:1], sedes=sedes.big_endian_int)
        self.logger.debug("Got msg with cmd_id: {}".format(cmd_id))
        proto = self.get_protocol_for(cmd_id)
        if proto is None:
            raise UnknownProtocolCommand(
                "No protocol found for cmd_id {}".format(cmd_id))
        decoded = proto.process(cmd_id, msg)
        if decoded is None:
            return
        request_id = decoded.get('request_id')
        if request_id is not None and request_id in self._pending_replies:
            callback = self._pending_replies.pop(request_id)
            callback(decoded)

    def process_p2p_handshake(self, decoded_msg):
        self.match_protocols(decoded_msg['capabilities'])
        if len(self.enabled_sub_protocols) == 0:
            self.disconnect(DisconnectReason.useless_peer)
            self.logger.debug(
                "No matching protocols with {}, disconnecting".format(self.remote))
        else:
            self.logger.debug(
                "Finished P2P handshake with {}; matching protocols: {}".format(
                    self.remote,
                    [(p.name, p.version) for p in self.enabled_sub_protocols]))

    def encrypt(self, header, frame):
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

    def decrypt_header(self, data):
        if len(data) != HEADER_LEN + MAC_LEN:
            raise ValueError("Unexpected header length: {}".format(len(data)))

        header_ciphertext = data[:HEADER_LEN]
        header_mac = data[HEADER_LEN:]
        mac_secret = self.ingress_mac.digest()[:HEADER_LEN]
        aes = self.mac_enc(mac_secret)[:HEADER_LEN]
        self.ingress_mac.update(sxor(aes, header_ciphertext))
        expected_header_mac = self.ingress_mac.digest()[:HEADER_LEN]
        if not bytes_eq(expected_header_mac, header_mac):
            raise AuthenticationError('Invalid header mac')
        return self.aes_dec.update(header_ciphertext)

    def decrypt_body(self, data, body_size):
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
            raise AuthenticationError('Invalid frame mac')
        return self.aes_dec.update(frame_ciphertext)[:body_size]

    def get_frame_size(self, header):
        # The frame size is encoded in the header as a 3-byte int, so before we unpack we need
        # to prefix it with an extra byte.
        encoded_size = b'\x00' + header[:3]
        (size,) = struct.unpack(b'>I', encoded_size)
        return size

    def send(self, header, body):
        cmd_id = rlp.decode(body[:1], sedes=sedes.big_endian_int)
        self.logger.debug("Sending msg with cmd_id: {}".format(cmd_id))
        self.writer.write(self.encrypt(header, body))

    def disconnect(self, reason):
        """Send a disconnect msg to the remote node and stop this Peer.

        :param reason: An item from the DisconnectReason enum.
        """
        if not isinstance(reason, DisconnectReason):
            raise ValueError(
                "Reason must be an item of DisconnectReason, got {}".format(reason))
            self.logger.debug("Disconnecting from remote peer; reason: {}".format(reason.value))
        self.base_protocol.send_disconnect(reason.value)
        self.stop()

    def match_protocols(self, remote_capabilities):
        """Match the sub-protocols supported by this Peer with the given remote capabilities.

        Every sub-protocol and remote-capability are defined by a protocol name and version. This
        method will get the match with the highest version for every protocol, sort them
        in ascending alphabetical order and add a Protocol instance for the protocol with that
        name/version to this peer's list of enabled sub protocols. Each Protocol instance will
        also have a cmd ID offset, defined as the offset of the previous item (0 for the base
        protocol) plus the protocol's cmd length (i.e. number of commands).
        """
        matching_capabilities = set(self.capabilities).intersection(remote_capabilities)
        higher_matching = reduceby(
            key=operator.itemgetter(0),
            binop=lambda a, b: a if a[1] > b[1] else b,
            seq=matching_capabilities)
        sub_protocols_by_name_and_version = dict(
            ((klass.name, klass.version), klass) for klass in self._supported_sub_protocols)
        offset = self.base_protocol.cmd_length
        for name, version in sorted(higher_matching.values()):
            proto_klass = sub_protocols_by_name_and_version[(name, version)]
            self.enabled_sub_protocols.append(proto_klass(self, offset))
            offset += proto_klass.cmd_length


class LESPeer(BasePeer):
    _les_proto = None
    _supported_sub_protocols = [LESProtocol]

    def __init__(self, remote, privkey, reader, writer, aes_secret, mac_secret,
                 egress_mac, ingress_mac, chaindb, network_id):
        super(LESPeer, self).__init__(
            remote, privkey, reader, writer, aes_secret, mac_secret,
            egress_mac, ingress_mac, chaindb, network_id)
        self._header_fetching_lock = asyncio.Lock()

    @asyncio.coroutine
    def fetch_headers(self, block_number, reorg_depth=0):
        """Fetch all headers from our canonical chain head up to block_number.

        If reorg_depth is provided, fetch headers from (current_head - reorg_depth) up to
        block_number.
        """
        with (yield from self._header_fetching_lock):
            self.logger.info("fetch_headers({}, reorg_depth={}) called".format(
                block_number, reorg_depth))
            head_number = self.chaindb.get_canonical_head().block_number
            head_number -= reorg_depth
            announced_head_number = block_number
            while announced_head_number > head_number:
                request_id = gen_request_id()
                target_head = min(head_number + MAX_HEADERS_FETCH, announced_head_number)
                self.les_proto.send_get_block_headers(
                    target_head, MAX_HEADERS_FETCH, request_id, reverse=True)
                reply = yield from self.wait_for_reply(request_id)
                for header in reversed(reply['headers']):
                    self.chaindb.persist_header_to_db(header)
                    # FIXME: The reference to the canonical chain head should not be stored in the
                    # chaindb as that is shared by all peers -- instead, that should be kept on a
                    # peer-specific db.
                    self.chaindb.add_block_number_to_hash_lookup(header)
                    self.chaindb.set_canonical_head(header.hash)
                    head_number = header.block_number
                self.logger.info("synced headers up to block {}".format(head_number))

    @property
    def les_proto(self):
        """Return the LESProtocol available for this peer.

        The available LESProtocol will be the highest version supported by this class and the
        remote peer. It is available only after the initial P2P handshake.
        """
        # Here we assume this class supports one version of the LESProtocol that is also
        # supported by the remote peer, which should be ok since LES is the only sub-protocol
        # supported by this class and the handshake will ensure we have a matching sub-protocol
        # with the remote peer.
        assert len(self.enabled_sub_protocols) > 0
        if self._les_proto is None:
            for proto in self.enabled_sub_protocols:
                if proto.name == LESProtocol.name:
                    self._les_proto = proto
            if self._les_proto is None:
                raise Exception(
                    "We assumed LESProtocol was supported, but it isn't. See comment above")
        return self._les_proto


class HeadInfo:
    def __init__(self, block_number, block_hash, total_difficulty, genesis_hash):
        self.block_number = block_number
        self.block_hash = block_hash
        self.total_difficulty = total_difficulty
        self.genesis_hash = genesis_hash


if __name__ == "__main__":
    """
    Run geth like this to be able to do a handshake and get a Peer connected to it.
    ./build/bin/geth -vmodule p2p=4,p2p/discv5=0,eth/*=0 \
      -nodekeyhex 45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8 \
      -port 30301 -nat none -testnet -lightserv 90
    """
    import argparse
    from evm.chains.ropsten import (
        RopstenChain,
        ROPSTEN_GENESIS_HEADER,
    )
    from evm.db.backends.memory import MemoryDB
    from evm.db.backends.level import LevelDB
    from evm.db.chain import BaseChainDB
    from evm.p2p import kademlia
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    remote_pubkey = keys.PrivateKey(decode_hex(
        "0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8")).public_key
    remote = kademlia.Node(remote_pubkey, kademlia.Address('127.0.0.1', 30301, 30301))

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str)
    args = parser.parse_args()

    genesis_header = ROPSTEN_GENESIS_HEADER
    if args.db is not None:
        chaindb = BaseChainDB(LevelDB(args.db))
    else:
        chaindb = BaseChainDB(MemoryDB())
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # We're starting with a fresh DB.
        chain = RopstenChain.from_genesis_header(chaindb, genesis_header)
    else:
        # We're reusing an existing db.
        chain = RopstenChain(chaindb)
    print("Current chain head: {}".format(chaindb.get_canonical_head().block_number))

    loop = asyncio.get_event_loop()
    try:
        peer = loop.run_until_complete(
            asyncio.wait_for(
                handshake(remote, ecies.generate_privkey(), LESPeer, chaindb, chain.network_id),
                HANDSHAKE_TIMEOUT))
        loop.run_until_complete(peer.start())
    except KeyboardInterrupt:
        pass

    loop.run_until_complete(peer.stop())
    loop.close()
