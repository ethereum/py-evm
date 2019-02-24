import asyncio
import binascii
import inspect
import logging
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
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
    read_pbmsg_safe,
    serialize,
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
    proto_codes = set([
        proto.code
        for proto in maddr.protocols()
    ])
    supported_proto_codes = set(_supported_conn_protocols)
    proto_cand = proto_codes.intersection(supported_proto_codes)
    if len(proto_cand) != 1:
        supported_protos = [
            protocols.protocol_with_code(proto)
            for proto in supported_proto_codes
        ]
        raise ValueError(
            "connection protocol should be only one protocol out of {}, maddr={}".format(
                supported_protos,
                maddr,
            )
        )
    return tuple(proto_cand)[0]


class Client:
    control_maddr: Multiaddr
    listen_maddr: Multiaddr
    listener: Optional[asyncio.AbstractServer] = None
    handlers: Dict[str, StreamHandler]

    logger = logging.getLogger('p2pclient.Client')

    def __init__(
            self,
            _control_maddr: Multiaddr = None,
            _listen_maddr: Multiaddr = None) -> None:
        if _control_maddr is None:
            _control_maddr = Multiaddr(config.control_maddr_str)
        if _listen_maddr is None:
            _listen_maddr = Multiaddr(config.listen_maddr_str)
        self.control_maddr = _control_maddr
        self.listen_maddr = _listen_maddr
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

    async def _write_pb(self, writer: asyncio.StreamWriter, data_pb) -> None:
        data_bytes = serialize(data_pb)
        writer.write(data_bytes)
        await writer.drain()

    async def listen(self) -> None:
        if self.listener is not None:
            raise ControlFailure("Listener is already listening")
        # TODO: `start_unix_server` finishes right after awaited, without more coroutine spawn
        #       Then what is serving for the incoming requests?
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
                "protocol not supported: protocol={}".format(
                    protocols.protocol_with_code(proto_code)
                )
            )

    async def close(self) -> None:
        self.listener.close()  # type: ignore
        await self.listener.wait_closed()  # type: ignore
        self.listener = None

    async def open_connection(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        proto_code = parse_conn_protocol(self.control_maddr)
        if proto_code == protocols.P_UNIX:
            control_path = self.control_maddr.value_for_protocol(protocols.P_UNIX)
            return await asyncio.open_unix_connection(control_path)
        elif proto_code == protocols.P_IP4:
            host = self.control_maddr.value_for_protocol(protocols.P_IP4)
            port = int(self.control_maddr.value_for_protocol(protocols.P_TCP))
            return await asyncio.open_connection(host=host, port=port)
        else:
            raise ValueError(
                "protocol not supported: protocol={}".format(
                    protocols.protocol_with_code(proto_code)
                )
            )

    async def identify(self) -> Tuple[PeerID, List[Multiaddr]]:
        reader, writer = await self.open_connection()
        req = p2pd_pb.Request(type=p2pd_pb.Request.IDENTIFY)  # type: ignore
        await self._write_pb(writer, req)

        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)
        peer_id_bytes = resp.identify.id
        maddrs_bytes = resp.identify.addrs

        maddrs = []
        for maddr_bytes in maddrs_bytes:
            maddr = Multiaddr(binascii.hexlify(maddr_bytes))
            maddrs.append(maddr)
        peer_id = PeerID(peer_id_bytes)

        return peer_id, maddrs

    async def connect(self, peer_id: PeerID, maddrs: List[Multiaddr]) -> None:
        reader, writer = await self.open_connection()

        maddrs_bytes = [binascii.unhexlify(i.to_bytes()) for i in maddrs]
        connect_req = p2pd_pb.ConnectRequest(
            peer=peer_id.to_bytes(),
            addrs=maddrs_bytes,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.CONNECT,  # type: ignore
            connect=connect_req,
        )
        await self._write_pb(writer, req)

        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def list_peers(self) -> List[PeerInfo]:
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.LIST_PEERS,  # type: ignore
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

        pinfos = [PeerInfo.from_pb(pinfo) for pinfo in resp.peers]  # type: ignore
        return pinfos

    async def disconnect(self, peer_id: PeerID) -> None:
        disconnect_req = p2pd_pb.DisconnectRequest(
            peer=peer_id.to_bytes(),
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.DISCONNECT,  # type: ignore
            disconnect=disconnect_req,
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def stream_open(
            self,
            peer_id: PeerID,
            protocols: List[str]) -> Tuple[StreamInfo, asyncio.StreamReader, asyncio.StreamWriter]:
        reader, writer = await self.open_connection()

        stream_open_req = p2pd_pb.StreamOpenRequest(
            peer=peer_id.to_bytes(),
            proto=protocols,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.STREAM_OPEN,  # type: ignore
            streamOpen=stream_open_req,
        )
        await self._write_pb(writer, req)

        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        raise_if_failed(resp)

        pb_stream_info = resp.streamInfo
        stream_info = StreamInfo.from_pb(pb_stream_info)

        return stream_info, reader, writer

    async def stream_handler(self, proto: str, handler_cb: StreamHandler) -> None:
        reader, writer = await self.open_connection()

        # FIXME: should introduce type annotation to solve this elegantly
        handler_sig = inspect.signature(handler_cb).parameters
        if len(handler_sig) != 3:
            raise ControlFailure(
                "signature of the callback handler {} is wrong: {}".format(
                    handler_cb,
                    handler_sig,
                )
            )
        listen_path_maddr_bytes = binascii.unhexlify(self.listen_maddr.to_bytes())
        stream_handler_req = p2pd_pb.StreamHandlerRequest(
            addr=listen_path_maddr_bytes,
            proto=[proto],
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.STREAM_HANDLER,  # type: ignore
            streamHandler=stream_handler_req,
        )
        await self._write_pb(writer, req)

        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

        # if success, add the handler to the dict
        self.handlers[proto] = handler_cb

    # DHT operations

    # TODO: type hints for `p2pd_pb.DHTRequest` and `p2pd_pb.DHTResponse`
    async def _do_dht(self, dht_req):
        reader, writer = await self.open_connection()
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.DHT,
            dht=dht_req,
        )
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        raise_if_failed(resp)

        try:
            dht_resp = resp.dht
        except AttributeError as e:
            raise ControlFailure(f"resp should contains dht: resp={resp}, e={e}")

        if dht_resp.type == dht_resp.VALUE:  # type: ignore
            return [dht_resp]

        if dht_resp.type != dht_resp.BEGIN:  # type: ignore
            raise ControlFailure(f"Type should be BEGIN instead of {dht_resp.type}")
        # BEGIN/END stream
        resps = []
        while True:
            dht_resp = p2pd_pb.DHTResponse()
            await read_pbmsg_safe(reader, dht_resp)
            if dht_resp.type == dht_resp.END:  # type: ignore
                break
            resps.append(dht_resp)
        writer.close()
        return resps

    async def find_peer(self, peer_id: PeerID) -> PeerInfo:
        """FIND_PEER
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.FIND_PEER,  # type: ignore
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

    async def find_peers_connected_to_peer(self, peer_id: PeerID) -> List[PeerInfo]:
        """FIND_PEERS_CONNECTED_TO_PEER
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.FIND_PEERS_CONNECTED_TO_PEER,  # type: ignore
            peer=peer_id.to_bytes(),
        )
        resps = await self._do_dht(dht_req)

        # TODO: maybe change these checks to a validator pattern
        try:
            pinfos = [PeerInfo.from_pb(dht_resp.peer) for dht_resp in resps]
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains peer info: resps={resps}, e={e}"
            )
        return pinfos

    async def find_providers(self, content_id_bytes: bytes, count: int) -> List[PeerInfo]:
        """FIND_PROVIDERS
        """
        # TODO: should have another class ContendID
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.FIND_PROVIDERS,  # type: ignore
            cid=content_id_bytes,
            count=count,
        )
        resps = await self._do_dht(dht_req)
        # TODO: maybe change these checks to a validator pattern
        try:
            pinfos = [PeerInfo.from_pb(dht_resp.peer) for dht_resp in resps]
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains peer info: resps={resps}, e={e}"
            )
        return pinfos

    async def get_closest_peers(self, key: bytes) -> List[PeerID]:
        """GET_CLOSEST_PEERS
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.GET_CLOSEST_PEERS,  # type: ignore
            key=key,
        )
        resps = await self._do_dht(dht_req)
        try:
            peer_ids = [PeerID(dht_resp.value) for dht_resp in resps]
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains `value`: resps={resps}, e={e}"
            )
        return peer_ids

    # TODO: typing for `crypto_pb.PublicKey`
    async def get_public_key(self, peer_id: PeerID) -> Any:
        """GET_PUBLIC_KEY
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.GET_PUBLIC_KEY,  # type: ignore
            peer=peer_id.to_bytes(),
        )
        resps = await self._do_dht(dht_req)
        if len(resps) != 1:
            raise ControlFailure(f"should only get one response, resps={resps}")
        try:
            # TODO: parse the public key with another class?
            public_key_pb_bytes = resps[0].value  # type: ignore
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
            type=p2pd_pb.DHTRequest.GET_VALUE,  # type: ignore
            key=key,
        )
        resps = await self._do_dht(dht_req)
        if len(resps) != 1:
            raise ControlFailure(f"should only get one response, resps={resps}")
        try:
            # TODO: parse the public key with another class?
            value = resps[0].value
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains `value`: resps={resps}, e={e}"
            )
        return value

    async def search_value(self, key: bytes) -> List[bytes]:
        """SEARCH_VALUE
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.SEARCH_VALUE,  # type: ignore
            key=key,
        )
        resps = await self._do_dht(dht_req)
        try:
            # TODO: parse the public key with another class?
            values = [resp.value for resp in resps]
        except AttributeError as e:
            raise ControlFailure(
                f"dht_resp should contains `value`: resps={resps}, e={e}"
            )
        return values

    async def put_value(self, key: bytes, value: bytes) -> None:
        """PUT_VALUE
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.PUT_VALUE,  # type: ignore
            key=key,
            value=value,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.DHT,  # type: ignore
            dht=dht_req,
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def provide(self, cid: bytes) -> None:
        """PROVIDE
        """
        dht_req = p2pd_pb.DHTRequest(
            type=p2pd_pb.DHTRequest.PROVIDE,  # type: ignore
            cid=cid,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.DHT,  # type: ignore
            dht=dht_req,
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    # connection manager

    async def tag_peer(self, peer_id: PeerID, tag: str, weight: int) -> None:
        """TAG_PEER
        """
        connmgr_req = p2pd_pb.ConnManagerRequest(
            type=p2pd_pb.ConnManagerRequest.TAG_PEER,  # type: ignore
            peer=peer_id.to_bytes(),
            tag=tag,
            weight=weight,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.CONNMANAGER,  # type: ignore
            connManager=connmgr_req,
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def untag_peer(self, peer_id: PeerID, tag: str) -> None:
        """UNTAG_PEER
        """
        connmgr_req = p2pd_pb.ConnManagerRequest(
            type=p2pd_pb.ConnManagerRequest.UNTAG_PEER,  # type: ignore
            peer=peer_id.to_bytes(),
            tag=tag,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.CONNMANAGER,  # type: ignore
            connManager=connmgr_req,
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def trim(self) -> None:
        """TRIM
        """
        connmgr_req = p2pd_pb.ConnManagerRequest(
            type=p2pd_pb.ConnManagerRequest.TRIM,  # type: ignore
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.CONNMANAGER,  # type: ignore
            connManager=connmgr_req,
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    # PubSub

    async def get_topics(self) -> List[str]:
        """PUBSUB GET_TOPICS
        """
        pubsub_req = p2pd_pb.PSRequest(
            type=p2pd_pb.PSRequest.GET_TOPICS,  # type: ignore
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.PUBSUB,  # type: ignore
            pubsub=pubsub_req,
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

        return resp.pubsub.topics  # type: ignore

    # FIXME: name conflicts: `list_topic_peers` is originally `list_peers` in pubsub
    async def list_topic_peers(self, topic: str) -> List[PeerID]:
        """PUBSUB LIST_PEERS
        """
        pubsub_req = p2pd_pb.PSRequest(
            type=p2pd_pb.PSRequest.LIST_PEERS,  # type: ignore
            topic=topic,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.PUBSUB,  # type: ignore
            pubsub=pubsub_req,
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

        peers = [PeerID(peer_id_bytes) for peer_id_bytes in resp.pubsub.peerIDs]  # type: ignore
        return peers

    async def publish(self, topic: str, data: bytes) -> None:
        """PUBSUB PUBLISH
        """
        pubsub_req = p2pd_pb.PSRequest(
            type=p2pd_pb.PSRequest.PUBLISH,  # type: ignore
            topic=topic,
            data=data,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.PUBSUB,  # type: ignore
            pubsub=pubsub_req,
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        writer.close()
        raise_if_failed(resp)

    async def subscribe(self, topic: str) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """PUBSUB SUBSCRIBE
        """
        pubsub_req = p2pd_pb.PSRequest(
            type=p2pd_pb.PSRequest.SUBSCRIBE,  # type: ignore
            topic=topic,
        )
        req = p2pd_pb.Request(
            type=p2pd_pb.Request.PUBSUB,  # type: ignore
            pubsub=pubsub_req,
        )
        reader, writer = await self.open_connection()
        await self._write_pb(writer, req)
        resp = p2pd_pb.Response()
        await read_pbmsg_safe(reader, resp)
        raise_if_failed(resp)

        return reader, writer
