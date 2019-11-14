import pytest

from trinity._utils.assertions import assert_type_equality
from trinity.protocol.les.commands import (
    Announce,
    BlockBodies,
    BlockHeaders,
    ContractCodes,
    GetBlockBodies,
    GetBlockHeaders,
    GetContractCodes,
    GetProofsV1,
    GetProofsV2,
    GetReceipts,
    ProofsV1,
    ProofsV2,
    Receipts,
    StatusV1,
    StatusV2,
)

from trinity.tools.factories.les import (
    AnnouncePayloadFactory,
    BlockBodiesPayloadFactory,
    BlockHeadersPayloadFactory,
    ContractCodesPayloadFactory,
    GetBlockBodiesPayloadFactory,
    GetBlockHeadersPayloadFactory,
    GetContractCodesPayloadFactory,
    GetProofsPayloadFactory,
    GetReceiptsPayloadFactory,
    ProofRequestFactory,
    ProofsPayloadV1Factory,
    ProofsPayloadV2Factory,
    ReceiptsPayloadFactory,
    StatusPayloadFactory,
)


@pytest.mark.parametrize(
    'command_type,payload',
    (
        (StatusV1, StatusPayloadFactory(version=1)),
        (StatusV1, StatusPayloadFactory(version=1, tx_relay=True)),
        (StatusV1, StatusPayloadFactory(version=1, serve_headers=True)),
        (Announce, AnnouncePayloadFactory()),
        (GetBlockHeaders, GetBlockHeadersPayloadFactory()),
        (GetBlockHeaders, GetBlockHeadersPayloadFactory(query__block_number_or_hash=0)),
        (BlockHeaders, BlockHeadersPayloadFactory()),
        (GetBlockBodies, GetBlockBodiesPayloadFactory()),
        (BlockBodies, BlockBodiesPayloadFactory()),
        (GetReceipts, GetReceiptsPayloadFactory()),
        (Receipts, ReceiptsPayloadFactory()),
        (GetProofsV1, GetProofsPayloadFactory()),
        (GetProofsV1, GetProofsPayloadFactory(proofs=(ProofRequestFactory(storage_key=b'\x01'),))),
        (ProofsV1, ProofsPayloadV1Factory()),
        (GetContractCodes, GetContractCodesPayloadFactory()),
        (ContractCodes, ContractCodesPayloadFactory()),
        (GetProofsV2, GetProofsPayloadFactory()),  # payload same as v1
        (GetProofsV2, GetProofsPayloadFactory(proofs=(ProofRequestFactory(storage_key=b'\x01'),))),
        (ProofsV2, ProofsPayloadV2Factory()),
        (StatusV2, StatusPayloadFactory(version=2, announce_type=2)),
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
