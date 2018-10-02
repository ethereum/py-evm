import asyncio

import grpc

import pytest

from cancel_token import (
    CancelToken,
)

from p2p.libp2p_bridge.config import (
    RPC_SERVER_LISTEN_IP,
    RPC_SERVER_PORT,
)
from p2p.libp2p_bridge.grpc_server import (
    GRPCServer,
)
from p2p.libp2p_bridge.message import (
    Collation,
    CollationRequest,
    MsgType,
)

import p2p.libp2p_bridge.github.com.ethresearch.sharding_p2p_poc.pb.event.event_pb2 as event_pb2
import p2p.libp2p_bridge.github.com.ethresearch.sharding_p2p_poc.pb.event.event_pb2_grpc as event_pb2_grpc


def make_stub():
    addr = '{}:{}'.format(RPC_SERVER_LISTEN_IP, RPC_SERVER_PORT)
    channel = grpc.insecure_channel(addr)
    return event_pb2_grpc.EventStub(channel)


@pytest.mark.asyncio
async def test_grpc_server_receive_collation(event_loop):
    token = CancelToken("grpc_server")
    grpc_server = GRPCServer(token=token)
    asyncio.ensure_future(grpc_server.run())
    await asyncio.sleep(0.1)
    assert token.loop == grpc_server._loop
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
    await grpc_server.cancel()


@pytest.mark.asyncio
async def test_grpc_server_receive_collation_request(event_loop):
    token = CancelToken("grpc_server", loop=event_loop)
    grpc_server = GRPCServer(token=token, loop=event_loop)
    asyncio.ensure_future(grpc_server.run())
    await asyncio.sleep(0.1)
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
    await grpc_server.cancel()
