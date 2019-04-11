import asyncio
import functools
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
    ConnectionManagerClient,
    ControlClient,
    DHTClient,
    PubSubClient,
    read_pbmsg_safe,
)

import libp2p.p2pclient.pb.p2pd_pb2 as p2pd_pb


NUM_P2PDS = 4
TIMEOUT_DURATION = 120  # seconds


@pytest.fixture(scope="module")
def peer_id_random():
    return PeerID.from_base58("QmcgpsyWgH8Y8ajJz1Cu72KnS5uo2Aa2LpzU7kinSupNK1")


@pytest.fixture
def enable_control():
    return False


@pytest.fixture
def enable_connmgr():
    return False


@pytest.fixture
def enable_dht():
    return False


@pytest.fixture
def enable_pubsub():
    return False


async def try_until_success(coro_func, timeout=TIMEOUT_DURATION):
    """
    Keep running ``coro_func`` until the time is out.
    All arguments of ``coro_func`` should be filled, i.e. it should be called without arguments.
    """
    t_start = time.monotonic()
    while True:
        result = await coro_func()
        if result:
            break
        if (time.monotonic() - t_start) >= timeout:
            # timeout
            assert False, f"{coro_func} still failed after `{timeout}` seconds"
        await asyncio.sleep(0.01)


class Daemon:
    control_maddr = None
    proc_daemon = None
    log_filename = ""
    f_log = None
    closed = None

    def __init__(self, control_maddr, enable_control, enable_connmgr, enable_dht, enable_pubsub):
        self.control_maddr = control_maddr
        self.enable_control = enable_control
        self.enable_connmgr = enable_connmgr
        self.enable_dht = enable_dht
        self.enable_pubsub = enable_pubsub
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
        ]
        if self.enable_connmgr:
            cmd_list += [
                "-connManager=true",
                "-connLo=1",
                "-connHi=2",
                "-connGrace=0",
            ]
        if self.enable_dht:
            cmd_list += [
                "-dht=true",
            ]
        if self.enable_pubsub:
            cmd_list += [
                "-pubsub=true",
                "-pubsubRouter=gossipsub",
            ]
        self.proc_daemon = subprocess.Popen(
            cmd_list,
            stdout=self.f_log,
            stderr=self.f_log,
            bufsize=0,
        )

    async def wait_until_ready(self):
        lines_head_pattern = (
            b'Control socket:',
            b'Peer ID:',
            b'Peer Addrs:',
        )
        lines_head_occurred = {
            line: False
            for line in lines_head_pattern
        }

        with open(self.log_filename, 'rb') as f_log_read:
            async def read_from_daemon_and_check():
                line = f_log_read.readline()
                for head_pattern in lines_head_occurred:
                    if line.startswith(head_pattern):
                        lines_head_occurred[head_pattern] = True
                return all([value for _, value in lines_head_occurred.items()])

            await try_until_success(read_from_daemon_and_check)

        # sleep for a while in case that the daemon haven't been ready after emitting these lines
        await asyncio.sleep(0.1)

    def close(self):
        if self.is_closed:
            return
        self.proc_daemon.terminate()
        self.proc_daemon.wait()
        self.f_log.close()
        self.is_closed = True


class DaemonTuple(NamedTuple):
    daemon: Daemon
    client: Client
    control: ControlClient
    connmgr: ConnectionManagerClient
    dht: DHTClient
    pubsub: PubSubClient


class ConnectionFailure(Exception):
    pass


async def make_p2pd_pair_unix(
        id_generator, enable_control, enable_connmgr, enable_dht, enable_pubsub):
    socket_id = id_generator()
    control_maddr = Multiaddr(f"/unix/tmp/test_p2pd_control_{socket_id}.sock")
    listen_maddr = Multiaddr(f"/unix/tmp/test_p2pd_listen_{socket_id}.sock")
    # remove the existing unix socket files if they are existing
    try:
        os.unlink(control_maddr.value_for_protocol(protocols.P_UNIX))
    except FileNotFoundError:
        pass
    try:
        os.unlink(listen_maddr.value_for_protocol(protocols.P_UNIX))
    except FileNotFoundError:
        pass
    return await _make_p2pd_pair(
        control_maddr=control_maddr,
        listen_maddr=listen_maddr,
        enable_control=enable_control,
        enable_connmgr=enable_connmgr,
        enable_dht=enable_dht,
        enable_pubsub=enable_pubsub,
    )


async def make_p2pd_pair_ip4(
        id_generator, enable_control, enable_connmgr, enable_dht, enable_pubsub):
    control_maddr = Multiaddr(f"/ip4/127.0.0.1/tcp/{id_generator()}")
    listen_maddr = Multiaddr(f"/ip4/127.0.0.1/tcp/{id_generator()}")
    return await _make_p2pd_pair(
        control_maddr=control_maddr,
        listen_maddr=listen_maddr,
        enable_control=enable_control,
        enable_connmgr=enable_connmgr,
        enable_dht=enable_dht,
        enable_pubsub=enable_pubsub,
    )


async def _make_p2pd_pair(
        control_maddr,
        listen_maddr,
        enable_control,
        enable_connmgr,
        enable_dht,
        enable_pubsub):
    p2pd = Daemon(
        control_maddr=control_maddr,
        enable_control=enable_control,
        enable_connmgr=enable_connmgr,
        enable_dht=enable_dht,
        enable_pubsub=enable_pubsub,
    )
    # wait for daemon ready
    await p2pd.wait_until_ready()
    client = Client(control_maddr)
    controlc = None
    connmgrc = None
    dhtc = None
    pubsubc = None
    if enable_control:
        controlc = ControlClient(client=client, listen_maddr=listen_maddr)
        await controlc.listen()
    if enable_connmgr:
        connmgrc = ConnectionManagerClient(client=client)
    if enable_dht:
        dhtc = DHTClient(client=client)
    if enable_pubsub:
        pubsubc = PubSubClient(client=client)
    return DaemonTuple(
        daemon=p2pd,
        client=client,
        control=controlc,
        connmgr=connmgrc,
        dht=dhtc,
        pubsub=pubsubc,
    )


@pytest.fixture(params=[make_p2pd_pair_ip4, make_p2pd_pair_unix])
async def p2pds(
        request,
        enable_control,
        enable_connmgr,
        enable_dht,
        enable_pubsub,
        unused_tcp_port_factory):
    make_p2pd_pair = request.param
    pairs = tuple(
        asyncio.ensure_future(
            make_p2pd_pair(
                id_generator=unused_tcp_port_factory,
                enable_control=enable_control,
                enable_connmgr=enable_connmgr,
                enable_dht=enable_dht,
                enable_pubsub=enable_pubsub,
            )
        )
        for i in range(NUM_P2PDS)
    )
    p2pd_tuples = await asyncio.gather(*pairs)
    yield p2pd_tuples

    # clean up
    for p2pd_tuple in p2pd_tuples:
        if not p2pd_tuple.daemon.is_closed:
            p2pd_tuple.daemon.close()
        if p2pd_tuple.control.listener is not None:
            await p2pd_tuple.control.close()


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_control_client_listen(p2pds):
    c0 = p2pds[0].control
    # test case: ensure the server is listening
    assert c0.listener is not None
    assert c0.listener.sockets is not None
    assert len(c0.listener.sockets) != 0
    # test case: listen twice
    with pytest.raises(ControlFailure):
        await c0.listen()


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_control_client_close(p2pds):
    c0 = p2pds[0].control
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


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_control_client_identify(p2pds):
    await p2pds[0].control.identify()


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_control_client_connect_success(p2pds):
    c0, c1 = p2pds[0].control, p2pds[1].control
    peer_id_0, maddrs_0 = await c0.identify()
    peer_id_1, maddrs_1 = await c1.identify()
    await c0.connect(peer_id_1, maddrs_1)
    # test case: repeated connections
    await c1.connect(peer_id_0, maddrs_0)


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_control_client_connect_failure(peer_id_random, p2pds):
    c0, c1 = p2pds[0].control, p2pds[1].control
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


async def _check_connection(p2pd_tuple_0, p2pd_tuple_1):
    peer_id_0, _ = await p2pd_tuple_0.control.identify()
    peer_id_1, _ = await p2pd_tuple_1.control.identify()
    peers_0 = [pinfo.peer_id for pinfo in await p2pd_tuple_0.control.list_peers()]
    peers_1 = [pinfo.peer_id for pinfo in await p2pd_tuple_1.control.list_peers()]
    return (peer_id_0 in peers_1) and (peer_id_1 in peers_0)


async def connect_safe(p2pd_tuple_0, p2pd_tuple_1):
    peer_id_1, maddrs_1 = await p2pd_tuple_1.control.identify()
    await p2pd_tuple_0.control.connect(peer_id_1, maddrs_1)
    await try_until_success(
        functools.partial(
            _check_connection,
            p2pd_tuple_0=p2pd_tuple_0,
            p2pd_tuple_1=p2pd_tuple_1,
        ),
    )


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_connect_safe(p2pds):
    await connect_safe(p2pds[0], p2pds[1])


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_control_client_list_peers(p2pds):
    c0, c1, c2 = p2pds[0].control, p2pds[1].control, p2pds[2].control
    # test case: no peers
    assert len(await c0.list_peers()) == 0
    # test case: 1 peer
    await connect_safe(p2pds[0], p2pds[1])
    assert len(await c0.list_peers()) == 1
    assert len(await c1.list_peers()) == 1
    # test case: one more peer
    await connect_safe(p2pds[0], p2pds[2])
    assert len(await c0.list_peers()) == 2
    assert len(await c1.list_peers()) == 1
    assert len(await c2.list_peers()) == 1


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_controle_client_disconnect(peer_id_random, p2pds):
    c0, c1 = p2pds[0].control, p2pds[1].control
    # test case: disconnect a peer without connections
    await c1.disconnect(peer_id_random)
    # test case: disconnect
    peer_id_0, _ = await c0.identify()
    await connect_safe(p2pds[0], p2pds[1])
    assert len(await c0.list_peers()) == 1
    assert len(await c1.list_peers()) == 1
    await c1.disconnect(peer_id_0)
    assert len(await c0.list_peers()) == 0
    assert len(await c1.list_peers()) == 0
    # test case: disconnect twice
    await c1.disconnect(peer_id_0)
    assert len(await c0.list_peers()) == 0
    assert len(await c1.list_peers()) == 0


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_control_client_stream_open_success(p2pds):
    c0, c1 = p2pds[0].control, p2pds[1].control

    peer_id_1, maddrs_1 = await c1.identify()
    await connect_safe(p2pds[0], p2pds[1])

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


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_control_client_stream_open_failure(p2pds):
    c0, c1 = p2pds[0].control, p2pds[1].control

    peer_id_1, _ = await c1.identify()
    await connect_safe(p2pds[0], p2pds[1])

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


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_control_client_stream_handler_success(p2pds):
    c0, c1 = p2pds[0].control, p2pds[1].control

    peer_id_1, _ = await c1.identify()
    await connect_safe(p2pds[0], p2pds[1])

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


@pytest.mark.parametrize(
    'enable_control',
    (True,),
)
@pytest.mark.asyncio
async def test_control_client_stream_handler_failure(p2pds):
    c0, c1 = p2pds[0].control, p2pds[1].control

    peer_id_1, _ = await c1.identify()
    await connect_safe(p2pds[0], p2pds[1])

    proto = "123"

    # test case: registered a wrong protocol name
    async def handle_proto_correct_params(stream_info, reader, writer):
        pass

    await c1.stream_handler("another_protocol", handle_proto_correct_params)
    with pytest.raises(ControlFailure):
        await c0.stream_open(peer_id_1, (proto,))


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_find_peer_success(p2pds):
    peer_id_2, _ = await p2pds[2].control.identify()
    await connect_safe(p2pds[0], p2pds[1])
    await connect_safe(p2pds[1], p2pds[2])
    pinfo = await p2pds[0].dht.find_peer(peer_id_2)
    assert pinfo.peer_id == peer_id_2
    assert len(pinfo.addrs) != 0


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_find_peer_failure(peer_id_random, p2pds):
    peer_id_2, _ = await p2pds[2].control.identify()
    await connect_safe(p2pds[0], p2pds[1])
    # test case: `peer_id` not found
    with pytest.raises(ControlFailure):
        await p2pds[0].dht.find_peer(peer_id_random)
    # test case: no route to the peer with peer_id_2
    with pytest.raises(ControlFailure):
        await p2pds[0].dht.find_peer(peer_id_2)


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_find_peers_connected_to_peer_success(p2pds):
    peer_id_2, _ = await p2pds[2].control.identify()
    await connect_safe(p2pds[0], p2pds[1])
    # test case: 0 <-> 1 <-> 2
    await connect_safe(p2pds[1], p2pds[2])
    pinfos_connecting_to_2 = await p2pds[0].dht.find_peers_connected_to_peer(peer_id_2)
    # TODO: need to confirm this behaviour. Why the result is the PeerInfo of `peer_id_2`?
    assert len(pinfos_connecting_to_2) == 1


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_find_peers_connected_to_peer_failure(peer_id_random, p2pds):
    peer_id_2, _ = await p2pds[2].control.identify()
    await connect_safe(p2pds[0], p2pds[1])
    # test case: request for random peer_id
    pinfos = await p2pds[0].dht.find_peers_connected_to_peer(peer_id_random)
    assert not pinfos
    # test case: no route to the peer with peer_id_2
    pinfos = await p2pds[0].dht.find_peers_connected_to_peer(peer_id_2)
    assert not pinfos


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_find_providers(p2pds):
    await connect_safe(p2pds[0], p2pds[1])
    # borrowed from https://github.com/ipfs/go-cid#parsing-string-input-from-users
    content_id_bytes = b'\x01r\x12 \xc0F\xc8\xechB\x17\xf0\x1b$\xb9\xecw\x11\xde\x11Cl\x8eF\xd8\x9a\xf1\xaeLa?\xb0\xaf\xe6K\x8b'  # noqa: E501
    pinfos = await p2pds[1].dht.find_providers(content_id_bytes, 100)
    assert not pinfos


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_get_closest_peers(p2pds):
    await connect_safe(p2pds[0], p2pds[1])
    await connect_safe(p2pds[1], p2pds[2])
    peer_ids_1 = await p2pds[1].dht.get_closest_peers(b"123")
    assert len(peer_ids_1) == 2


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_get_public_key_success(peer_id_random, p2pds):
    peer_id_0, _ = await p2pds[0].control.identify()
    peer_id_1, _ = await p2pds[1].control.identify()
    await connect_safe(p2pds[0], p2pds[1])
    await connect_safe(p2pds[1], p2pds[2])
    await asyncio.sleep(0.2)
    pk0 = await p2pds[0].dht.get_public_key(peer_id_0)
    pk1 = await p2pds[0].dht.get_public_key(peer_id_1)
    assert pk0 != pk1


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_get_public_key_failure(peer_id_random, p2pds):
    peer_id_2, _ = await p2pds[2].control.identify()
    await connect_safe(p2pds[0], p2pds[1])
    await connect_safe(p2pds[1], p2pds[2])
    # test case: failed to get the pubkey of the peer_id_random
    with pytest.raises(ControlFailure):
        await p2pds[0].dht.get_public_key(peer_id_random)
    # test case: should get the pubkey of the peer_id_2
    # TODO: why?
    await p2pds[0].dht.get_public_key(peer_id_2)


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_get_value(p2pds):
    key_not_existing = b"/123/456"
    # test case: no peer in table
    with pytest.raises(ControlFailure):
        await p2pds[0].dht.get_value(key_not_existing)
    await connect_safe(p2pds[0], p2pds[1])
    # test case: routing not found
    with pytest.raises(ControlFailure):
        await p2pds[0].dht.get_value(key_not_existing)


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_search_value(p2pds):
    key_not_existing = b"/123/456"
    # test case: no peer in table
    with pytest.raises(ControlFailure):
        await p2pds[0].dht.search_value(key_not_existing)
    await connect_safe(p2pds[0], p2pds[1])
    # test case: non-existing key
    pinfos = await p2pds[0].dht.search_value(key_not_existing)
    assert len(pinfos) == 0


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_put_value(p2pds):
    peer_id_0, _ = await p2pds[0].control.identify()
    await connect_safe(p2pds[0], p2pds[1])

    # test case: valid key
    pk0 = await p2pds[0].dht.get_public_key(peer_id_0)
    # make the `key` from pk0
    algo = multihash.Func.sha2_256
    value = pk0.Data
    mh_digest = multihash.digest(value, algo)
    mh_digest_bytes = mh_digest.encode()
    key = b"/pk/" + mh_digest_bytes
    await p2pds[0].dht.put_value(key, value)
    # test case: get_value
    await p2pds[1].dht.get_value(key) == value

    # test case: invalid key
    key_invalid = b"/123/456"
    with pytest.raises(ControlFailure):
        await p2pds[0].dht.put_value(key_invalid, key_invalid)


@pytest.mark.parametrize(
    'enable_control, enable_dht',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_dht_client_provide(p2pds):
    peer_id_0, _ = await p2pds[0].control.identify()
    await connect_safe(p2pds[0], p2pds[1])
    # test case: no providers
    content_id_bytes = b'\x01r\x12 \xc0F\xc8\xechB\x17\xf0\x1b$\xb9\xecw\x11\xde\x11Cl\x8eF\xd8\x9a\xf1\xaeLa?\xb0\xaf\xe6K\x8b'  # noqa: E501
    pinfos_empty = await p2pds[1].dht.find_providers(content_id_bytes, 100)
    assert not pinfos_empty
    # test case: c0 provides
    await p2pds[0].dht.provide(content_id_bytes)
    pinfos = await p2pds[1].dht.find_providers(content_id_bytes, 100)
    assert len(pinfos) == 1
    assert pinfos[0].peer_id == peer_id_0


@pytest.mark.parametrize(
    'enable_control, enable_connmgr',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_connmgr_client_tag_peer(peer_id_random, p2pds):
    peer_id_0, _ = await p2pds[0].control.identify()
    # test case: tag myself
    await p2pds[0].connmgr.tag_peer(peer_id_0, "123", 123)
    # test case: tag others
    await p2pds[1].connmgr.tag_peer(peer_id_0, "123", 123)
    # test case: tag the same peers multiple times
    await p2pds[1].connmgr.tag_peer(peer_id_0, "456", 456)
    # test case: tag multiple peers
    await p2pds[1].connmgr.tag_peer(peer_id_random, "123", 1)
    # test case: tag the same peer with the same tag but different weight
    await p2pds[1].connmgr.tag_peer(peer_id_random, "123", 123)


@pytest.mark.parametrize(
    'enable_control, enable_connmgr',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_connmgr_client_untag_peer(peer_id_random, p2pds):
    # test case: untag an inexisting tag
    await p2pds[0].connmgr.untag_peer(peer_id_random, "123")
    # test case: untag a tag
    await p2pds[0].connmgr.tag_peer(peer_id_random, "123", 123)
    await p2pds[0].connmgr.untag_peer(peer_id_random, "123")
    # test case: untag a tag twice
    await p2pds[0].connmgr.untag_peer(peer_id_random, "123")


@pytest.mark.parametrize(
    'enable_control, enable_connmgr',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_connmgr_client_trim_automatically_by_connmgr(p2pds):
    # test case: due to `connHi=2` and `connLo=1`, when `p2pds[1]` connecting to the third peer,
    #            `p2pds[3]`, the connmgr of `p2pds[1]` will try to prune the connections, down to
    #            `connLo=1`.
    peer_id_0, maddrs_0 = await p2pds[0].control.identify()
    peer_id_2, maddrs_2 = await p2pds[2].control.identify()
    peer_id_3, maddrs_3 = await p2pds[3].control.identify()
    await p2pds[1].control.connect(peer_id_0, maddrs_0)
    await p2pds[1].control.connect(peer_id_2, maddrs_2)
    await p2pds[1].control.connect(peer_id_3, maddrs_3)
    # sleep to wait for the goroutine `Connmgr.TrimOpenConns` invoked by `mNotifee.Connected`
    await asyncio.sleep(1)
    assert len(await p2pds[1].control.list_peers()) == 1


@pytest.mark.parametrize(
    'enable_control, enable_connmgr',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_connmgr_client_trim(p2pds):
    peer_id_0, _ = await p2pds[0].control.identify()
    peer_id_2, _ = await p2pds[2].control.identify()
    await connect_safe(p2pds[1], p2pds[0])
    await connect_safe(p2pds[1], p2pds[2])
    assert len(await p2pds[1].control.list_peers()) == 2
    await p2pds[1].connmgr.tag_peer(peer_id_0, "123", 1)
    await p2pds[1].connmgr.tag_peer(peer_id_2, "123", 2)
    # trim the connections, the number of connections should go down to the low watermark
    await p2pds[1].connmgr.trim()
    peers_1 = await p2pds[1].control.list_peers()
    assert len(peers_1) == 1
    assert peers_1[0].peer_id == peer_id_2


@pytest.mark.parametrize(
    'enable_control, enable_pubsub',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_pubsub_client_get_topics(p2pds):
    topics = await p2pds[0].pubsub.get_topics()
    assert len(topics) == 0


@pytest.mark.parametrize(
    'enable_control, enable_pubsub',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_pubsub_client_list_topic_peers(p2pds):
    peers = await p2pds[0].pubsub.list_peers("123")
    assert len(peers) == 0


@pytest.mark.parametrize(
    'enable_control, enable_pubsub',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_pubsub_client_publish(p2pds):
    await p2pds[0].pubsub.publish("123", b"data")


@pytest.mark.parametrize(
    'enable_control, enable_pubsub',
    (
        (True, True),
    ),
)
@pytest.mark.asyncio
async def test_pubsub_client_subscribe(p2pds):
    peer_id_0, _ = await p2pds[0].control.identify()
    peer_id_1, _ = await p2pds[1].control.identify()
    await connect_safe(p2pds[0], p2pds[1])
    await connect_safe(p2pds[1], p2pds[2])
    topic = "topic123"
    data = b"data"
    reader_0, writer_0 = await p2pds[0].pubsub.subscribe(topic)
    reader_1, _ = await p2pds[1].pubsub.subscribe(topic)
    # test case: `get_topics` after subscriptions
    assert topic in await p2pds[0].pubsub.get_topics()
    assert topic in await p2pds[1].pubsub.get_topics()
    # wait for mesh built
    await asyncio.sleep(2)
    # test case: `list_topic_peers` after subscriptions
    assert peer_id_0 in await p2pds[1].pubsub.list_peers(topic)
    assert peer_id_1 in await p2pds[0].pubsub.list_peers(topic)
    # test case: publish, and both clients receive data
    await p2pds[0].pubsub.publish(topic, data)
    pubsub_msg_0 = p2pd_pb.PSMessage()
    await read_pbmsg_safe(reader_0, pubsub_msg_0)
    assert pubsub_msg_0.data == data
    pubsub_msg_1 = p2pd_pb.PSMessage()
    await read_pbmsg_safe(reader_1, pubsub_msg_1)
    assert pubsub_msg_1.data == data
    # test case: publish more data
    another_data_0 = b"another_data_0"
    another_data_1 = b"another_data_1"
    await p2pds[0].pubsub.publish(topic, another_data_0)
    await p2pds[0].pubsub.publish(topic, another_data_1)
    pubsub_msg_1_0 = p2pd_pb.PSMessage()
    await read_pbmsg_safe(reader_1, pubsub_msg_1_0)
    pubsub_msg_1_1 = p2pd_pb.PSMessage()
    await read_pbmsg_safe(reader_1, pubsub_msg_1_1)
    assert set([pubsub_msg_1_0.data, pubsub_msg_1_1.data]) == set([another_data_0, another_data_1])
    # test case: subscribe to multiple topics
    another_topic = "topic456"
    reader_0_another, writer_0_another = await p2pds[0].pubsub.subscribe(another_topic)
    reader_1_another, writer_1_another = await p2pds[1].pubsub.subscribe(another_topic)
    await p2pds[0].pubsub.publish(another_topic, another_data_0)
    pubsub_msg_1_another = p2pd_pb.PSMessage()
    await read_pbmsg_safe(reader_1_another, pubsub_msg_1_another)
    assert pubsub_msg_1_another.data == another_data_0
    # test case: test `from_field`
    assert PeerID(pubsub_msg_1_1.from_field) == peer_id_0
    # test case: test `from_field`, when it is sent through 1 hop(p2pds[1])
    reader_2, writer_2 = await p2pds[2].pubsub.subscribe(topic)
    another_data_2 = b"another_data_2"
    await p2pds[0].pubsub.publish(topic, another_data_2)
    pubsub_msg_2_0 = p2pd_pb.PSMessage()
    await read_pbmsg_safe(reader_2, pubsub_msg_2_0)
    assert PeerID(pubsub_msg_2_0.from_field) == peer_id_0
    # test case: unsubscribe by closing the stream
    writer_0.close()
    await asyncio.sleep(0)
    assert topic not in await p2pds[0].pubsub.get_topics()

    async def is_peer_removed_from_topic():
        return (peer_id_0 not in await p2pds[1].pubsub.list_peers(topic))

    await try_until_success(is_peer_removed_from_topic)
