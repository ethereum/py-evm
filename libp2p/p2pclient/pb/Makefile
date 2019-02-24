p2pd_path = ${GOPATH}/src/github.com/libp2p/go-libp2p-daemon
p2pd_pb_path = $(p2pd_path)/pb
p2pd_pbs = $(shell find $(p2pd_pb_path) -name *.proto)
p2p_crypto_pb_path = ${GOPATH}/src/github.com/libp2p/go-libp2p-crypto/pb
p2p_crypto_pbs = $(shell find $(p2p_crypto_pb_path) -name *.proto)

all: p2pd_pb_pys p2p_crypto_pys

p2pd_pb_pys: $(p2pd_pbs)
	protoc -I$(p2pd_pb_path) $(p2pd_pbs) --python_out=.

p2p_crypto_pys: $(p2p_crypto_pbs)
	protoc -I$(p2p_crypto_pb_path) $(p2p_crypto_pbs) --python_out=.

clean:
	rm *pb2.py

