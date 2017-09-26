from cytoolz import (
    assoc,
)

from eth_utils import (
    reversed_return,
)

from evm import (
    Chain,
)

from evm.vm.flavors import (
    FrontierVM as BaseFrontierVM,
    HomesteadVM as BaseHomesteadVM,
    EIP150VM as BaseEIP150VM,
)

from evm.utils.chain import (
    generate_vms_by_range,
)


def chfp_method_factory(parent_class):
    def create_tester_header_from_parent(vm_class, parent_header, **header_params):
        """
        Creates and initializes a new block header from the provided
        `parent_header`.
        """
        return parent_class.create_header_from_parent(
            parent_header,
            **assoc(header_params, 'gas_limit', parent_header.gas_limit)
        )
    return create_tester_header_from_parent


FrontierTesterVM = BaseFrontierVM.configure(
    name='FrontierTesterVM',
    create_header_from_parent=classmethod(chfp_method_factory(BaseFrontierVM)),
)


BaseHomesteadTesterVM = BaseHomesteadVM.configure(
    name='HomesteadTesterVM',
    create_header_from_parent=classmethod(chfp_method_factory(BaseHomesteadVM)),
)


EIP150TesterVM = BaseEIP150VM.configure(
    name='EIP150TesterVM',
    create_header_from_parent=classmethod(chfp_method_factory(BaseEIP150VM)),
)


INVALID_FORK_ACTIVATION_MSG = (
    "The {0}-fork activation block may not be null if the {1}-fork block "
    "is non null"
)


@reversed_return
def _generate_vm_configuration(homestead=None, dao=None, anti_dos=None):
    # If no explicit configuration has been passed, configure the vm to start
    # with the latest fork rules at block 0
    if anti_dos is None and homestead is None:
        yield (0, EIP150TesterVM)

    if anti_dos is not None:
        yield (anti_dos, EIP150TesterVM)

        # If the EIP150 rules do not start at block 0 and homestead has not
        # been configured for a specific block, configure homestead to start at
        # block 0.
        if anti_dos > 0 and homestead is None:
            HomesteadTesterVM = BaseHomesteadTesterVM.configure(
                dao_fork_block_number=0,
            )
            yield (0, HomesteadTesterVM)

    if homestead is not None:
        if dao is False:
            # If dao support has explicitely been configured as `False` then
            # mark the HomesteadTesterVM as not supporting the fork.
            HomesteadTesterVM = BaseHomesteadTesterVM.configure(support_dao_fork=False)
        elif dao is not None:
            # Otherwise, if a specific dao fork block has been set, use it.
            HomesteadTesterVM = BaseHomesteadTesterVM.configure(dao_fork_block_number=dao)
        else:
            # Otherwise, default to the homestead block as the start of the dao fork.
            HomesteadTesterVM = BaseHomesteadTesterVM.configure(dao_fork_block_number=homestead)
        yield (homestead, HomesteadTesterVM)

        # If the homestead block is configured to start after block 0, set the
        # frontier rules to start at block 0.
        if homestead > 0:
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

    def configure_forks(self, homestead=None, dao=None, anti_dos=0):
        """
        TODO: add support for state_cleanup
        """
        vm_configuration = _generate_vm_configuration(
            homestead=homestead,
            dao=dao,
            anti_dos=anti_dos,
        )
        self.vms_by_range = generate_vms_by_range(vm_configuration)
