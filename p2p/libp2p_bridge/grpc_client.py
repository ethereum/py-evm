from p2p.libp2p_bridge.constants import (
    UNKNOWN_PID,
    UNKNOWN_TOPIC,
)

import p2p.libp2p_bridge.pb.message.message_pb2 as message_pb2
import p2p.libp2p_bridge.pb.rpc.rpc_pb2 as rpc_pb2


class RPCFailure(Exception):
    pass


def throw_if_not_success(response, request):
    if response.response.status != rpc_pb2.Response.SUCCESS:
        raise RPCFailure(
            "response={}, request={}".format(
                response,
                request,
            )
        )


class GRPCClient:
    stub = None

    def __init__(self, stub):
        self.stub = stub

    #
    # RPC for CLI usage
    #

    def add_peer(self, ip, port, seed):
        addpeer_req = rpc_pb2.RPCAddPeerRequest(
            ip=ip,
            port=port,
            seed=seed,
        )
        response = self.stub.AddPeer(addpeer_req)
        throw_if_not_success(response, addpeer_req)
        return response.response.message

    def subscribe_shards(self, shard_ids):
        subscribe_shards_req = rpc_pb2.RPCSubscribeShardRequest(shardIDs=shard_ids)
        response = self.stub.SubscribeShard(subscribe_shards_req)
        throw_if_not_success(response, subscribe_shards_req)
        return response.response.message

    def unsubscribe_shards(self, shard_ids):
        unsubscribe_shards_req = rpc_pb2.RPCUnsubscribeShardRequest(shardIDs=shard_ids)
        response = self.stub.UnsubscribeShard(unsubscribe_shards_req)
        throw_if_not_success(response, unsubscribe_shards_req)
        return response.response.message

    def get_subscribed_shards(self):
        getsubshard_req = rpc_pb2.RPCGetSubscribedShardRequest()
        response = self.stub.GetSubscribedShard(getsubshard_req)
        throw_if_not_success(response, getsubshard_req)
        return response.shardIDs

    def broadcast_collation(self, shard_id, num_collations, collation_size, frequency):
        broadcastcollation_req = rpc_pb2.RPCBroadcastCollationRequest(
            shardID=shard_id,
            number=num_collations,
            size=collation_size,
            period=frequency,
        )
        response = self.stub.BroadcastCollation(broadcastcollation_req)
        throw_if_not_success(response, broadcastcollation_req)
        return response.response.message

    def send_collation(self, shard_id, period, blobs):
        collation_msg = message_pb2.Collation(
            shardID=shard_id,
            period=period,
            blobs=blobs,
        )
        sendcollation_req = rpc_pb2.RPCSendCollationRequest(
            collation=collation_msg,
        )
        response = self.stub.SendCollation(sendcollation_req)
        throw_if_not_success(response, sendcollation_req)
        return response.response.message

    def stop_server(self):
        stopserver_req = rpc_pb2.RPCStopServerRequest()
        response = self.stub.StopServer(stopserver_req)
        throw_if_not_success(response, stopserver_req)
        return response.response.message

    #
    # RPC for data transmission
    #

    def send(self, peer_id, msg_type, data):
        req = rpc_pb2.SendRequest(
            peerID=peer_id,
            topic=UNKNOWN_TOPIC,
            msgType=msg_type.value,
            data=data,
        )
        response = self.stub.Send(req)
        throw_if_not_success(response, req)
        return response.data

    def broadcast(self, topic, msg_type, data):
        req = rpc_pb2.SendRequest(
            peerID=UNKNOWN_PID,
            topic=topic,
            msgType=msg_type.value,
            data=data,
        )
        response = self.stub.Send(req)
        throw_if_not_success(response, req)
        return response.data
