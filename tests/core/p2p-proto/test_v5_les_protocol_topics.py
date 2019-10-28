from eth.chains.ropsten import ROPSTEN_GENESIS_HEADER

from p2p import discovery

from trinity.protocol.les.proto import LESProtocolV1, LESProtocolV2


def test_get_v5_topic():
    les_topic = discovery.get_v5_topic(LESProtocolV1, ROPSTEN_GENESIS_HEADER.hash)
    assert les_topic == b'LES@41941023680923e0'
    les2_topic = discovery.get_v5_topic(LESProtocolV2, ROPSTEN_GENESIS_HEADER.hash)
    assert les2_topic == b'LES2@41941023680923e0'
