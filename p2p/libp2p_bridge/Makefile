shardingp2p_pb_path = github.com/ethresearch/sharding-p2p-poc/pb
shardingp2p_pb_rpc_path = ${GOPATH}/src/$(shardingp2p_pb_path)/rpc
shardingp2p_pb_msg_path = ${GOPATH}/src/$(shardingp2p_pb_path)/message
shardingp2p_pb_event_path = ${GOPATH}/src/$(shardingp2p_pb_path)/event
rpc_proto_source = $(shardingp2p_pb_rpc_path)/rpc.proto
msg_proto_source = $(shardingp2p_pb_msg_path)/message.proto
event_proto_source = $(shardingp2p_pb_event_path)/event.proto
pb_py_path = github/com/ethresearch/sharding_p2p_poc/pb
rpc_pb_py = rpc_pb2.py rpc_pb2_grpc.py
msg_pb_py = message_pb2.py
event_pb_py = event_pb2.py event_pb2_grpc.py
rpc_pb_py_dest = $(patsubst %,$(pb_py_path)/rpc/%, $(rpc_pb_py))
msg_pb_py_dest = $(patsubst %,$(pb_py_path)/message/%, $(msg_pb_py))
event_pb_py_dest = $(patsubst %,$(pb_py_path)/event/%, $(event_pb_py))

all: $(rpc_pb_py_dest) $(msg_pb_py_dest) $(event_pb_py_dest)

$(rpc_pb_py_dest) $(msg_pb_py_dest) $(event_pb_py_dest): $(rpc_proto_source) $(msg_proto_source)
	python -m grpc_tools.protoc -I${GOPATH}/src -I$(shardingp2p_pb_rpc_path) -I$(shardingp2p_pb_msg_path) --python_out=. --grpc_python_out=. $(rpc_proto_source) $(msg_proto_source) $(event_proto_source)
	mv github.com/ethresearch/sharding_p2p_poc/pb/rpc/*.py github/com/ethresearch/sharding_p2p_poc/pb/rpc/
	mv github.com/ethresearch/sharding_p2p_poc/pb/event/*.py github/com/ethresearch/sharding_p2p_poc/pb/event/
	rm -rf github.com

clean:
	rm -f $(rpc_pb_py_dest) $(msg_pb_py_dest) $(event_pb_py_dest)

