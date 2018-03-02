from cytoolz import (
    assoc,
)

from eth_utils import (
    reversed_return,
)

from evm.chains.base import Chain

from evm.vm.forks import (
    FrontierVM as BaseFrontierVM,
    HomesteadVM as BaseHomesteadVM,
    TangerineWhistleVM as BaseTangerineWhistleVM,
    SpuriousDragonVM as BaseSpuriousDragonVM,
)

from evm.utils.chain import (
    generate_vms_by_range,
)


class MaintainGasLimitMixin(object):
    @classmethod
    def create_header_from_parent(cls, parent_header, **header_params):
        """
        Call the parent class method maintaining the same gas_limit as the
        previous block.
        """
        return super(MaintainGasLimitMixin, cls).create_header_from_parent(
            parent_header,
            **assoc(header_params, 'gas_limit', parent_header.gas_limit)
        )


class FrontierTesterVM(MaintainGasLimitMixin, BaseFrontierVM):
    pass


class BaseHomesteadTesterVM(MaintainGasLimitMixin, BaseHomesteadVM):
    pass


class TangerineWhistleTesterVM(MaintainGasLimitMixin, BaseTangerineWhistleVM):
    pass


class SpuriousDragonTesterVM(MaintainGasLimitMixin, BaseSpuriousDragonVM):
    pass


INVALID_FORK_ACTIVATION_MSG = (
    "The {0}-fork activation block may not be null if the {1}-fork block "
    "is non null"
)


@reversed_return
def _generate_vm_configuration(homestead_start_block=None,
                               dao_start_block=None,
                               tangerine_whistle_start_block=None,
                               spurious_dragon_block=None):
    # If no explicit configuration has been passed, configure the vm to start
    # with the latest fork rules at block 0
    no_declared_blocks = (
        spurious_dragon_block is None and
        tangerine_whistle_start_block is None and
        homestead_start_block is None
    )
    if no_declared_blocks:
        yield (0, SpuriousDragonTesterVM)

    if spurious_dragon_block is not None:
        yield (spurious_dragon_block, SpuriousDragonTesterVM)

        remaining_blocks_not_declared = (
            homestead_start_block is None and
            tangerine_whistle_start_block is None
        )
        if spurious_dragon_block > 0 and remaining_blocks_not_declared:
            yield (0, TangerineWhistleTesterVM)

    if tangerine_whistle_start_block is not None:
        yield (tangerine_whistle_start_block, TangerineWhistleTesterVM)

        # If the EIP150 rules do not start at block 0 and homestead_start_block has not
        # been configured for a specific block, configure homestead_start_block to start at
        # block 0.
        if tangerine_whistle_start_block > 0 and homestead_start_block is None:
            HomesteadTesterVM = BaseHomesteadTesterVM.configure(
                dao_fork_block_number=0,
            )
            yield (0, HomesteadTesterVM)

    if homestead_start_block is not None:
        if dao_start_block is False:
            # If dao_start_block support has explicitely been configured as `False` then
            # mark the HomesteadTesterVM as not supporting the fork.
            HomesteadTesterVM = BaseHomesteadTesterVM.configure(support_dao_fork=False)
        elif dao_start_block is not None:
            # Otherwise, if a specific dao_start_block fork block has been set, use it.
            HomesteadTesterVM = BaseHomesteadTesterVM.configure(
                dao_fork_block_number=dao_start_block,
            )
        else:
            # Otherwise, default to the homestead_start_block block as the
            # start of the dao_start_block fork.
            HomesteadTesterVM = BaseHomesteadTesterVM.configure(
                dao_fork_block_number=homestead_start_block,
            )
        yield (homestead_start_block, HomesteadTesterVM)

        # If the homestead_start_block block is configured to start after block 0, set the
        # frontier rules to start at block 0.
        if homestead_start_block > 0:
            yield (0, FrontierTesterVM)


BaseMainnetTesterChain = Chain.configure(
    'MainnetTesterChain',
    vm_configuration=_generate_vm_configuration()
)


class MainnetTesterChain(BaseMainnetTesterChain):
    def validate_seal(self, block):
        """
        We don't validate the proof of work seal on the tester chain.
        """
        pass

    def configure_forks(self,
                        homestead_start_block=None,
                        dao_start_block=None,
                        tangerine_whistle_start_block=None,
                        spurious_dragon_block=None):
        """
        TODO: add support for state_cleanup
        """
        vm_configuration = _generate_vm_configuration(
            homestead_start_block=homestead_start_block,
            dao_start_block=dao_start_block,
            tangerine_whistle_start_block=tangerine_whistle_start_block,
            spurious_dragon_block=spurious_dragon_block,
        )
        self.vms_by_range = generate_vms_by_range(vm_configuration)
