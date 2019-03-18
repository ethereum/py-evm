import asyncio
import binascii
import logging
from typing import (
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    Sequence,
    Tuple,
)

from google.protobuf.message import (
    Message as PBMessage,
)
from multiaddr import (
    Multiaddr,
    protocols,
)

from . import config

from .datastructures import (
    PeerID,
    PeerInfo,
    StreamInfo,
)
from .exceptions import (
    ControlFailure,
    DispatchFailure,
)
from .serialization import (
    read_unsigned_varint,
    write_unsigned_varint,
)
from .utils import (
    raise_if_failed,
)

from .pb import p2pd_pb2 as p2pd_pb
from .pb import crypto_pb2 as crypto_pb


StreamHandler = Callable[
    [StreamInfo, asyncio.StreamReader, asyncio.StreamWriter],
    Awaitable[None],
]


_supported_conn_protocols = (
    protocols.P_IP4,
    # protocols.P_IP6,
    protocols.P_UNIX,
)


def parse_conn_protocol(maddr: Multiaddr) -> int:
    proto_codes = set(
        proto.code
        for proto in maddr.protocols()
    )
    proto_cand = proto_codes.intersection(_supported_conn_protocols)
    if len(proto_cand) != 1:
        supported_protos = (
            protocols.protocol_with_code(proto)
            for proto in _supported_conn_protocols
        )
        raise ValueError(
            f"connection protocol should be only one protocol out of {supported_protos}"
            ", maddr={maddr}"
        )
    return tuple(proto_cand)[0]


async def write_pbmsg(writer: asyncio.StreamWriter, pbmsg: PBMessage) -> None:
    size = pbmsg.ByteSize()
    write_unsigned_varint(writer, size)
    msg_bytes: bytes = pbmsg.SerializeToString()
    writer.write(msg_bytes)
    await writer.drain()


async def read_pbmsg_safe(reader: asyncio.StreamReader, pbmsg: PBMessage) -> None:
    len_msg_bytes = await read_unsigned_varint(reader)
    msg_bytes = await reader.readexactly(len_msg_bytes)
    pbmsg.ParseFromString(msg_bytes)


class Client:
    control_maddr: Multiaddr
    logger = logging.getLogger('p2pclient.Client')

    def __init__(self, control_maddr: Multiaddr = None) -> None:
        if control_maddr is None:
            control_maddr = Multiaddr(config.control_maddr_str)
        self.control_maddr = control_maddr

    async def open_connection(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        proto_code = parse_conn_protocol(self.control_maddr)
        if proto_code == protocols.P_UNIX:
            control_path = self.control_maddr.value_for_protocol(protocols.P_UNIX)
            self.logger.debug("Client %s opens connection to %s", self, self.control_maddr)
            return await asyncio.open_unix_connection(control_path)
        elif proto_code == protocols.P_IP4:
            host = self.control_maddr.value_for_protocol(protocols.P_IP4)
            port = int(self.control_maddr.value_for_protocol(protocols.P_TCP))
            return await asyncio.open_connection(host=host, port=port)
        else:
            raise ValueError(
                f"protocol not supported: protocol={protocols.protocol_with_code(proto_code)}"
            )


class ControlClient:
    listen_maddr: Multiaddr
    client: Client
    handlers: Dict[str, StreamHandler]
    listener: asyncio.AbstractServer = None
    logger = logging.getLogger('p2pclient.ControlClient')

    def __init__(self, client: Client, listen_maddr: Multiaddr = None) -> None:
        if listen_maddr is None:
            listen_maddr = Multiaddr(config.listen_maddr_str)
        self.listen_maddr = listen_maddr
        self.client = client
        self.handlers = {}

    async def _dispatcher(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        pb_stream_info = p2pd_pb.StreamInfo()
        await read_pbmsg_safe(reader, pb_stream_info)
        stream_info = StreamInfo.from_pb(pb_stream_info)
        self.logger.info("New incoming stream: %s", stream_info)
        try:
            handler = self.handlers[stream_info.proto]
        except KeyError as e:
            # should never enter here... daemon should reject the stream for us.
            writer.close()
            raise DispatchFailure(e)
        await handler(stream_info, reader, writer)

    async def listen(self) -> None:
        if self.listener is not None:
            raise ControlFailure("Listener is already listening")
        proto_code = parse_conn_protocol(self.listen_maddr)
        if proto_code == protocols.P_UNIX:
            listen_path = self.listen_maddr.value_for_protocol(protocols.P_UNIX)
            self.listener = await asyncio.start_unix_server(self._dispatcher, listen_path)
        elif proto_code == protocols.P_IP4:
            host = self.listen_maddr.value_for_protocol(protocols.P_IP4)
            port = int(self.listen_maddr.value_for_protocol(protocols.P_TCP))
            self.listener = await asyncio.start_server(self._dispatcher, host=host, port=port)
        else:
            raise ValueError(
                f"protocol not supported: protocol={protocols.protocol_with_code(proto_code)}"
            )
        self.logger.info("Client %s starts listening to %s", self, self.listen_maddr)

    async def close(self) -> None:
        self.listener.close()
        await self.listener.wait_closed()
        self.listener = None
        self.logger.info("Client %s closed", self)

    async def identify(self) -> Tuple[PeerID, Tuple[Multiaddr, ...]]:
        reader, writer = await self.client.open_connection()
        req = p2pd_pb.Request(type=p2pd_pb.Request.IDENTIFY)
        await write_pbmsg(writer, req)

        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)
        peer_id_bytes = resp.identify.id
        maddrs_bytes = resp.identify.addrs

        maddrs = tuple(
            Multiaddr(binascii.hexlify(maddr_bytes))
            for maddr_bytes in maddrs_bytes
        )
        peer_id = PeerID(peer_id_bytes)

        return peer_id, maddrs

    async def connect(self, peer_id: PeerID, maddrs: Iterable[Multiaddr]) -> None:
        reader, writer = await self.client.open_connection()

        maddrs_bytes = [binascii.unhexlify(i.to_bytes()) for i in maddrs]
        connect_req = p2pd_pb.ConnectRequest(
            peer=peer_id.to_bytes(),
            addrs=maddrs_bytes,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.CONNECT,
            connect=connect_req,
        )
        await write_pbmsg(writer, req)

        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def list_peers(self) -> Tuple[PeerInfo, ...]:
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.LIST_PEERS,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

        peers = tuple(PeerInfo.from_pb(pinfo) for pinfo in resp.peers)
        return peers

    async def disconnect(self, peer_id: PeerID) -> None:
        disconnect_req = p2pd_pb.DisconnectRequest(
            peer=peer_id.to_bytes(),
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.DISCONNECT,
            disconnect=disconnect_req,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def stream_open(
            self,
            peer_id: PeerID,
            protocols: Sequence[str]) -> Tuple[
            StreamInfo, asyncio.StreamReader, asyncio.StreamWriter]:
        reader, writer = await self.client.open_connection()

        stream_open_req = p2pd_pb.StreamOpenRequest(
            peer=peer_id.to_bytes(),
            proto=list(protocols),
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.STREAM_OPEN,
            streamOpen=stream_open_req,
        )
        await write_pbmsg(writer, req)

        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        raise_if_failed(resp)

        pb_stream_info = resp.streamInfo
        stream_info = StreamInfo.from_pb(pb_stream_info)

        return stream_info, reader, writer

    async def stream_handler(self, proto: str, handler_cb: StreamHandler) -> None:
        reader, writer = await self.client.open_connection()

        listen_path_maddr_bytes = binascii.unhexlify(self.listen_maddr.to_bytes())
        stream_handler_req = p2pd_pb.StreamHandlerRequest(
            addr=listen_path_maddr_bytes,
            proto=[proto],
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.STREAM_HANDLER,
            streamHandler=stream_handler_req,
        )
        await write_pbmsg(writer, req)

        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

        # if success, add the handler to the dict
        self.handlers[proto] = handler_cb


class DHTClient:
    client: Client

    def __init__(self, client: Client) -> None:
        self.client = client

    @staticmethod
    async def _read_dht_stream(reader: asyncio.StreamReader) -> AsyncGenerator[
            p2pd_pb.DHTResponse, None]:
        while True:
            dht_resp = p2pd_pb.DHTResponse()
            await read_pbmsg_safe(reader, dht_resp)
            if dht_resp.type == dht_resp.END:
                break
            yield dht_resp

    async def _do_dht(self, dht_req: p2pd_pb.DHTRequest) -> Tuple[
            p2pd_pb.DHTResponse, ...]:
        reader, writer = await self.client.open_connection()
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.DHT,
            dht=dht_req,
        )
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        raise_if_failed(resp)

        try:
            dht_resp = resp.dht
        except AttributeError as e:
            raise ControlFailure(f"resp should contains dht: resp={resp}, e={e}")

        if dht_resp.type == dht_resp.VALUE:
            return (dht_resp,)

        if dht_resp.type != dht_resp.BEGIN:
            raise ControlFailure(f"Type should be BEGIN instead of {dht_resp.type}")
        # BEGIN/END stream
        resps = tuple([i async for i in self._read_dht_stream(reader)])
        writer.close()
        return resps

    async def find_peer(self, peer_id: PeerID) -> PeerInfo:
        """FIND_PEER
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.FIND_PEER,
            peer=peer_id.to_bytes(),
        )
        resps = await self._do_dht(dht_req)
        if len(resps) != 1:
            raise ControlFailure(f"should only get one response from `find_peer`, resps={resps}")
        dht_resp = resps[0]
        try:
            pinfo = dht_resp.peer
        except AttributeError as e:
            raise ControlFailure(f"dht_resp should contains peer info: dht_resp={dht_resp}, e={e}")
        return PeerInfo.from_pb(pinfo)

    async def find_peers_connected_to_peer(self, peer_id: PeerID) -> Tuple[PeerInfo, ...]:
        """FIND_PEERS_CONNECTED_TO_PEER
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.FIND_PEERS_CONNECTED_TO_PEER,
            peer=peer_id.to_bytes(),
        )
        resps = await self._do_dht(dht_req)
        try:
            pinfos = tuple(
                PeerInfo.from_pb(dht_resp.peer)
                for dht_resp in resps
            )
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains peer info: resps={resps}, e={e}"
            )
        return pinfos

    async def find_providers(self, content_id_bytes: bytes, count: int) -> Tuple[PeerInfo, ...]:
        """FIND_PROVIDERS
        """
        # TODO: should have another class ContendID
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.FIND_PROVIDERS,
            cid=content_id_bytes,
            count=count,
        )
        resps = await self._do_dht(dht_req)
        try:
            pinfos = tuple(
                PeerInfo.from_pb(dht_resp.peer)
                for dht_resp in resps
            )
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains peer info: resps={resps}, e={e}"
            )
        return pinfos

    async def get_closest_peers(self, key: bytes) -> Tuple[PeerID, ...]:
        """GET_CLOSEST_PEERS
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.GET_CLOSEST_PEERS,
            key=key,
        )
        resps = await self._do_dht(dht_req)
        try:
            peer_ids = tuple(
                PeerID(dht_resp.value)
                for dht_resp in resps
            )
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains `value`: resps={resps}, e={e}"
            )
        return peer_ids

    async def get_public_key(self, peer_id: PeerID) -> crypto_pb.PublicKey:
        """GET_PUBLIC_KEY
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.GET_PUBLIC_KEY,
            peer=peer_id.to_bytes(),
        )
        resps = await self._do_dht(dht_req)
        if len(resps) != 1:
            raise ControlFailure(f"should only get one response, resps={resps}")
        try:
            # TODO: parse the public key with another class?
            public_key_pb_bytes = resps[0].value
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains `value`: resps={resps}, e={e}"
            )
        public_key_pb = crypto_pb.PublicKey()
        public_key_pb.ParseFromString(public_key_pb_bytes)
        return public_key_pb

    async def get_value(self, key: bytes) -> bytes:
        """GET_VALUE
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.GET_VALUE,
            key=key,
        )
        resps = await self._do_dht(dht_req)
        if len(resps) != 1:
            raise ControlFailure(f"should only get one response, resps={resps}")
        try:
            value = resps[0].value
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains `value`: resps={resps}, e={e}"
            )
        return value

    async def search_value(self, key: bytes) -> Tuple[bytes, ...]:
        """SEARCH_VALUE
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.SEARCH_VALUE,
            key=key,
        )
        resps = await self._do_dht(dht_req)
        try:
            values = tuple(resp.value for resp in resps)
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains `value`: resps={resps}, e={e}"
            )
        return values

    async def put_value(self, key: bytes, value: bytes) -> None:
        """PUT_VALUE
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.PUT_VALUE,
            key=key,
            value=value,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.DHT,
            dht=dht_req,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def provide(self, cid: bytes) -> None:
        """PROVIDE
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.PROVIDE,
            cid=cid,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.DHT,
            dht=dht_req,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)


class ConnectionManagerClient:
    client: Client

    def __init__(self, client: Client) -> None:
        self.client = client

    async def tag_peer(self, peer_id: PeerID, tag: str, weight: int) -> None:
        """TAG_PEER
        """
        connmgr_req = p2pd_pb.ConnManagerRequest(
            type=p2pd_pb.ConnManagerRequest.TAG_PEER,
            peer=peer_id.to_bytes(),
            tag=tag,
            weight=weight,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.CONNMANAGER,
            connManager=connmgr_req,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def untag_peer(self, peer_id: PeerID, tag: str) -> None:
        """UNTAG_PEER
        """
        connmgr_req = p2pd_pb.ConnManagerRequest(
            type=p2pd_pb.ConnManagerRequest.UNTAG_PEER,
            peer=peer_id.to_bytes(),
            tag=tag,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.CONNMANAGER,
            connManager=connmgr_req,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def trim(self) -> None:
        """TRIM
        """
        connmgr_req = p2pd_pb.ConnManagerRequest(
            type=p2pd_pb.ConnManagerRequest.TRIM,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.CONNMANAGER,
            connManager=connmgr_req,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)


class PubSubClient:
    client: Client

    def __init__(self, client: Client) -> None:
        self.client = client

    async def get_topics(self) -> Tuple[str, ...]:
        """PUBSUB GET_TOPICS
        """
        pubsub_req = p2pd_pb.PSRequest(
            type=p2pd_pb.PSRequest.GET_TOPICS,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.PUBSUB,
            pubsub=pubsub_req,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

        topics = tuple(resp.pubsub.topics)
        return topics

    async def list_peers(self, topic: str) -> Tuple[PeerID, ...]:
        """PUBSUB LIST_PEERS
        """
        pubsub_req = p2pd_pb.PSRequest(
            type=p2pd_pb.PSRequest.LIST_PEERS,
            topic=topic,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.PUBSUB,
            pubsub=pubsub_req,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

        return tuple(
            PeerID(peer_id_bytes)
            for peer_id_bytes in resp.pubsub.peerIDs
        )

    async def publish(self, topic: str, data: bytes) -> None:
        """PUBSUB PUBLISH
        """
        pubsub_req = p2pd_pb.PSRequest(
            type=p2pd_pb.PSRequest.PUBLISH,
            topic=topic,
            data=data,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.PUBSUB,
            pubsub=pubsub_req,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def subscribe(self, topic: str) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """PUBSUB SUBSCRIBE
        """
        pubsub_req = p2pd_pb.PSRequest(
            type=p2pd_pb.PSRequest.SUBSCRIBE,
            topic=topic,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.PUBSUB,
            pubsub=pubsub_req,
        )
        reader, writer = await self.client.open_connection()
        await write_pbmsg(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        raise_if_failed(resp)

        return reader, writer
