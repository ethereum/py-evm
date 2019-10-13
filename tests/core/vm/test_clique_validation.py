import pytest

from eth_utils import (
    decode_hex,
)

from eth.chains.goerli import (
    GOERLI_GENESIS_HEADER,
)
from eth.consensus.clique import CliqueConsensus

from eth.rlp.headers import BlockHeader

from eth.vm.forks.petersburg import (
    PetersburgVM,
)


GOERLI_HEADER_ONE = BlockHeader(
    difficulty=2,
    block_number=1,
    gas_limit=10475521,
    timestamp=1548947453,
    coinbase=decode_hex('0x0000000000000000000000000000000000000000'),
    parent_hash=decode_hex('0xbf7e331f7f7c1dd2e05159666b3bf8bc7a8a3a9eb1d518969eab529dd9b88c1a'),
    uncles_hash=decode_hex('0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347'),
    state_root=decode_hex('0x5d6cded585e73c4e322c30c2f782a336316f17dd85a4863b9d838d2d4b8b3008'),
    transaction_root=decode_hex('0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421'),  # noqa: E501
    receipt_root=decode_hex('0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421'),
    bloom=0,
    gas_used=0,
    extra_data=decode_hex('0x506172697479205465636820417574686f7269747900000000000000000000002bbf886181970654ed46e3fae0ded41ee53fec702c47431988a7ae80e6576f3552684f069af80ba11d36327aaf846d470526e4a1c461601b2fd4ebdcdc2b734a01'),  # noqa: E501
    mix_hash=decode_hex('0x0000000000000000000000000000000000000000000000000000000000000000'),
    nonce=decode_hex('0x0000000000000000'),
)


@pytest.fixture
def clique(base_db):
    clique = CliqueConsensus(base_db)
    clique._chain_db.persist_header(GOERLI_GENESIS_HEADER)
    return clique


@pytest.mark.parametrize(
    'VM, header, previous_header, valid',
    (
        (PetersburgVM, GOERLI_HEADER_ONE, GOERLI_GENESIS_HEADER, True),
    ),
)
def test_can_validate_header(clique, VM, header, previous_header, valid):
    CliqueVM = VM.configure(
        extra_data_max_bytes=128,
        validate_seal=lambda header: clique.validate_seal(header),
    )
    CliqueVM.validate_header(header, previous_header, check_seal=True)
