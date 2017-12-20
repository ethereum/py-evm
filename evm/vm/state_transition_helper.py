import copy
import logging
import traceback


logger = logging.getLogger("evm.research.state_transition_helper")


def apply_transaction(transaction, block, prev_vm, chaindb):
    """
    Apply transaction to the block, return the result with a new block object

    Original Goal: apply_transaction(stateobj, db, blockdata, transaction)
    -> state_obj', reads, writes
    """
    # TODO: try to use simplier StateObj object instead of VM as the
    # state transition container?

    # init vm
    vm = copy.deepcopy(prev_vm)
    vm.chaindb = chaindb

    # result
    success = True
    reads = None
    writes = None

    try:
        vm.set_stateless(True)
        computation = vm.apply_transaction_to_block(
            transaction,
            block,
            vm.chaindb,
        )
        vm.set_stateless(False)
        if computation.is_error:
            success = False
    except Exception as e:
        # FIXME: any specific exception type in this function?
        logger.error(
            "Unexpected error when handling remote msg: {}".format(traceback.format_exc()))
        success = False

    reads = vm.reads
    writes = vm.writes

    return success, reads, writes, vm.block
