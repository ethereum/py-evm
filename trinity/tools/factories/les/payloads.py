try:
    import factory
    from faker import Faker
except ImportError:
    raise ImportError(
        "The p2p.tools.factories module requires the `factory_boy` and `faker` libraries."
    )

import secrets

from eth_utils import to_bytes

from eth.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_DIFFICULTY,
)

from trinity.constants import MAINNET_NETWORK_ID

from trinity.protocol.les.payloads import (
    AnnouncePayload,
    BlockBodiesPayload,
    BlockHeadersPayload,
    ContractCodeRequest,
    ContractCodesPayload,
    GetBlockBodiesPayload,
    GetBlockHeadersPayload,
    GetContractCodesPayload,
    GetProofsPayload,
    GetReceiptsPayload,
    ProofRequest,
    ProofsPayloadV1,
    ProofsPayloadV2,
    ReceiptsPayload,
    StatusPayload,
)
from trinity.protocol.les.proto import LESProtocolV2

from trinity.tools.factories.address import AddressFactory
from trinity.tools.factories.block_body import BlockBodyFactory
from trinity.tools.factories.block_hash import BlockHashFactory
from trinity.tools.factories.common import BlockHeadersQueryFactory
from trinity.tools.factories.headers import BlockHeaderFactory
from trinity.tools.factories.receipts import ReceiptFactory


MAINNET_GENESIS_HASH = to_bytes(hexstr='0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3')  # noqa: E501


faker = Faker()


class StatusPayloadFactory(factory.Factory):
    class Meta:
        model = StatusPayload

    version = LESProtocolV2.version
    network_id = MAINNET_NETWORK_ID
    head_td = GENESIS_DIFFICULTY
    head_hash = MAINNET_GENESIS_HASH
    head_number = GENESIS_BLOCK_NUMBER
    genesis_hash = MAINNET_GENESIS_HASH
    serve_headers = True
    serve_chain_since = 0
    serve_state_since = None
    serve_recent_state = None
    serve_recent_chain = None
    tx_relay = False
    flow_control_bl = None
    flow_control_mcr = None
    flow_control_mrr = None
    announce_type = factory.LazyAttribute(
        lambda o: o.version if o.version >= LESProtocolV2.version else None
    )


class AnnouncePayloadFactory(factory.Factory):
    class Meta:
        model = AnnouncePayload

    head_hash = MAINNET_GENESIS_HASH
    head_number = GENESIS_BLOCK_NUMBER
    head_td = GENESIS_DIFFICULTY
    reorg_depth = 0
    params = ()


class GetBlockHeadersPayloadFactory(factory.Factory):
    class Meta:
        model = GetBlockHeadersPayload

    request_id = factory.Sequence(lambda n: n)
    query = factory.SubFactory(BlockHeadersQueryFactory)


class BlockHeadersPayloadFactory(factory.Factory):
    class Meta:
        model = BlockHeadersPayload

    request_id = factory.Sequence(lambda n: n)
    buffer_value = 0
    headers = factory.LazyFunction(lambda: tuple(BlockHeaderFactory.create_batch(2)))


class GetBlockBodiesPayloadFactory(factory.Factory):
    class Meta:
        model = GetBlockBodiesPayload

    request_id = factory.Sequence(lambda n: n)
    block_hashes = factory.LazyFunction(lambda: tuple(BlockHashFactory.create_batch(2)))


class BlockBodiesPayloadFactory(factory.Factory):
    class Meta:
        model = BlockBodiesPayload

    request_id = factory.Sequence(lambda n: n)
    buffer_value = 0
    bodies = factory.LazyFunction(lambda: tuple(BlockBodyFactory.create_batch(2)))


class GetReceiptsPayloadFactory(factory.Factory):
    class Meta:
        model = GetReceiptsPayload

    request_id = factory.Sequence(lambda n: n)
    block_hashes = factory.LazyFunction(lambda: tuple(BlockHashFactory.create_batch(2)))


class ReceiptsPayloadFactory(factory.Factory):
    class Meta:
        model = ReceiptsPayload

    request_id = factory.Sequence(lambda n: n)
    buffer_value = 0
    receipts = factory.LazyFunction(
        lambda: (tuple(ReceiptFactory.create_batch(2)), tuple(ReceiptFactory.create_batch(3)))
    )


class ProofRequestFactory(factory.Factory):
    class Meta:
        model = ProofRequest

    block_hash = factory.SubFactory(BlockHashFactory)
    storage_key = None
    state_key = factory.SubFactory(AddressFactory)
    from_level = 0


class GetProofsPayloadFactory(factory.Factory):
    class Meta:
        model = GetProofsPayload

    request_id = factory.Sequence(lambda n: n)
    proofs = factory.LazyFunction(
        lambda: tuple(ProofRequestFactory.create_batch(1))
    )


class ProofsPayloadV1Factory(factory.Factory):
    class Meta:
        model = ProofsPayloadV1

    request_id = factory.Sequence(lambda n: n)
    buffer_value = 0
    proofs = factory.LazyFunction(lambda: ((secrets.token_bytes(256),),))


class ContractCodeRequestFactory(factory.Factory):
    class Meta:
        model = ContractCodeRequest

    block_hash = factory.SubFactory(BlockHashFactory)
    account = factory.SubFactory(AddressFactory)


class GetContractCodesPayloadFactory(factory.Factory):
    class Meta:
        model = GetContractCodesPayload

    request_id = factory.Sequence(lambda n: n)
    code_requests = factory.LazyFunction(lambda: tuple(ContractCodeRequestFactory.create_batch(2)))


class ContractCodesPayloadFactory(factory.Factory):
    class Meta:
        model = ContractCodesPayload

    request_id = factory.Sequence(lambda n: n)
    buffer_value = 0
    codes = factory.LazyFunction(lambda: tuple(faker.binary(20) for _ in range(2)))


class ProofsPayloadV2Factory(factory.Factory):
    class Meta:
        model = ProofsPayloadV2

    request_id = factory.Sequence(lambda n: n)
    buffer_value = 0
    proof = factory.LazyFunction(lambda: tuple((secrets.token_bytes(50) for _ in range(2))))
