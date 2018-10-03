import grpc

import pytest

from p2p.libp2p_bridge.grpc_server import (
    GRPCServer,
)
from p2p.libp2p_bridge.message import (
    Collation,
    CollationRequest,
    MsgType,
)

import p2p.libp2p_bridge.pb.event.event_pb2 as event_pb2
import p2p.libp2p_bridge.pb.event.event_pb2_grpc as event_pb2_grpc


TEST_RPC_SERVER_ADDR = "127.0.0.1:55666"


@pytest.fixture("module")
def grpc_server():
    s = GRPCServer()
    s.start(TEST_RPC_SERVER_ADDR)
    yield s
    s.stop()


def make_stub():
    channel = grpc.insecure_channel(TEST_RPC_SERVER_ADDR)
    return event_pb2_grpc.EventStub(channel)


def test_grpc_server_receive_collation(grpc_server):
    collation = Collation(1, 2, b"")
    req = event_pb2.ReceiveRequest(
        peerID="",
        msgType=MsgType.Collation.value,
        data=collation.to_bytes(),
    )
    stub = make_stub()
    resp = stub.Receive(req)
    result_bytes = resp.data
    assert len(result_bytes) == 1 and bool(result_bytes)


def test_grpc_server_receive_collation_request(grpc_server):
    cr = CollationRequest(1, 2, "")
    req = event_pb2.ReceiveRequest(
        peerID="",
        msgType=MsgType.CollationRequest.value,
        data=cr.to_bytes(),
    )
    stub = make_stub()
    resp = stub.Receive(req)
    collation_bytes = resp.data
    collation = Collation.from_bytes(collation_bytes)
    assert collation.shard_id == 1
    assert collation.period == 2
