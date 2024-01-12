from eth_keys import (
    keys,
)
from eth_typing import (
    Address,
)
from eth_utils import (
    decode_hex,
)
import pytest

from eth.chains.goerli import (
    GOERLI_GENESIS_HEADER,
)
from eth.consensus.clique._utils import (
    get_block_signer,
    get_signers_at_checkpoint,
    sign_block_header,
)
from eth.consensus.clique.constants import (
    SIGNATURE_LENGTH,
    VANITY_LENGTH,
)
from eth.rlp.headers import (
    BlockHeader,
)

ALICE_PK = keys.PrivateKey(
    decode_hex("0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8")
)

ALICE = Address(ALICE_PK.public_key.to_canonical_address())


BOB_PK = keys.PrivateKey(
    decode_hex("0x15a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8")
)

BOB = Address(BOB_PK.public_key.to_canonical_address())


GOERLI_GENESIS_ALLOWED_SIGNER = decode_hex("0xe0a2bd4258d2768837baa26a28fe71dc079f84c7")

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


GOERLI_HEADER_5288_VOTE_IN = BlockHeader(
    difficulty=1,
    block_number=5288,
    gas_limit=8000000,
    timestamp=1549029298,
    # The signer we vote for
    coinbase=decode_hex("0xa8e8f14732658e4b51e8711931053a8a69baf2b1"),
    parent_hash=decode_hex(
        "0xd785b7ab9906d8dcf8ff76edeca0b17aa8b24e7ee099712213c3cf073cdf9eec"
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
        "0x506172697479205465636820417574686f726974790000000000000000000000540dd3d15669fa6158287d898f6a7b47091d25251ace9581ad593d6008e272201bcf1cca1e60d826336b3622b3a5638d92a0e156df97c49051657ecd54e62af801"  # noqa: E501
    ),
    mix_hash=decode_hex(
        "0x0000000000000000000000000000000000000000000000000000000000000000"
    ),
    # Vote in favor
    nonce=decode_hex("0xffffffffffffffff"),
)

# This is the first block that votes in another signer. It also means that the
# list of signers *at* this block height is already counted with this new signers
# (so not starting at 5281)
GOERLI_HEADER_5280_VOTE_IN = BlockHeader(
    difficulty=2,
    block_number=5280,
    gas_limit=8000000,
    timestamp=1549026638,
    # The signer we vote for
    coinbase=decode_hex("0x000000568b9b5a365eaa767d42e74ed88915c204"),
    parent_hash=decode_hex(
        "0x876bc08d585a543d3b16de98f333430520fded5cbc44791d97bfc9ab7ae95d0b"
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
        "0x506172697479205465636820417574686f7269747900000000000000000000007cab59e95e66578de7f4d1f662b56ee205d94ea2cb81afa121b684de82305d806e5c3cd2066afd48e236d50bba55ae3bb4fa60b4f1d6f93d62677e52923fbf3800"  # noqa: E501
    ),
    mix_hash=decode_hex(
        "0x0000000000000000000000000000000000000000000000000000000000000000"
    ),
    # Vote in favor
    nonce=decode_hex("0xffffffffffffffff"),
)

UNSIGNED_HEADER = GOERLI_HEADER_ONE.copy(
    extra_data=VANITY_LENGTH * b"0" + SIGNATURE_LENGTH * b"0"
)


@pytest.mark.parametrize(
    "header, expected_signer",
    (
        (GOERLI_HEADER_ONE, GOERLI_GENESIS_ALLOWED_SIGNER),
        (GOERLI_HEADER_TWO, GOERLI_GENESIS_ALLOWED_SIGNER),
        (GOERLI_HEADER_5288_VOTE_IN, GOERLI_GENESIS_ALLOWED_SIGNER),
    ),
)
def test_get_signer(header, expected_signer):
    signer = get_block_signer(header)
    assert signer == expected_signer


@pytest.mark.parametrize(
    "header, signer, expected_signers",
    (
        # We included the expected signers here to prove that signing a header does not
        # accidentially erase the list of signers at checkpoints
        (
            GOERLI_GENESIS_HEADER,
            ALICE_PK,
            (GOERLI_GENESIS_ALLOWED_SIGNER,),
        ),
        (
            GOERLI_HEADER_ONE,
            BOB_PK,
            (),
        ),
        (
            UNSIGNED_HEADER,
            BOB_PK,
            (),
        ),
    ),
)
def test_can_sign_header(header, signer, expected_signers):
    signed_header = sign_block_header(header, signer)
    assert get_block_signer(signed_header) == signer.public_key.to_canonical_address()
    assert get_signers_at_checkpoint(signed_header) == expected_signers


def test_get_allowed_signers():
    signers = get_signers_at_checkpoint(GOERLI_GENESIS_HEADER)
    assert signers == (GOERLI_GENESIS_ALLOWED_SIGNER,)
