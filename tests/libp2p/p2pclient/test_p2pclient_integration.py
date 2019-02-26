import asyncio
import os
import subprocess
import time
from typing import (
    NamedTuple,
)

import pytest

from multiaddr import (
    Multiaddr,
    protocols,
)

import multihash

from libp2p.p2pclient.datastructures import (
    PeerID,
)
from libp2p.p2pclient.exceptions import (
    ControlFailure,
)
from libp2p.p2pclient.p2pclient import (
    Client,
)
from libp2p.p2pclient.serialization import (
    read_pbmsg_safe,
)

import libp2p.p2pclient.pb.p2pd_pb2 as p2pd_pb


NUM_P2PDS = 4


@pytest.fixture(scope="module")
def peer_id_random():
    return PeerID.from_base58("QmcgpsyWgH8Y8ajJz1Cu72KnS5uo2Aa2LpzU7kinSupNK1")


@pytest.fixture
def enable_connmgr():
    return False


class Daemon:
    control_maddr = None
    proc_daemon = None
    log_filename = ""
    f_log = None
    closed = None

    def __init__(self, control_maddr, enable_connmgr):
        self.control_maddr = control_maddr
        self.enable_connmgr = enable_connmgr
        self.is_closed = False
        self._start_logging()
        self._run()

    def _start_logging(self):
        name_control_maddr = str(self.control_maddr).replace('/', '_').replace('.', '_')
        self.log_filename = f'/tmp/log_p2pd{name_control_maddr}.txt'
        self.f_log = open(self.log_filename, 'wb')

    def _run(self):
        cmd_list = [
            "p2pd",
            f"-listen={str(self.control_maddr)}",
            "-dht=true",
            "-pubsub=true",
            "-pubsubRouter=gossipsub",
        ]
        if self.enable_connmgr:
            cmd_list += [
                "-connManager=true",
                "-connLo=1",
                "-connHi=2",
                "-connGrace=0",
            ]
        self.proc_daemon = subprocess.Popen(
            cmd_list,
            stdout=self.f_log,
            stderr=self.f_log,
            bufsize=0,
        )

    async def wait_until_ready(self):
        timeout = 10  # seconds
        lines_head_pattern = (
            b'Control socket:',
            b'Peer ID:',
            b'Peer Addrs:',
        )
        lines_head_occurred = {
            line: False
            for line in lines_head_pattern
        }
        t_start = time.time()
        with open(self.log_filename, 'rb') as f_log_read:
            while True:
                is_finished = all([value for _, value in lines_head_occurred.items()])
                if is_finished:
                    break
                if time.time() - t_start > timeout:
                    raise Exception("daemon is not ready before timeout")
                line = f_log_read.readline()
                for head_pattern in lines_head_occurred:
                    if line.startswith(head_pattern):
                        lines_head_occurred[head_pattern] = True
                await asyncio.sleep(0.1)
        # sleep for a while in case that the daemon haven't been ready after emitting these lines
        await asyncio.sleep(0.1)

    def close(self):
        if self.is_closed:
            return
        self.proc_daemon.terminate()
        self.proc_daemon.wait()
        self.f_log.close()
        self.is_closed = True


class DaemonPair(NamedTuple):
    daemon: Daemon
    client: Client


class ConnectionFailure(Exception):
    pass


async def make_p2pd_pair_unix(serial_no, enable_connmgr):
    control_maddr = Multiaddr(f"/unix/tmp/test_p2pd_control_{serial_no}.sock")
    listen_maddr = Multiaddr(f"/unix/tmp/test_p2pd_listen_{serial_no}.sock")
    # remove the existing unix socket files if they are existing
    try:
        os.unlink(control_maddr.value_for_protocol(protocols.P_UNIX))
    except FileNotFoundError:
        pass
    try:
        os.unlink(listen_maddr.value_for_protocol(protocols.P_UNIX))
    except FileNotFoundError:
        pass
    return await _make_p2pd_pair(control_maddr, listen_maddr, enable_connmgr)


async def make_p2pd_pair_ip4(serial_no, enable_connmgr):
    base_port = 35566
    num_ports = 2
    control_maddr = Multiaddr(f"/ip4/127.0.0.1/tcp/{base_port+(serial_no*num_ports)}")
    listen_maddr = Multiaddr(f"/ip4/127.0.0.1/tcp/{base_port+(serial_no*num_ports)+1}")
    return await _make_p2pd_pair(control_maddr, listen_maddr, enable_connmgr)


async def _make_p2pd_pair(control_maddr, listen_maddr, enable_connmgr):
    p2pd = Daemon(control_maddr, enable_connmgr)
    # wait for daemon ready
    await p2pd.wait_until_ready()
    # TODO: probably remove the sleep and make sure the daemon is correctly spun up
    p2pc = Client(control_maddr, listen_maddr)
    await p2pc.listen()
    return DaemonPair(p2pd, p2pc)


@pytest.fixture(params=[make_p2pd_pair_ip4, make_p2pd_pair_unix])
async def p2pds(request, enable_connmgr):
    make_p2pd_pair = request.param
    pairs = (
        asyncio.ensure_future(make_p2pd_pair(i, enable_connmgr))
        for i in range(NUM_P2PDS)
    )
    p2pd_pairs = await asyncio.gather(*pairs)
    yield p2pd_pairs

    # clean up
    for p2pd_pair in p2pd_pairs:
        if not p2pd_pair.daemon.is_closed:
            p2pd_pair.daemon.close()
        if p2pd_pair.client.listener is not None:
            await p2pd_pair.client.close()


@pytest.mark.asyncio
async def test_client_listen(p2pds):
    c0 = p2pds[0].client
    # test case: ensure the server is listening
    assert c0.listener is not None
    assert c0.listener.sockets is not None
    assert len(c0.listener.sockets) != 0
    # test case: listen twice
    with pytest.raises(ControlFailure):
        await c0.listen()


@pytest.mark.asyncio
async def test_client_close(p2pds):
    c0 = p2pds[0].client
    # reference to the listener before `Client.close`, since it will set listener to `None`
    listener = c0.listener
    assert c0.listener is not None
    await c0.close()
    assert c0.listener is None
    # test case: ensure there is no sockets after closing
    # for versions before python 3.7 and 3.7+, respectively
    assert listener.sockets is None or len(listener.sockets) == 0
    # test case: it's fine to listen again, after closing
    await c0.listen()


@pytest.mark.asyncio
async def test_client_identify(p2pds):
    await p2pds[0].client.identify()


@pytest.mark.asyncio
async def test_client_connect_success(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    peer_id_0, maddrs_0 = await c0.identify()
    peer_id_1, maddrs_1 = await c1.identify()
    await c0.connect(peer_id_1, maddrs_1)
    # test case: repeated connections
    await c1.connect(peer_id_0, maddrs_0)


@pytest.mark.asyncio
async def test_client_connect_failure(peer_id_random, p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    peer_id_1, maddrs_1 = await c1.identify()
    await c0.identify()
    # test case: `peer_id` mismatches
    with pytest.raises(ControlFailure):
        await c0.connect(peer_id_random, maddrs_1)
    # test case: empty maddrs
    with pytest.raises(ControlFailure):
        await c0.connect(peer_id_1, [])
    # test case: wrong maddrs
    with pytest.raises(ControlFailure):
        await c0.connect(peer_id_1, [Multiaddr("/ip4/127.0.0.1/udp/0")])


async def _connect_and_check(client_0, client_1):
    peer_id_0, _ = await client_0.identify()
    peer_id_1, maddrs_1 = await client_1.identify()
    await client_0.connect(peer_id_1, maddrs_1)
    peers_0 = [pinfo.peer_id for pinfo in await client_0.list_peers()]
    peers_1 = [pinfo.peer_id for pinfo in await client_1.list_peers()]
    if peer_id_0 not in peers_1:
        raise ConnectionFailure(
            f"failed to connect: peer_id_0={peer_id_0} not in peers_1={peers_1}"
        )
    if peer_id_1 not in peers_0:
        raise ConnectionFailure(
            f"failed to connect: peer_id_1={peer_id_1} not in peers_0={peers_0}"
        )


async def connect_safe(client_0, client_1):
    timeout = 30  # seconds
    t_start = time.time()
    while True:
        try:
            await _connect_and_check(client_0, client_1)
            # if the connection succeeds, jump out of this while loop immediately
            break
        except ConnectionFailure as e:
            reason = str(e)
        if (time.time() - t_start) > timeout:
            # timeout
            assert False, f"failed to connect peers: {reason}"
        await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_connect_safe(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    await connect_safe(c0, c1)


@pytest.mark.asyncio
async def test_client_list_peers(p2pds):
    c0, c1, c2 = p2pds[0].client, p2pds[1].client, p2pds[2].client
    # test case: no peers
    assert len(await c0.list_peers()) == 0
    # test case: 1 peer
    await connect_safe(c0, c1)
    assert len(await c0.list_peers()) == 1
    assert len(await c1.list_peers()) == 1
    # test case: one more peer
    await connect_safe(c0, c2)
    assert len(await c0.list_peers()) == 2
    assert len(await c1.list_peers()) == 1
    assert len(await c2.list_peers()) == 1


@pytest.mark.asyncio
async def test_client_disconnect(peer_id_random, p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    # test case: disconnect a peer without connections
    await c1.disconnect(peer_id_random)
    # test case: disconnect
    peer_id_0, _ = await c0.identify()
    await connect_safe(c0, c1)
    assert len(await c0.list_peers()) == 1
    assert len(await c1.list_peers()) == 1
    await c1.disconnect(peer_id_0)
    assert len(await c0.list_peers()) == 0
    assert len(await c1.list_peers()) == 0
    # test case: disconnect twice
    await c1.disconnect(peer_id_0)
    assert len(await c0.list_peers()) == 0
    assert len(await c1.list_peers()) == 0


@pytest.mark.asyncio
async def test_client_stream_open_success(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client

    peer_id_1, maddrs_1 = await c1.identify()
    await connect_safe(c0, c1)

    proto = "123"

    async def handle_proto(stream_info, reader, writer):
        assert reader.at_eof()

    await c1.stream_handler(proto, handle_proto)

    # test case: normal
    stream_info, _, writer = await c0.stream_open(
        peer_id_1,
        (proto,),
    )
    assert stream_info.peer_id == peer_id_1
    assert stream_info.addr in maddrs_1
    assert stream_info.proto == "123"
    writer.close()
    await asyncio.sleep(0.1)  # yield

    # test case: open with multiple protocols
    stream_info, _, writer = await c0.stream_open(
        peer_id_1,
        (proto, "another_protocol"),
    )
    assert stream_info.peer_id == peer_id_1
    assert stream_info.addr in maddrs_1
    assert stream_info.proto == "123"
    writer.close()
    await asyncio.sleep(0.1)  # yield


@pytest.mark.asyncio
async def test_client_stream_open_failure(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client

    peer_id_1, _ = await c1.identify()
    await connect_safe(c0, c1)

    proto = "123"

    # test case: `stream_open` to a peer who didn't register the protocol
    with pytest.raises(ControlFailure):
        await c0.stream_open(
            peer_id_1,
            (proto,),
        )

    # test case: `stream_open` to a peer for a non-registered protocol
    async def handle_proto(stream_info, reader, writer):
        pass

    await c1.stream_handler(proto, handle_proto)
    with pytest.raises(ControlFailure):
        await c0.stream_open(
            peer_id_1,
            ("another_protocol",),
        )


def _get_current_running_dispatched_handler():
    running_handlers = tuple(
        task
        for task in asyncio.Task.all_tasks()
        if (task._coro.__name__ == "_dispatcher") and (not task.done())
    )
    # assume there should only be exactly one dispatched handler
    assert len(running_handlers) == 1
    return running_handlers[0]


@pytest.mark.asyncio
async def test_client_stream_handler_success(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client

    peer_id_1, _ = await c1.identify()
    await connect_safe(c0, c1)

    proto = "protocol123"
    bytes_to_send = b"yoyoyoyoyog"
    # event for this test function to wait until the handler function receiving the incoming data
    event_proto = asyncio.Event()

    async def handle_proto(stream_info, reader, writer):
        event_proto.set()
        bytes_received = await reader.read(len(bytes_to_send))
        assert bytes_received == bytes_to_send

    await c1.stream_handler(proto, handle_proto)
    assert proto in c1.handlers
    assert handle_proto == c1.handlers[proto]

    # test case: test the stream handler `handle_proto`
    _, _, writer = await c0.stream_open(
        peer_id_1,
        (proto,),
    )
    # wait until the handler function starts blocking waiting for the data
    await event_proto.wait()
    # because we haven't sent the data, we know the handler function must still blocking waiting.
    # get the task of the protocol handler
    task_proto_handler = _get_current_running_dispatched_handler()
    writer.write(bytes_to_send)
    await writer.drain()

    # wait for the handler to finish
    await task_proto_handler
    assert task_proto_handler.done()
    # check if `AssertionError` is thrown
    assert task_proto_handler.exception() is None

    writer.close()

    # test case: two streams to different handlers respectively
    another_proto = "another_protocol123"
    another_bytes_to_send = b"456"
    event_another_proto = asyncio.Event()

    async def handle_another_proto(stream_info, reader, writer):
        event_another_proto.set()
        bytes_received = await reader.read(len(another_bytes_to_send))
        assert bytes_received == another_bytes_to_send

    await c1.stream_handler(another_proto, handle_another_proto)
    assert another_proto in c1.handlers
    assert handle_another_proto == c1.handlers[another_proto]

    _, _, another_writer = await c0.stream_open(
        peer_id_1,
        (another_proto,),
    )
    await event_another_proto.wait()

    # we know at this moment the handler must still blocking wait
    task_another_protocol_handler = _get_current_running_dispatched_handler()

    another_writer.write(another_bytes_to_send)
    await another_writer.drain()

    await task_another_protocol_handler
    assert task_another_protocol_handler.done()
    assert task_another_protocol_handler.exception() is None

    another_writer.close()

    # test case: registering twice can override the previous registration
    event_third = asyncio.Event()

    async def handler_third(stream_info, reader, writer):
        event_third.set()

    await c1.stream_handler(another_proto, handler_third)
    assert another_proto in c1.handlers
    # ensure the handler is override
    assert handler_third == c1.handlers[another_proto]

    await c0.stream_open(
        peer_id_1,
        (another_proto,),
    )
    # ensure the overriding handler is called when the protocol is opened a stream
    await event_third.wait()


@pytest.mark.asyncio
async def test_client_stream_handler_failure(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client

    peer_id_1, _ = await c1.identify()
    await connect_safe(c0, c1)

    proto = "123"

    # test case: registered a wrong protocol name
    async def handle_proto_correct_params(stream_info, reader, writer):
        pass

    await c1.stream_handler("another_protocol", handle_proto_correct_params)
    with pytest.raises(ControlFailure):
        await c0.stream_open(peer_id_1, (proto,))

    # test case: registered a handler with the wrong signature(parameters)
    async def handle_proto_wrong_params(stream_info, reader):
        pass

    with pytest.raises(ControlFailure):
        await c1.stream_handler(proto, handle_proto_wrong_params)


@pytest.mark.asyncio
async def test_client_find_peer_success(p2pds):
    c0, c1, c2 = p2pds[0].client, p2pds[1].client, p2pds[2].client
    peer_id_2, _ = await c2.identify()
    await connect_safe(c0, c1)
    await connect_safe(c1, c2)
    pinfo = await c0.find_peer(peer_id_2)
    assert pinfo.peer_id == peer_id_2
    assert len(pinfo.addrs) != 0


@pytest.mark.asyncio
async def test_client_find_peer_failure(peer_id_random, p2pds):
    c0, c1, c2 = p2pds[0].client, p2pds[1].client, p2pds[2].client
    peer_id_2, _ = await c2.identify()
    await connect_safe(c0, c1)
    # test case: `peer_id` not found
    with pytest.raises(ControlFailure):
        await c0.find_peer(peer_id_random)
    # test case: no route to the peer with peer_id_2
    with pytest.raises(ControlFailure):
        await c0.find_peer(peer_id_2)


@pytest.mark.asyncio
async def test_client_find_peers_connected_to_peer_success(p2pds):
    c0, c1, c2 = p2pds[0].client, p2pds[1].client, p2pds[2].client
    peer_id_2, _ = await c2.identify()
    await connect_safe(c0, c1)
    # test case: 0 <-> 1 <-> 2
    await connect_safe(c1, c2)
    pinfos_connecting_to_2 = await c0.find_peers_connected_to_peer(peer_id_2)
    # TODO: need to confirm this behaviour. Why the result is the PeerInfo of `peer_id_2`?
    assert len(pinfos_connecting_to_2) == 1


@pytest.mark.asyncio
async def test_client_find_peers_connected_to_peer_failure(peer_id_random, p2pds):
    c0, c1, c2 = p2pds[0].client, p2pds[1].client, p2pds[2].client
    peer_id_2, _ = await c2.identify()
    await connect_safe(c0, c1)
    # test case: request for random peer_id
    pinfos = await c0.find_peers_connected_to_peer(peer_id_random)
    assert not pinfos
    # test case: no route to the peer with peer_id_2
    pinfos = await c0.find_peers_connected_to_peer(peer_id_2)
    assert not pinfos


@pytest.mark.asyncio
async def test_client_find_providers(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    await connect_safe(c0, c1)
    # borrowed from https://github.com/ipfs/go-cid#parsing-string-input-from-users
    content_id_bytes = b'\x01r\x12 \xc0F\xc8\xechB\x17\xf0\x1b$\xb9\xecw\x11\xde\x11Cl\x8eF\xd8\x9a\xf1\xaeLa?\xb0\xaf\xe6K\x8b'  # noqa: E501
    pinfos = await c1.find_providers(content_id_bytes, 100)
    assert not pinfos


@pytest.mark.asyncio
async def test_client_get_closest_peers(p2pds):
    c0, c1, c2 = p2pds[0].client, p2pds[1].client, p2pds[2].client
    await connect_safe(c0, c1)
    await connect_safe(c1, c2)
    peer_ids_1 = await c1.get_closest_peers(b"123")
    assert len(peer_ids_1) == 2


@pytest.mark.asyncio
async def test_client_get_public_key_success(peer_id_random, p2pds):
    c0, c1, c2 = p2pds[0].client, p2pds[1].client, p2pds[2].client
    peer_id_0, _ = await c0.identify()
    peer_id_1, _ = await c1.identify()
    await connect_safe(c0, c1)
    await connect_safe(c1, c2)
    await asyncio.sleep(0.2)
    pk0 = await c0.get_public_key(peer_id_0)
    pk1 = await c0.get_public_key(peer_id_1)
    assert pk0 != pk1


@pytest.mark.asyncio
async def test_client_get_public_key_failure(peer_id_random, p2pds):
    c0, c1, c2 = p2pds[0].client, p2pds[1].client, p2pds[2].client
    peer_id_2, _ = await c2.identify()
    await connect_safe(c0, c1)
    await connect_safe(c1, c2)
    # test case: failed to get the pubkey of the peer_id_random
    with pytest.raises(ControlFailure):
        await c0.get_public_key(peer_id_random)
    # test case: should get the pubkey of the peer_id_2
    # TODO: why?
    await c0.get_public_key(peer_id_2)


@pytest.mark.asyncio
async def test_client_get_value(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    key_not_existing = b"/123/456"
    # test case: no peer in table
    with pytest.raises(ControlFailure):
        await c0.get_value(key_not_existing)
    await connect_safe(c0, c1)
    # test case: routing not found
    with pytest.raises(ControlFailure):
        await c0.get_value(key_not_existing)


@pytest.mark.asyncio
async def test_client_search_value(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    key_not_existing = b"/123/456"
    # test case: no peer in table
    with pytest.raises(ControlFailure):
        await c0.search_value(key_not_existing)
    await connect_safe(c0, c1)
    # test case: non-existing key
    pinfos = await c0.search_value(key_not_existing)
    assert len(pinfos) == 0


@pytest.mark.asyncio
async def test_client_put_value(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    peer_id_0, _ = await c0.identify()
    await connect_safe(c0, c1)

    # test case: valid key
    pk0 = await c0.get_public_key(peer_id_0)
    # make the `key` from pk0
    algo = multihash.Func.sha2_256
    value = pk0.Data
    mh_digest = multihash.digest(value, algo)
    mh_digest_bytes = mh_digest.encode()
    key = b"/pk/" + mh_digest_bytes
    await c0.put_value(key, value)
    # test case: get_value
    await c1.get_value(key) == value

    # test case: invalid key
    key_invalid = b"/123/456"
    with pytest.raises(ControlFailure):
        await c0.put_value(key_invalid, key_invalid)


@pytest.mark.asyncio
async def test_client_provide(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    peer_id_0, _ = await c0.identify()
    await connect_safe(c0, c1)
    # test case: no providers
    content_id_bytes = b'\x01r\x12 \xc0F\xc8\xechB\x17\xf0\x1b$\xb9\xecw\x11\xde\x11Cl\x8eF\xd8\x9a\xf1\xaeLa?\xb0\xaf\xe6K\x8b'  # noqa: E501
    pinfos_empty = await c1.find_providers(content_id_bytes, 100)
    assert not pinfos_empty
    # test case: c0 provides
    await c0.provide(content_id_bytes)
    pinfos = await c1.find_providers(content_id_bytes, 100)
    assert len(pinfos) == 1
    assert pinfos[0].peer_id == peer_id_0


@pytest.mark.parametrize(
    'enable_connmgr',
    (
        True,
    ),
)
@pytest.mark.asyncio
async def test_client_tag_peer(peer_id_random, p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    peer_id_0, _ = await c0.identify()
    # test case: tag myself
    await c0.tag_peer(peer_id_0, "123", 123)
    # test case: tag others
    await c1.tag_peer(peer_id_0, "123", 123)
    # test case: tag the same peers multiple times
    await c1.tag_peer(peer_id_0, "456", 456)
    # test case: tag multiple peers
    await c1.tag_peer(peer_id_random, "123", 1)
    # test case: tag the same peer with the same tag but different weight
    await c1.tag_peer(peer_id_random, "123", 123)


@pytest.mark.parametrize(
    'enable_connmgr',
    (
        True,
    ),
)
@pytest.mark.asyncio
async def test_client_untag_peer(peer_id_random, p2pds):
    c0 = p2pds[0].client
    # test case: untag an inexisting tag
    await c0.untag_peer(peer_id_random, "123")
    # test case: untag a tag
    await c0.tag_peer(peer_id_random, "123", 123)
    await c0.untag_peer(peer_id_random, "123")
    # test case: untag a tag twice
    await c0.untag_peer(peer_id_random, "123")


@pytest.mark.parametrize(
    'enable_connmgr',
    (
        True,
    ),
)
@pytest.mark.asyncio
async def test_client_trim_automatically_by_connmgr(p2pds):
    c0, c1, c2, c3 = p2pds[0].client, p2pds[1].client, p2pds[2].client, p2pds[3].client
    await connect_safe(c1, c0)
    await connect_safe(c1, c2)
    await connect_safe(c1, c3)
    # sleep to wait for the goroutine `Connmgr.TrimOpenConns` invoked by `mNotifee.Connected`
    await asyncio.sleep(1)
    assert len(await c1.list_peers()) == 2


@pytest.mark.parametrize(
    'enable_connmgr',
    (
        True,
    ),
)
@pytest.mark.asyncio
async def test_client_trim(p2pds):
    c0, c1, c2 = p2pds[0].client, p2pds[1].client, p2pds[2].client
    peer_id_0, _ = await c0.identify()
    peer_id_2, _ = await c2.identify()
    await connect_safe(c1, c0)
    await connect_safe(c1, c2)
    assert len(await c1.list_peers()) == 2
    await c1.tag_peer(peer_id_0, "123", 1)
    await c1.tag_peer(peer_id_2, "123", 2)
    # trim the connections, the number of connections should go down to the low watermark
    await c1.trim()
    peers_1 = await c1.list_peers()
    assert len(peers_1) == 1
    assert peers_1[0].peer_id == peer_id_2


@pytest.mark.asyncio
async def test_client_get_topics(p2pds):
    c0 = p2pds[0].client
    topics = await c0.get_topics()
    assert len(topics) == 0


@pytest.mark.asyncio
async def test_client_list_topic_peers(p2pds):
    c0 = p2pds[0].client
    peers = await c0.list_topic_peers("123")
    assert len(peers) == 0


@pytest.mark.asyncio
async def test_client_publish(p2pds):
    c0 = p2pds[0].client
    await c0.publish("123", b"data")


@pytest.mark.asyncio
async def test_client_subscribe(p2pds):
    c0, c1 = p2pds[0].client, p2pds[1].client
    peer_id_0, _ = await c0.identify()
    peer_id_1, _ = await c1.identify()
    await connect_safe(c0, c1)
    topic = "topic123"
    data = b"data"
    reader_0, writer_0 = await c0.subscribe(topic)
    reader_1, _ = await c1.subscribe(topic)
    # test case: `get_topics` after subscriptions
    assert topic in await c0.get_topics()
    assert topic in await c1.get_topics()
    # wait for mesh built
    await asyncio.sleep(2)
    # test case: `list_topic_peers` after subscriptions
    assert peer_id_0 in await c1.list_topic_peers(topic)
    assert peer_id_1 in await c0.list_topic_peers(topic)
    # test case: publish, and both clients receive data
    await c0.publish(topic, data)
    pubsub_msg_0 = p2pd_pb.PSMessage()
    await read_pbmsg_safe(reader_0, pubsub_msg_0)
    assert pubsub_msg_0.data == data
    pubsub_msg_1 = p2pd_pb.PSMessage()
    await read_pbmsg_safe(reader_1, pubsub_msg_1)
    assert pubsub_msg_1.data == data
    # test case: publish more data
    another_data_0 = b"another_data_0"
    another_data_1 = b"another_data_1"
    await c0.publish(topic, another_data_0)
    await c0.publish(topic, another_data_1)
    pubsub_msg_1_0 = p2pd_pb.PSMessage()
    await read_pbmsg_safe(reader_1, pubsub_msg_1_0)
    assert pubsub_msg_1_0.data == another_data_0
    pubsub_msg_1_1 = p2pd_pb.PSMessage()
    await read_pbmsg_safe(reader_1, pubsub_msg_1_1)
    assert pubsub_msg_1_1.data == another_data_1
    # test case: unsubscribe by closing the stream
    writer_0.close()
    await reader_0.read() == b""
    assert topic not in await c0.get_topics()
    assert peer_id_0 not in await c1.list_topic_peers(topic)
