from concurrent import futures
import logging
import time

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

import p2p.libp2p_bridge.github.com.ethresearch.sharding_p2p_poc.pb.event.event_pb2 as event_pb2
import p2p.libp2p_bridge.github.com.ethresearch.sharding_p2p_poc.pb.event.event_pb2_grpc as event_pb2_grpc


def make_response(status):
    response = event_pb2.Response()
    if status:
        response.status = event_pb2.Response.SUCCESS
    else:
        response.status = event_pb2.Response.FAILURE
    return response


def handle_new_collation(collation):
    return bytes(True)


def handle_collation_request(collation_request):
    c = Collation(collation_request.shard_id, collation_request.period, b"fake")
    return c.to_bytes()


type_msg_map = {
    MsgType.Collation: (Collation, handle_new_collation),
    MsgType.CollationRequest: (CollationRequest, handle_collation_request),
}


def dispatch(msg_type, data_bytes):
    if msg_type not in type_msg_map:
        return b""
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

    server = None
    logger = logging.getLogger('p2p.libp2p_bridge.grpc_server')

    def run(self):
        self.server = grpc.server(futures.ThreadPoolExecutor())
        event_pb2_grpc.add_EventServicer_to_server(
            EventServicer(),
            self.server,
        )
        listen_addr = '{}:{}'.format(RPC_SERVER_LISTEN_IP, RPC_SERVER_PORT)
        self.server.add_insecure_port(listen_addr)
        self.server.start()
        self.logger.info("Server started")
        try:
            while True:
                time.sleep(86400)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.logger.exception("uncaught exception: %s", e)
        finally:
            self.server.stop(0)


def run_grpc_server():
    # TODO: leave `max_workers=None` in ThreadPoolExecutor,
    #       letting it set as `os.cpu_count() * 5`
    grpc_server = GRPCServer()
    grpc_server.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    run_grpc_server()
