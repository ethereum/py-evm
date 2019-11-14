import secrets

import pytest

from trinity._utils.assertions import assert_type_equality
from trinity.protocol.eth.commands import (
    BlockBodies,
    BlockHeaders,
    GetBlockBodies,
    GetBlockHeaders,
    GetNodeData,
    GetReceipts,
    NewBlock,
    NewBlockHashes,
    NodeData,
    Receipts,
    Status,
    Transactions,
)

from trinity.tools.factories import (
    BaseTransactionFieldsFactory,
    BlockBodyFactory,
    BlockHashFactory,
    BlockHeaderFactory,
    ReceiptFactory,
)
from trinity.tools.factories.common import (
    BlockHeadersQueryFactory,
)
from trinity.tools.factories.eth import (
    NewBlockHashFactory,
    NewBlockPayloadFactory,
    StatusPayloadFactory,
)


@pytest.mark.parametrize(
    'command_type,payload',
    (
        (Status, StatusPayloadFactory()),
        (NewBlockHashes, tuple(NewBlockHashFactory.create_batch(2))),
        (Transactions, tuple(BaseTransactionFieldsFactory.create_batch(2))),
        (GetBlockHeaders, BlockHeadersQueryFactory()),
        (GetBlockHeaders, BlockHeadersQueryFactory(block_number_or_hash=BlockHashFactory())),
        (BlockHeaders, tuple(BlockHeaderFactory.create_batch(2))),
        (GetBlockBodies, tuple(BlockHashFactory.create_batch(2))),
        (BlockBodies, tuple(BlockBodyFactory.create_batch(2))),
        (NewBlock, NewBlockPayloadFactory()),
        (GetNodeData, tuple(BlockHashFactory.create_batch(2))),
        (NodeData, (secrets.token_bytes(10), secrets.token_bytes(100))),
        (GetReceipts, tuple(BlockHashFactory.create_batch(2))),
        (Receipts, (tuple(ReceiptFactory.create_batch(2)), tuple(ReceiptFactory.create_batch(3)))),
    ),
)
@pytest.mark.parametrize(
    'snappy_support',
    (True, False),
)
def test_les_protocol_command_round_trips(command_type, payload, snappy_support):
    cmd = command_type(payload)
    message = cmd.encode(command_type.protocol_command_id, snappy_support=snappy_support)
    assert message.command_id == command_type.protocol_command_id
    result = command_type.decode(message, snappy_support=snappy_support)
    assert isinstance(result, command_type)
    assert result.payload == payload
    assert_type_equality(result.payload, payload)
