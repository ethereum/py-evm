from typing import (
    Type,
    Union,
)

from p2p.protocol import BaseProtocol

from .commands import (
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


class BaseLESProtocol(BaseProtocol):
    name = 'les'
    status_command_type: Union[Type[StatusV1], Type[StatusV2]]
    get_proofs_command_type: Union[Type[GetProofsV1], Type[GetProofsV2]]


class LESProtocolV1(BaseLESProtocol):
    version = 1
    commands = (
        StatusV1,
        Announce,
        BlockHeaders, GetBlockHeaders,
        BlockBodies, GetBlockBodies,
        Receipts, GetReceipts,
        ProofsV1, GetProofsV1,
        ContractCodes, GetContractCodes,
    )
    command_length = 15

    status_command_type = StatusV1
    get_proofs_command_type = GetProofsV1


class LESProtocolV2(BaseLESProtocol):
    version = 2
    commands = (
        StatusV2,
        Announce,
        BlockHeaders, GetBlockHeaders,
        BlockBodies, GetBlockBodies,
        Receipts, GetReceipts,
        ProofsV2, GetProofsV2,
        ContractCodes, GetContractCodes,
    )
    command_length = 21

    status_command_type = StatusV2
    get_proofs_command_type = GetProofsV2
