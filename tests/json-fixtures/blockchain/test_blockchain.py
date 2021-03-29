import os
from pathlib import Path
import pytest
import rlp

from eth_utils import (
    to_tuple,
    ValidationError,
)

from eth.rlp.headers import (
    BlockHeader,
)

from eth.tools.rlp import (
    assert_imported_genesis_header_unchanged,
    assert_mined_block_unchanged,
)
from eth.tools._utils.normalization import (
    normalize_blockchain_fixtures,
)
from eth.tools.fixtures import (
    apply_fixture_block_to_chain,
    filter_fixtures,
    generate_fixture_tests,
    genesis_params_from_fixture,
    load_fixture,
    new_chain_from_fixture,
    should_run_slow_tests,
    verify_state,
)


ROOT_PROJECT_DIR = Path(__file__).parents[3]


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'BlockchainTests')


# These are the slowest tests from the full blockchain test run. This list
# should be regenerated occasionally using `--durations 100` - preferably
# several runs, using top N percentile to populate the list incrementally.
# Then sort alphabetically, to reduce churn (lines just being pushed up/down).
SLOWEST_TESTS = {
    ('GeneralStateTests/stAttackTest/ContractCreationSpam.json', 'ContractCreationSpam_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stAttackTest/ContractCreationSpam.json', 'ContractCreationSpam_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stCallCreateCallCodeTest/Call1024BalanceTooLow.json', 'Call1024BalanceTooLow_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stCallCreateCallCodeTest/Call1024PreCalls.json', 'Call1024PreCalls_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stCallCreateCallCodeTest/Call1024PreCalls.json', 'Call1024PreCalls_d0g1v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stCallCreateCallCodeTest/CallRecursiveBombPreCall.json', 'CallRecursiveBombPreCall_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stCallCreateCallCodeTest/Callcode1024BalanceTooLow.json', 'Callcode1024BalanceTooLow_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stChangedEIP150/Call1024BalanceTooLow.json', 'Call1024BalanceTooLow_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stChangedEIP150/Call1024PreCalls.json', 'Call1024PreCalls_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stChangedEIP150/Call1024PreCalls.json', 'Call1024PreCalls_d0g1v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stChangedEIP150/Callcode1024BalanceTooLow.json', 'Callcode1024BalanceTooLow_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stCreate2/Create2OnDepth1024.json', 'Create2OnDepth1024_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stCreate2/Create2Recursive.json', 'Create2Recursive_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stCreate2/Create2Recursive.json', 'Create2Recursive_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stCreate2/Create2Recursive.json', 'Create2Recursive_d0g1v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stCreate2/Create2Recursive.json', 'Create2Recursive_d0g1v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stDelegatecallTestHomestead/Call1024BalanceTooLow.json', 'Call1024BalanceTooLow_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stDelegatecallTestHomestead/Call1024PreCalls.json', 'Call1024PreCalls_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stDelegatecallTestHomestead/Call1024PreCalls.json', 'Call1024PreCalls_d0g1v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stDelegatecallTestHomestead/Delegatecall1024.json', 'Delegatecall1024_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRandom/randomStatetest48.json', 'randomStatetest48_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRandom2/randomStatetest458.json', 'randomStatetest458_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRandom2/randomStatetest467.json', 'randomStatetest467_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRandom2/randomStatetest636.json', 'randomStatetest636_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRandom2/randomStatetest639.json', 'randomStatetest639_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRecursiveCreate/recursiveCreateReturnValue.json', 'recursiveCreateReturnValue_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/LoopCallsDepthThenRevert2.json', 'LoopCallsDepthThenRevert2_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/LoopCallsDepthThenRevert3.json', 'LoopCallsDepthThenRevert3_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/LoopCallsThenRevert.json', 'LoopCallsThenRevert_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/LoopCallsThenRevert.json', 'LoopCallsThenRevert_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/LoopCallsThenRevert.json', 'LoopCallsThenRevert_d0g1v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/LoopCallsThenRevert.json', 'LoopCallsThenRevert_d0g1v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stShift/shiftCombinations.json', 'shiftCombinations_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call1024BalanceTooLow.json', 'static_Call1024BalanceTooLow_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call1024BalanceTooLow2.json', 'static_Call1024BalanceTooLow2_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call1024PreCalls.json', 'static_Call1024PreCalls_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call1024PreCalls2.json', 'static_Call1024PreCalls2_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call1024PreCalls2.json', 'static_Call1024PreCalls2_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call1024PreCalls3.json', 'static_Call1024PreCalls3_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call1MB1024Calldepth.json', 'static_Call1MB1024Calldepth_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000.json', 'static_Call50000_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000.json', 'static_Call50000_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000.json', 'static_Call50000_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000.json', 'static_Call50000_d1g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_ecrec.json', 'static_Call50000_ecrec_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_ecrec.json', 'static_Call50000_ecrec_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_ecrec.json', 'static_Call50000_ecrec_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_ecrec.json', 'static_Call50000_ecrec_d1g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_identity.json', 'static_Call50000_identity_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_identity.json', 'static_Call50000_identity_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_identity.json', 'static_Call50000_identity_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_identity.json', 'static_Call50000_identity_d1g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_identity2.json', 'static_Call50000_identity2_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_identity2.json', 'static_Call50000_identity2_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_identity2.json', 'static_Call50000_identity2_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_identity2.json', 'static_Call50000_identity2_d1g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_rip160.json', 'static_Call50000_rip160_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_rip160.json', 'static_Call50000_rip160_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_rip160.json', 'static_Call50000_rip160_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000_rip160.json', 'static_Call50000_rip160_d1g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000bytesContract50_1.json', 'static_Call50000bytesContract50_1_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000bytesContract50_1.json', 'static_Call50000bytesContract50_1_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000bytesContract50_2.json', 'static_Call50000bytesContract50_2_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Call50000bytesContract50_2.json', 'static_Call50000bytesContract50_2_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_LoopCallsDepthThenRevert2.json', 'static_LoopCallsDepthThenRevert2_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_LoopCallsDepthThenRevert3.json', 'static_LoopCallsDepthThenRevert3_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_LoopCallsThenRevert.json', 'static_LoopCallsThenRevert_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_LoopCallsThenRevert.json', 'static_LoopCallsThenRevert_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_LoopCallsThenRevert.json', 'static_LoopCallsThenRevert_d0g1v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_LoopCallsThenRevert.json', 'static_LoopCallsThenRevert_d0g1v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Return50000_2.json', 'static_Return50000_2_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stStaticCall/static_Return50000_2.json', 'static_Return50000_2_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stSystemOperationsTest/CallRecursiveBomb0_OOG_atMaxCallDepth.json', 'CallRecursiveBomb0_OOG_atMaxCallDepth_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stTimeConsuming/CALLBlake2f_MaxRounds.json', 'CALLBlake2f_MaxRounds_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stTimeConsuming/CALLBlake2f_MaxRounds.json', 'CALLBlake2f_MaxRounds_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stTimeConsuming/static_Call50000_sha256.json', 'static_Call50000_sha256_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stTimeConsuming/static_Call50000_sha256.json', 'static_Call50000_sha256_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stTimeConsuming/static_Call50000_sha256.json', 'static_Call50000_sha256_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stTimeConsuming/static_Call50000_sha256.json', 'static_Call50000_sha256_d1g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_one_point_fail.json', 'ecpairing_one_point_fail_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_three_point_fail_1.json', 'ecpairing_three_point_fail_1_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_three_point_match_1.json', 'ecpairing_three_point_match_1_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_three_point_match_1.json', 'ecpairing_three_point_match_1_d0g3v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_fail_1.json', 'ecpairing_two_point_fail_1_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_fail_2.json', 'ecpairing_two_point_fail_2_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_match_1.json', 'ecpairing_two_point_match_1_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_match_2.json', 'ecpairing_two_point_match_2_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_match_2.json', 'ecpairing_two_point_match_2_d0g3v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_match_3.json', 'ecpairing_two_point_match_3_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_match_3.json', 'ecpairing_two_point_match_3_d0g3v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_match_4.json', 'ecpairing_two_point_match_4_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_match_4.json', 'ecpairing_two_point_match_4_d0g3v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_oog.json', 'ecpairing_two_point_oog_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_point_oog.json', 'ecpairing_two_point_oog_d0g3v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_points_with_one_g2_zero.json', 'ecpairing_two_points_with_one_g2_zero_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/ecpairing_two_points_with_one_g2_zero.json', 'ecpairing_two_points_with_one_g2_zero_d0g3v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/pairingTest.json', 'pairingTest_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/pairingTest.json', 'pairingTest_d0g3v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/pairingTest.json', 'pairingTest_d1g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/pairingTest.json', 'pairingTest_d1g3v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/pairingTest.json', 'pairingTest_d2g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/pairingTest.json', 'pairingTest_d2g3v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/pairingTest.json', 'pairingTest_d3g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/pairingTest.json', 'pairingTest_d4g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/pairingTest.json', 'pairingTest_d5g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stZeroKnowledge/pairingTest.json', 'pairingTest_d5g3v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d8g0v0_Istanbul'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d10g0v0_Istanbul'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d11g0v0_Istanbul'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d12g0v0_Istanbul'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d13g0v0_Istanbul'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d14g0v0_Istanbul'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d8g0v0_Berlin'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d10g0v0_Berlin'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d11g0v0_Berlin'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d12g0v0_Berlin'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d13g0v0_Berlin'),
    ('GeneralStateTests/VMTests/vmPerformance/loopExp.json', 'loopExp_d14g0v0_Berlin'),
    ('GeneralStateTests/VMTests/vmPerformance/loopMul.json', 'loopMul_d0g0v0_Istanbul'),
    ('GeneralStateTests/VMTests/vmPerformance/loopMul.json', 'loopMul_d1g0v0_Istanbul'),
    ('GeneralStateTests/VMTests/vmPerformance/loopMul.json', 'loopMul_d2g0v0_Istanbul'),
    ('GeneralStateTests/VMTests/vmPerformance/loopMul.json', 'loopMul_d0g0v0_Berlin'),
    ('GeneralStateTests/VMTests/vmPerformance/loopMul.json', 'loopMul_d1g0v0_Berlin'),
    ('GeneralStateTests/VMTests/vmPerformance/loopMul.json', 'loopMul_d2g0v0_Berlin'),
    ('InvalidBlocks/bcForgedTest/bcForkBlockTest.json', 'BlockWrongResetGas'),  # noqa: E501
    ('InvalidBlocks/bcForgedTest/bcInvalidRLPTest.json', 'BLOCK_difficulty_TooLarge'),  # noqa: E501
    ('InvalidBlocks/bcMultiChainTest/UncleFromSideChain.json', 'UncleFromSideChain_Constantinople'),  # noqa: E501
    ('TransitionTests/bcHomesteadToDao/DaoTransactions.json', 'DaoTransactions'),  # noqa: E501
    ('TransitionTests/bcHomesteadToDao/DaoTransactions_UncleExtradata.json', 'DaoTransactions_UncleExtradata'),  # noqa: E501
    ('ValidBlocks/bcGasPricerTest/RPC_API_Test.json', 'RPC_API_Test_EIP150'),  # noqa: E501
    ('ValidBlocks/bcGasPricerTest/RPC_API_Test.json', 'RPC_API_Test_EIP158'),  # noqa: E501
    ('ValidBlocks/bcGasPricerTest/RPC_API_Test.json', 'RPC_API_Test_Frontier'),  # noqa: E501
    ('ValidBlocks/bcGasPricerTest/RPC_API_Test.json', 'RPC_API_Test_Homestead'),  # noqa: E501
    ('ValidBlocks/bcRandomBlockhashTest/randomStatetest284BC.json', 'randomStatetest284BC_Byzantium'),  # noqa: E501
    ('ValidBlocks/bcStateTests/randomStatetest94.json', 'randomStatetest94_Byzantium'),  # noqa: E501
    ('ValidBlocks/bcStateTests/randomStatetest94.json', 'randomStatetest94_Constantinople'),  # noqa: E501
    ('ValidBlocks/bcStateTests/randomStatetest94.json', 'randomStatetest94_ConstantinopleFix'),  # noqa: E501
    ('ValidBlocks/bcStateTests/randomStatetest94.json', 'randomStatetest94_Homestead'),  # noqa: E501
    ('ValidBlocks/bcStateTests/randomStatetest94.json', 'randomStatetest94_Istanbul'),  # noqa: E501
    ('ValidBlocks/VMTests/vmPerformance/loop-add-10M.json', 'loop-add-10M_Istanbul'),
    ('ValidBlocks/VMTests/vmPerformance/loop-add-10M.json', 'loop-add-10M_Berlin'),
    ('ValidBlocks/VMTests/vmPerformance/loop-divadd-10M.json', 'loop-divadd-10M_Istanbul'),
    ('ValidBlocks/VMTests/vmPerformance/loop-divadd-10M.json', 'loop-divadd-10M_Berlin'),
    ('ValidBlocks/VMTests/vmPerformance/loop-divadd-unr100-10M.json', 'loop-divadd-unr100-10M_Istanbul'),  # noqa: E501
    ('ValidBlocks/VMTests/vmPerformance/loop-divadd-unr100-10M.json', 'loop-divadd-unr100-10M_Berlin'),  # noqa: E501
    ('ValidBlocks/VMTests/vmPerformance/loop-exp-16b-100k.json', 'loop-exp-16b-100k_Istanbul'),
    ('ValidBlocks/VMTests/vmPerformance/loop-exp-16b-100k.json', 'loop-exp-16b-100k_Berlin'),
    ('ValidBlocks/VMTests/vmPerformance/loop-exp-1b-1M.json', 'loop-exp-1b-1M_Istanbul'),
    ('ValidBlocks/VMTests/vmPerformance/loop-exp-1b-1M.json', 'loop-exp-1b-1M_Berlin'),
    ('ValidBlocks/VMTests/vmPerformance/loop-exp-32b-100k.json', 'loop-exp-32b-100k_Istanbul'),
    ('ValidBlocks/VMTests/vmPerformance/loop-exp-32b-100k.json', 'loop-exp-32b-100k_Berlin'),
    ('ValidBlocks/VMTests/vmPerformance/loop-exp-nop-1M.json', 'loop-exp-nop-1M_Istanbul'),
    ('ValidBlocks/VMTests/vmPerformance/loop-exp-nop-1M.json', 'loop-exp-nop-1M_Berlin'),
    ('ValidBlocks/VMTests/vmPerformance/loop-mul.json', 'loop-mul_Istanbul'),
    ('ValidBlocks/VMTests/vmPerformance/loop-mul.json', 'loop-mul_Berlin'),
    ('ValidBlocks/VMTests/vmPerformance/loop-mulmod-2M.json', 'loop-mulmod-2M_Istanbul'),
    ('ValidBlocks/VMTests/vmPerformance/loop-mulmod-2M.json', 'loop-mulmod-2M_Berlin'),
}


# These are tests that are thought to be incorrect or buggy upstream,
# at the commit currently checked out in submodule `fixtures`.
# Ideally, this list should be empty.
# WHEN ADDING ENTRIES, ALWAYS PROVIDE AN EXPLANATION!
INCORRECT_UPSTREAM_TESTS = {
    # The test considers a "synthetic" scenario (the state described there can't
    # be arrived at using regular consensus rules).
    # * https://github.com/ethereum/py-evm/pull/1224#issuecomment-418775512
    # The result is in conflict with the yellow-paper:
    # * https://github.com/ethereum/py-evm/pull/1224#issuecomment-418800369
    ('GeneralStateTests/stRevertTest/RevertInCreateInInit_d0g0v0.json', 'RevertInCreateInInit_d0g0v0_Byzantium'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/RevertInCreateInInit_d0g0v0.json', 'RevertInCreateInInit_d0g0v0_Constantinople'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/RevertInCreateInInit_d0g0v0.json', 'RevertInCreateInInit_d0g0v0_ConstantinopleFix'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/RevertInCreateInInit.json', 'RevertInCreateInInit_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/RevertInCreateInInit.json', 'RevertInCreateInInit_d0g0v0_Berlin'),  # noqa: E501

    # The CREATE2 variant seems to have been derived from the one above - it, too,
    # has a "synthetic" state, on which py-evm flips.
    # * https://github.com/ethereum/py-evm/pull/1181#issuecomment-446330609
    ('GeneralStateTests/stCreate2/RevertInCreateInInitCreate2_d0g0v0.json', 'RevertInCreateInInitCreate2_d0g0v0_Constantinople'),  # noqa: E501
    ('GeneralStateTests/stCreate2/RevertInCreateInInitCreate2_d0g0v0.json', 'RevertInCreateInInitCreate2_d0g0v0_ConstantinopleFix'),  # noqa: E501
    ('GeneralStateTests/stCreate2/RevertInCreateInInitCreate2.json', 'RevertInCreateInInitCreate2_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stCreate2/RevertInCreateInInitCreate2.json', 'RevertInCreateInInitCreate2_d0g0v0_Berlin'),  # noqa: E501

    # Four variants have been specifically added to test a collision type
    # like the above; therefore, they fail in the same manner.
    # * https://github.com/ethereum/py-evm/pull/1579#issuecomment-446591118
    # Interestingly, d2 passes in Constantinople after a refactor of storage handling,
    # the same test was already passing in ConstantinopleFix. Since the situation is synthetic,
    # not much research went into why, yet.
    ('GeneralStateTests/stSStoreTest/InitCollision_d0g0v0.json', 'InitCollision_d0g0v0_Constantinople'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision_d1g0v0.json', 'InitCollision_d1g0v0_Constantinople'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision_d3g0v0.json', 'InitCollision_d3g0v0_Constantinople'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision_d0g0v0.json', 'InitCollision_d0g0v0_ConstantinopleFix'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision_d1g0v0.json', 'InitCollision_d1g0v0_ConstantinopleFix'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision_d3g0v0.json', 'InitCollision_d3g0v0_ConstantinopleFix'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision.json', 'InitCollision_d0g0v0_Istanbul'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision.json', 'InitCollision_d1g0v0_Istanbul'),
    # The d2 variant started failing again after fixing a long-hidden consensus bug
    # but only in Istanbul, not in Constantinople.
    ('GeneralStateTests/stSStoreTest/InitCollision.json', 'InitCollision_d2g0v0_Istanbul'),
    ('GeneralStateTests/stSStoreTest/InitCollision.json', 'InitCollision_d3g0v0_Istanbul'),
    ('GeneralStateTests/stSStoreTest/InitCollision.json', 'InitCollision_d0g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision.json', 'InitCollision_d1g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision.json', 'InitCollision_d2g0v0_Berlin'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision.json', 'InitCollision_d3g0v0_Berlin'),  # noqa: E501
}


def blockchain_fixture_mark_fn(fixture_path, fixture_name, fixture_fork):
    fixture_id = (fixture_path, fixture_name)

    if fixture_path.startswith('bcExploitTest'):
        return pytest.mark.skip("Exploit tests are slow")
    elif fixture_path.startswith('bcForkStressTest/ForkStressTest.json'):
        return pytest.mark.skip("Fork stress tests are slow.")
    elif fixture_path == 'bcWalletTest/walletReorganizeOwners.json':
        return pytest.mark.skip("Wallet owner reorganization tests are slow")
    elif fixture_id in INCORRECT_UPSTREAM_TESTS:
        return pytest.mark.xfail(reason="Listed in INCORRECT_UPSTREAM_TESTS.")
    elif 'stTransactionTest/zeroSigTransa' in fixture_path:
        return pytest.mark.skip("EIP-86 not supported.")
    elif fixture_id in SLOWEST_TESTS:
        if should_run_slow_tests():
            return
        else:
            return pytest.mark.skip("Skipping slow test")
    elif 'stQuadraticComplexityTest' in fixture_path:
        return pytest.mark.skip("Skipping slow test")


def generate_ignore_fn_for_fork(passed_fork):
    if passed_fork:
        passed_fork = passed_fork.lower()

        def ignore_fn(fixture_path, fixture_key, fixture_fork):
            return fixture_fork.lower() != passed_fork

        return ignore_fn


@to_tuple
def expand_fixtures_forks(all_fixtures):
    for fixture_path, fixture_key in all_fixtures:
        fixture = load_fixture(fixture_path, fixture_key)
        yield fixture_path, fixture_key, fixture['network']


def pytest_generate_tests(metafunc):
    fork = metafunc.config.getoption('fork')
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
        preprocess_fn=expand_fixtures_forks,
        filter_fn=filter_fixtures(
            fixtures_base_dir=BASE_FIXTURE_PATH,
            mark_fn=blockchain_fixture_mark_fn,
            ignore_fn=generate_ignore_fn_for_fork(fork)
        ),
    )


@pytest.fixture
def fixture(fixture_data):
    fixture_path, fixture_key, fixture_fork = fixture_data
    fixture = load_fixture(
        fixture_path,
        fixture_key,
        normalize_blockchain_fixtures,
    )
    return fixture


def test_blockchain_fixtures(fixture_data, fixture):
    try:
        chain = new_chain_from_fixture(fixture)
    except ValueError as e:
        raise AssertionError(f"could not load chain for {fixture_data}") from e

    genesis_params = genesis_params_from_fixture(fixture)
    expected_genesis_header = BlockHeader(**genesis_params)

    # TODO: find out if this is supposed to pass?
    # if 'genesisRLP' in fixture:
    #     assert rlp.encode(genesis_header) == fixture['genesisRLP']

    genesis_block = chain.get_canonical_block_by_number(0)
    genesis_header = genesis_block.header

    assert_imported_genesis_header_unchanged(expected_genesis_header, genesis_header)

    # 1 - mine the genesis block
    # 2 - loop over blocks:
    #     - apply transactions
    #     - mine block
    # 3 - diff resulting state with expected state
    # 4 - check that all previous blocks were valid

    for block_fixture in fixture['blocks']:
        should_be_good_block = 'blockHeader' in block_fixture

        if 'rlp_error' in block_fixture:
            assert not should_be_good_block
            continue

        if should_be_good_block:
            (original_block, executed_block, block_rlp) = apply_fixture_block_to_chain(
                block_fixture,
                chain,
                perform_validation=False  # we manually validate below
            )
            assert_mined_block_unchanged(original_block, executed_block)
            chain.validate_block(original_block)
        else:
            try:
                apply_fixture_block_to_chain(block_fixture, chain)
            except (TypeError, rlp.DecodingError, rlp.DeserializationError, ValidationError):
                # failure is expected on this bad block
                pass
            else:
                raise AssertionError("Block should have caused a validation error")

    latest_block_hash = chain.get_canonical_block_by_number(chain.get_block().number - 1).hash
    if latest_block_hash != fixture['lastblockhash']:
        verify_state(fixture['postState'], chain.get_vm().state)
