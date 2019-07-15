from eth_keys import datatypes

from multiaddr import Multiaddr

import multihash

from libp2p.peer.id import (
    ID,
)

from .configs import (
    RPC_PROTOCOL_PREFIX,
)


def peer_id_from_pubkey(pubkey: datatypes.PublicKey) -> ID:
    algo = multihash.Func.sha2_256
    mh_digest = multihash.digest(pubkey.to_bytes(), algo)
    return ID(mh_digest.encode())


def make_tcp_ip_maddr(ip: str, port: int) -> Multiaddr:
    return Multiaddr(f"/ip4/{ip}/tcp/{port}")


def make_rpc_protocol_id(message_name: str, schema_version: str, encoding: str) -> str:
    return f"{RPC_PROTOCOL_PREFIX}/{message_name}/{schema_version}/{encoding}"
