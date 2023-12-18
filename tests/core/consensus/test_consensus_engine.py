from eth_utils import (
    ValidationError,
)
import pytest

from eth.abc import (
    ConsensusAPI,
)
from eth.chains.base import (
    MiningChain,
)
from eth.consensus import (
    ConsensusContext,
)
from eth.tools.builder.chain import (
    genesis,
)
from eth.vm.forks.istanbul import (
    IstanbulVM,
)

CONSENSUS_DATA_LENGH = 9

WHITELISTED_ROOT = b"root"

ZERO_BYTE = b"\x00"


class WhitelistConsensus(ConsensusAPI):
    """
    A pseudo consensus engine for testing.
    Each accepted block puts another block on a whitelist.
    """

    def __init__(self, context: ConsensusContext) -> None:
        self.base_db = context.db

    def _get_consensus_data(self, consensus_data):
        if len(consensus_data) != CONSENSUS_DATA_LENGH:
            raise ValidationError(
                f"The `extra_data` field must be of length {CONSENSUS_DATA_LENGH}"
                f"but was {len(consensus_data)}"
            )

        return consensus_data[:4], consensus_data[5:]

    def validate_seal(self, header):
        current, following = self._get_consensus_data(header.extra_data)

        if current == WHITELISTED_ROOT or current in self.base_db:
            self.base_db[following] = ZERO_BYTE
        else:
            raise ValidationError(f"Block isn't on whitelist: {current}")

    def validate_seal_extension(self, header, parents):
        pass

    @classmethod
    def get_fee_recipient(cls, header):
        return header.coinbase


def test_stateful_consensus_isnt_shared_across_chain_instances():
    class ChainClass(MiningChain):
        vm_configuration = (
            (0, IstanbulVM.configure(consensus_class=WhitelistConsensus)),
        )

    chain = genesis(ChainClass)

    chain.mine_block(extra_data=b"root-1000")
    chain.mine_block(extra_data=b"1000-1001")
    # we could even mine the same block twice
    chain.mine_block(extra_data=b"1000-1001")

    # But we can not jump ahead
    with pytest.raises(ValidationError, match="Block isn't on whitelist"):
        chain.mine_block(extra_data=b"1002-1003")

    # A different chain but same consensus engine class
    second_chain = genesis(ChainClass)

    # Should maintain its independent whitelist
    with pytest.raises(ValidationError, match="Block isn't on whitelist"):
        second_chain.mine_block(extra_data=b"1000-1001")

    second_chain.mine_block(extra_data=b"root-2000")

    # And the second chain's whitelist should also not interfere with the first one's
    with pytest.raises(ValidationError, match="Block isn't on whitelist"):
        chain.mine_block(extra_data=b"2000-2001")
