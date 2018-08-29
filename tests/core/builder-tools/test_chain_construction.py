import pytest

from eth_utils import ValidationError

from eth.chains.base import MiningChain
from eth.consensus.pow import check_pow
from eth.tools.builder.chain import (
    build,
    enable_pow_mining,
    disable_pow_check,
    name,
    fork_at,
    byzantium_at,
    frontier_at,
    homestead_at,
    spurious_dragon_at,
    tangerine_whistle_at,
    constantinople_at,
    genesis,
)
from eth.vm.forks import (
    FrontierVM,
    HomesteadVM,
    TangerineWhistleVM,
    SpuriousDragonVM,
    ByzantiumVM,
    ConstantinopleVM,
)


def test_chain_builder_construct_chain_name():
    chain = build(
        MiningChain,
        name('ChainForTest'),
    )

    assert issubclass(chain, MiningChain)
    assert chain.__name__ == 'ChainForTest'


def test_chain_builder_construct_chain_vm_configuration_single_fork():
    chain = build(
        MiningChain,
        fork_at(FrontierVM, 0),
    )

    assert issubclass(chain, MiningChain)
    assert len(chain.vm_configuration) == 1
    assert chain.vm_configuration[0][0] == 0
    assert chain.vm_configuration[0][1] == FrontierVM


def test_chain_builder_construct_chain_vm_configuration_multiple_forks():
    chain = build(
        MiningChain,
        fork_at(FrontierVM, 0),
        fork_at(HomesteadVM, 5),
    )

    assert issubclass(chain, MiningChain)
    assert len(chain.vm_configuration) == 2
    assert chain.vm_configuration[0][0] == 0
    assert chain.vm_configuration[0][1] == FrontierVM
    assert chain.vm_configuration[1][0] == 5
    assert chain.vm_configuration[1][1] == HomesteadVM


@pytest.mark.parametrize(
    'fork_fn,vm_class',
    (
        (frontier_at, FrontierVM),
        (homestead_at, HomesteadVM),
        (tangerine_whistle_at, TangerineWhistleVM),
        (spurious_dragon_at, SpuriousDragonVM),
        (byzantium_at, ByzantiumVM),
        (constantinople_at, ConstantinopleVM),
    )
)
def test_chain_builder_construct_chain_fork_specific_helpers(fork_fn, vm_class):
    class DummyVM(FrontierVM):
        pass

    class ChainForTest(MiningChain):
        vm_configuration = (
            (0, DummyVM),
        )

    chain = build(
        ChainForTest,
        fork_fn(12),
    )

    assert issubclass(chain, MiningChain)
    assert len(chain.vm_configuration) == 2
    assert chain.vm_configuration[0][0] == 0
    assert chain.vm_configuration[0][1] is DummyVM
    assert chain.vm_configuration[1][0] == 12
    assert chain.vm_configuration[1][1] is vm_class


def test_chain_builder_enable_pow_mining():
    chain = build(
        MiningChain,
        frontier_at(0),
        enable_pow_mining(),
        genesis(),
    )
    block = chain.mine_block()
    check_pow(
        block.number,
        block.header.mining_hash,
        block.header.mix_hash,
        block.header.nonce,
        block.header.difficulty,
    )


def test_chain_builder_without_any_mining_config():
    chain = build(
        MiningChain,
        frontier_at(0),
        genesis(),
    )
    with pytest.raises(ValidationError, match='mix hash mismatch'):
        chain.mine_block()


def test_chain_builder_disable_pow_check():
    chain = build(
        MiningChain,
        frontier_at(0),
        disable_pow_check(),
        genesis(),
    )
    block = chain.mine_block()
    with pytest.raises(ValidationError, match='mix hash mismatch'):
        check_pow(
            block.number,
            block.header.mining_hash,
            block.header.mix_hash,
            block.header.nonce,
            block.header.difficulty,
        )
