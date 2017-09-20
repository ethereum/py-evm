import asyncio
import logging
import struct

import rlp
from rlp import sedes

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

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
    sxor,
)
from evm.p2p.les import LESProtocol
from evm.p2p.protocol import roundup_16
from evm.p2p.p2p_proto import (
    Hello,
    P2PProtocol,
)


class Peer:
    logger = logging.getLogger("evm.p2p.peer.Peer")
    _sub_protocols = [LESProtocol]
    # FIXME: Must be configurable.
    listen_port = 30303

    # We use keyword arguments here because there are too many arguments and it's very easy
    # for callers to get them wrong.
    def __init__(self, remote=None, privkey=None, reader=None, writer=None, aes_secret=None,
                 mac_secret=None, egress_mac=None, ingress_mac=None):
        self.remote = remote
        self.privkey = privkey
        self.reader = reader
        self.writer = writer
        self.base_protocol = P2PProtocol(self)

        self.egress_mac = egress_mac
        self.ingress_mac = ingress_mac
        # Yes, the encryption is insecure, see: https://github.com/ethereum/devp2p/issues/32
        iv = b"\x00" * 16
        aes_cipher = Cipher(algorithms.AES(aes_secret), modes.CTR(iv), default_backend())
        self.aes_enc = aes_cipher.encryptor()
        self.aes_dec = aes_cipher.decryptor()
        mac_cipher = Cipher(algorithms.AES(mac_secret), modes.ECB(), default_backend())
        self.mac_enc = mac_cipher.encryptor().update

    @property
    def capabilities(self):
        return [(klass.name, klass.version) for klass in self._sub_protocols]

    def get_protocol_for(self, cmd_id):
        if cmd_id >= self.base_protocol.cmd_length:
            # TODO: Return the appropriate sub-protocol
            return None
        return self.base_protocol

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
        self.logger.debug("Processing msg with cmd_id: {}".format(cmd_id))
        proto = self.get_protocol_for(cmd_id)
        if proto is None:
            self.logger.warn("No protocol found for cmd_id {}".format(cmd_id))
            return
        decoded_msg = proto.process(cmd_id, msg)
        if cmd_id == Hello.id:
            # TODO: Populate self.sub_protocols based on self.capabilities and
            # hello['capabilities']
            self.logger.debug("Got hello: {}".format(decoded_msg))

    def encrypt(self, header, frame):
        if len(header) != HEADER_LEN:
            raise ValueError("Unexpected header length: {}".format(len(header)))

        header_ciphertext = self.aes_enc.update(header)
        mac_secret = self.egress_mac.digest()[:HEADER_LEN]
        # egress-mac.update(aes(mac-secret,egress-mac) ^ header-ciphertext).digest
        self.egress_mac.update(sxor(self.mac_enc(mac_secret), header_ciphertext))
        header_mac = self.egress_mac.digest()[:HEADER_LEN]

        frame_ciphertext = self.aes_enc.update(frame)
        # egress-mac.update(aes(mac-secret,egress-mac) ^
        # left128(egress-mac.update(frame-ciphertext).digest))
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
        if expected_header_mac != header_mac:
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
        if frame_mac != expected_frame_mac:
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

    def send_hello(self):
        header, body = self.base_protocol.get_hello_message()
        self.send(header, body)


if __name__ == "__main__":
    # Run geth like this to be able to do a handshake and get a Peer connected to it.
    # ./build/bin/geth -verbosity 9 \
    #   --nodekeyhex 45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8 \
    #   --port 30301 --nat none --testnet --nodiscover --light

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
