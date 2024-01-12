from eth_utils import (
    ValidationError,
    decode_hex,
)
import pytest

from eth.chains.base import (
    MiningChain,
)
from eth.chains.goerli import (
    GOERLI_GENESIS_HEADER,
)
from eth.consensus.clique import (
    CliqueApplier,
    CliqueConsensusContext,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks.petersburg import (
    PetersburgVM,
)

GOERLI_HEADER_ONE = BlockHeader(
    difficulty=2,
    block_number=1,
    gas_limit=10475521,
    timestamp=1548947453,
    coinbase=decode_hex("0x0000000000000000000000000000000000000000"),
    parent_hash=decode_hex(
        "0xbf7e331f7f7c1dd2e05159666b3bf8bc7a8a3a9eb1d518969eab529dd9b88c1a"
    ),
    uncles_hash=decode_hex(
        "0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347"
    ),
    state_root=decode_hex(
        "0x5d6cded585e73c4e322c30c2f782a336316f17dd85a4863b9d838d2d4b8b3008"
    ),
    transaction_root=decode_hex(
        "0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"
    ),
    receipt_root=decode_hex(
        "0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"
    ),
    bloom=0,
    gas_used=0,
    extra_data=decode_hex(
        "0x506172697479205465636820417574686f7269747900000000000000000000002bbf886181970654ed46e3fae0ded41ee53fec702c47431988a7ae80e6576f3552684f069af80ba11d36327aaf846d470526e4a1c461601b2fd4ebdcdc2b734a01"  # noqa: E501
    ),
    mix_hash=decode_hex(
        "0x0000000000000000000000000000000000000000000000000000000000000000"
    ),
    nonce=decode_hex("0x0000000000000000"),
)

GOERLI_HEADER_TWO = BlockHeader(
    difficulty=2,
    block_number=2,
    gas_limit=10465292,
    timestamp=1548947468,
    coinbase=decode_hex("0x0000000000000000000000000000000000000000"),
    parent_hash=decode_hex(
        "0x8f5bab218b6bb34476f51ca588e9f4553a3a7ce5e13a66c660a5283e97e9a85a"
    ),
    uncles_hash=decode_hex(
        "0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347"
    ),
    state_root=decode_hex(
        "0x5d6cded585e73c4e322c30c2f782a336316f17dd85a4863b9d838d2d4b8b3008"
    ),
    transaction_root=decode_hex(
        "0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"
    ),
    receipt_root=decode_hex(
        "0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"
    ),
    bloom=0,
    gas_used=0,
    extra_data=decode_hex(
        "0x506172697479205465636820417574686f726974790000000000000000000000fdd66d441eff7d4116fe987f0f10812fc68b06cc500ff71c492234b9a7b8b2f45597190d97cd85f6daa45ac9518bef9f715f4bd414504b1a21d8c681654055df00"  # noqa: E501
    ),
    mix_hash=decode_hex(
        "0x0000000000000000000000000000000000000000000000000000000000000000"
    ),
    nonce=decode_hex("0x0000000000000000"),
)


@pytest.fixture
def goerli_chain(base_db):
    vms = (
        (
            0,
            PetersburgVM,
        ),
    )
    clique_vms = CliqueApplier().amend_vm_configuration(vms)

    chain = MiningChain.configure(
        vm_configuration=clique_vms,
        consensus_context_class=CliqueConsensusContext,
        chain_id=5,
    ).from_genesis_header(base_db, GOERLI_GENESIS_HEADER)
    return chain


@pytest.mark.parametrize(
    "headers, valid",
    (
        ((GOERLI_GENESIS_HEADER, GOERLI_HEADER_ONE), True),
        ((GOERLI_GENESIS_HEADER, GOERLI_HEADER_TWO), False),
    ),
)
def test_can_validate_header(goerli_chain, headers, valid):
    if valid:
        goerli_chain.validate_chain_extension(headers)
    else:
        with pytest.raises(ValidationError):
            goerli_chain.validate_chain_extension(headers)
