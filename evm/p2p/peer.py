import asyncio
import logging

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from eth_utils import (
    decode_hex,
)

from eth_keys import keys


class Peer(asyncio.Protocol):
    logger = logging.getLogger("evm.p2p.peer.Peer")

    def __init__(self, remote, privkey, reader, writer, aes_secret, mac_secret,
                 egress_mac, ingress_mac):
        self.remote = remote
        self.privkey = privkey
        self.reader = reader
        self.writer = writer

        self.egress_mac = egress_mac
        self.ingress_mac = ingress_mac
        # Yes, the encryption is insecure, see: https://github.com/ethereum/devp2p/issues/32
        iv = b"\x00" * 16
        aes_cipher = Cipher(algorithms.AES(aes_secret), modes.CTR(iv), default_backend())
        self.aes_enc = aes_cipher.encryptor()
        self.aes_dec = aes_cipher.decryptor()
        mac_cipher = Cipher(algorithms.AES(mac_secret), modes.ECB(), default_backend())
        self.mac_enc = mac_cipher.encryptor().update


if __name__ == "__main__":
    # Run geth like this to be able to do a handshake and get a Peer connected to it.
    # ./build/bin/geth -verbosity 9 \
    #   --nodekeyhex 45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8 \
    #   --port 30301 --nat none --testnet --nodiscover --light

    from evm.p2p import kademlia
    from evm.p2p import auth
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    privkey = keys.PrivateKey(
        decode_hex('65462b0520ef7d3df61b9992ed3bea0c56ead753be7c8b3614e0ce01e4cac41b'))
    remote_pubkey = keys.PrivateKey(decode_hex(
        "0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8")).public_key
    remote = kademlia.Node(remote_pubkey, kademlia.Address('127.0.0.1', 30301, 30301))

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    peer = None

    @asyncio.coroutine
    def do_handshake():
        global peer
        peer = yield from auth.handshake(remote, privkey)

    loop.run_until_complete(do_handshake())
