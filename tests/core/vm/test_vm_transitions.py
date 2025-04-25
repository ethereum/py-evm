import pytest

from eth.chains.base import (
    MiningChain,
)
from eth.chains.mainnet import (
    MAINNET_VMS,
)
from eth.consensus import (
    NoProofConsensus,
)
from eth.db.atomic import (
    AtomicDB,
)

vm_pairs = []
for i in range(1, len(MAINNET_VMS)):
    for j in range(i):
        vm_pairs.append((MAINNET_VMS[j], MAINNET_VMS[i]))


@pytest.mark.parametrize("from_vm, to_vm", vm_pairs)
def test_transitions_from_all_vms_before_the_vm_under_test(from_vm, to_vm):
    chain = MiningChain.configure(
        vm_configuration=[
            (0, from_vm.configure(consensus_class=NoProofConsensus)),
            (1, to_vm.configure(consensus_class=NoProofConsensus)),
        ],
    ).from_genesis(AtomicDB(), {"difficulty": 0})
    chain.mine_block()
