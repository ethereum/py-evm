import grpc

from p2p.libp2p_bridge.config import (
    RPC_CLIENT_IP,
    RPC_CLIENT_PORT,
)
from p2p.libp2p_bridge.constants import (
    COLLATION_TOPIC_FORMAT,
)
from p2p.libp2p_bridge.grpc_client import (
    GRPCClient,
)
from p2p.libp2p_bridge.message import (
    Collation,
    CollationRequest,
    MsgType,
)

import p2p.libp2p_bridge.pb.rpc.rpc_pb2_grpc as rpc_pb2_grpc


def make_collation_topic(shard_id):
    return COLLATION_TOPIC_FORMAT.format(shard_id)


class P2PClient:
    rpc_client = None

    def __init__(self, rpc_client):
        self.rpc_client = rpc_client

    def broadcast_collation(self, collation):
        topic = make_collation_topic(collation.shard_id)
        collation_bytes = collation.to_bytes()
        self.rpc_client.broadcast(topic, MsgType.Collation, collation_bytes)
        return True

    def request_collation(self, peer_id, shard_id, period, collation_hash):
        req = CollationRequest(shard_id, period, collation_hash)
        req_bytes = req.to_bytes()
        res_bytes = self.rpc_client.send(peer_id, MsgType.CollationRequest, req_bytes)
        return Collation.from_bytes(res_bytes)


def make_grpc_stub():
    dial_addr = "{}:{}".format(RPC_CLIENT_IP, RPC_CLIENT_PORT)
    channel = grpc.insecure_channel(dial_addr)
    return rpc_pb2_grpc.PocStub(channel)


def test_grpc_client():
    """
    This test is to test whether grpc client works well when
        - our go node is started
        - peer's go node is started
        - peer's python grpc server is started
    To run this test, please ensure
        - we have started a grpc_server, by running `python grpc_server.py`
        - we have started two `sharding-p2p-poc` nodes, one with seed=0, rpcport=13000, and another
            with seed=1, rpcport=13001
    Scenario `broadcast`:
        When we call `grpc_client.broadcast`, it first calls our go node's `pubsub.publish`.
        Our go node will broadcast the data and return `is_successful`. After the data is relayed
        to peer's go node, the node will call its python's `grpc_server.receive`, and therefore
        peer's python side receive the data, and then returns `is_valid` to peer's go node.
    Scenario `request`:
        When we call `grpc_client.request`, it first calls our go node's `shardmanager.reuqest`.
        Our go node will ask peer's go node for the data. Peer's go node will call its
        python's `grpc_server.receive`, and therefore peer's python side receive the request,
        parse and handle the request, and then returns the corresponding data.
    """
    stub = make_grpc_stub()
    rpc_client = GRPCClient(stub)
    rpc_client.subscribe_shards([0, 1])
    rpc_client.unsubscribe_shards([0])
    assert 1 in rpc_client.get_subscribed_shards()
    # print(rpc_client.get_subscribed_shards())
    # RPC should fail when subscribing an invalid shard
    # print(rpc_client.subscribe_shards([40, 56]))
    # print(rpc_client.get_subscribed_shards())
    # print(rpc_client.unsubscribe_shards([40]))
    # print(rpc_client.get_subscribed_shards())
    # print(rpc_client.broadcast_collation(56, 10, 5566, 100))
    # print(rpc_client.send_collation(56, 1, b'123'))

    # peer_id_0 = "QmS5QmciTXXnCUCyxud5eWFenUMAmvAWSDa1c7dvdXRMZ7"
    peer_id_1 = "QmexAnfpHrhMmAC5UNQVS8iBuUUgDrMbMY17Cck2gKrqeX"

    p2p_client = P2PClient(rpc_client)
    c1 = Collation(1, 2, b"\xbe\xef")
    assert p2p_client.broadcast_collation(c1)
    c2 = p2p_client.request_collation(peer_id_1, 1, 2, "")
    assert c2.shard_id == 1
    assert c2.period == 2
