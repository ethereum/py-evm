import asyncio
import logging
import operator
import struct

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

from evm.p2p import ecies
from evm.p2p.constants import (
    HEADER_LEN,
    MAC_LEN,
)
from evm.p2p.exceptions import (
    AuthenticationError,
    PeerDisconnected,
)
from evm.p2p.utils import (
    roundup_16,
    sxor,
)
from evm.p2p.les import LESProtocol
from evm.p2p.p2p_proto import (
    DisconnectReason,
    P2PProtocol,
)


class Peer:
    logger = logging.getLogger("evm.p2p.peer.Peer")
    _supported_sub_protocols = [LESProtocol]
    # FIXME: Must be configurable.
    listen_port = 30303

    def __init__(self, remote, privkey, reader, writer, aes_secret, mac_secret,
                 egress_mac, ingress_mac):
        self.remote = remote
        self.privkey = privkey
        self.reader = reader
        self.writer = writer
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

        # The Protocol constructor will send the handshake msg, so it must be the last thing we do
        # here.
        self.base_protocol = P2PProtocol(self)

    @property
    def capabilities(self):
        return [(klass.name, klass.version) for klass in self._supported_sub_protocols]

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
            data = yield from self.reader.readexactly(n)
        except asyncio.IncompleteReadError:
            raise PeerDisconnected()
        return data

    @asyncio.coroutine
    def start(self):
        yield from self.read_loop()

    def stop(self):
        self.writer.close()

    @asyncio.coroutine
    def read_loop(self):
        while True:
            try:
                msg = yield from self.read_msg()
            except PeerDisconnected:
                self.logger.debug("Remote disconnected, stopping: {}".format(self.remote))
                self.stop()
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
            self.logger.warn("No protocol found for cmd_id {}".format(cmd_id))
            return
        proto.process(cmd_id, msg)

    def process_p2p_handshake(self, decoded_msg):
        self.match_protocols(decoded_msg['capabilities'])
        if len(self.enabled_sub_protocols) == 0:
            self.disconnect(DisconnectReason.useless_peer)

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
        self.logger.debug("Matching protocols: {}".format(matching_capabilities))


if __name__ == "__main__":
    """
    Run geth like this to be able to do a handshake and get a Peer connected to it.
    ./build/bin/geth -vmodule p2p=4,p2p/discv5=0,eth/*=0 \
      -nodekeyhex 45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8 \
      -port 30301 -nat none -testnet -lightserv 90
    """
    from evm.p2p import kademlia
    from evm.p2p import auth
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    remote_pubkey = keys.PrivateKey(decode_hex(
        "0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8")).public_key
    remote = kademlia.Node(remote_pubkey, kademlia.Address('127.0.0.1', 30301, 30301))

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    peers = []

    @asyncio.coroutine
    def do_handshake():
        peer = yield from auth.handshake(remote, ecies.generate_privkey())
        peers.append(peer)

    count = 1  # Number of peers to start
    try:
        loop.run_until_complete(asyncio.gather(
            *[do_handshake() for _ in range(count)]))
        loop.run_until_complete(asyncio.gather(
            *[peer.start() for peer in peers]))
    except KeyboardInterrupt:
        pass

    for peer in peers:
        peer.stop()
    loop.close()
