import time
from concurrent import futures
import logging

import grpc

from p2p.libp2p_bridge.config import (
    RPC_SERVER_LISTEN_IP,
    RPC_SERVER_PORT,
)
from p2p.libp2p_bridge.message import (
    Collation,
    CollationRequest,
    MsgType,
)

import p2p.libp2p_bridge.pb.event.event_pb2 as event_pb2
import p2p.libp2p_bridge.pb.event.event_pb2_grpc as event_pb2_grpc


def make_response(status):
    response = event_pb2.Response()
    if status:
        response.status = event_pb2.Response.SUCCESS
    else:
        response.status = event_pb2.Response.FAILURE
    return response


def handle_new_collation(collation):
    # TODO: things should be done when new collation arrives should be added here
    return bytes(True)


def handle_collation_request(collation_request):
    # TODO: things should be done when someone request a collation should be added here
    c = Collation(collation_request.shard_id, collation_request.period, b"fake")
    return c.to_bytes()


type_msg_map = {
    MsgType.Collation: (Collation, handle_new_collation),
    MsgType.CollationRequest: (CollationRequest, handle_collation_request),
}


class MsgTypeNotFound(Exception):
    pass


def dispatch(msg_type, data_bytes):
    if msg_type not in type_msg_map:
        raise MsgTypeNotFound("message type: {} is not in type_msg_map".format(msg_type))
    msg_cls, handler = type_msg_map[msg_type]
    deserialized_msg = msg_cls.from_bytes(data_bytes)
    return handler(deserialized_msg)


class EventServicer(event_pb2_grpc.EventServicer):

    logger = logging.getLogger('p2p.libp2p_bridge.event_servicer')

    def Receive(self, request, context):
        response = make_response(True)  # Request succeeded
        ret_bytes = dispatch(MsgType(request.msgType), request.data)
        receive_response = event_pb2.ReceiveResponse(
            response=response,
            data=ret_bytes,
        )
        self.logger.info("Receive: request=%s, response=%s", request, receive_response)
        return receive_response


class GRPCServer:

    logger = logging.getLogger('p2p.libp2p_bridge.grpc_server')
    server = None

    def __init__(self):
        # TODO: leave `max_workers=None` in ThreadPoolExecutor,
        #       letting it set as `os.cpu_count() * 5`
        self.server = grpc.server(futures.ThreadPoolExecutor())

    def start(self, listen_addr):
        event_pb2_grpc.add_EventServicer_to_server(
            EventServicer(),
            self.server,
        )
        self.server.add_insecure_port(listen_addr)
        self.logger.info("grpc_server started")
        self.server.start()

    def stop(self):
        self.server.stop(0)

    def run(self, listen_addr):
        self.start(listen_addr)
        try:
            while True:
                time.sleep(86400)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.logger.exception("uncaught exception: %s", e)
        finally:
            self.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    listen_addr = '{}:{}'.format(RPC_SERVER_LISTEN_IP, RPC_SERVER_PORT)
    grpc_server = GRPCServer()
    grpc_server.run(listen_addr)
