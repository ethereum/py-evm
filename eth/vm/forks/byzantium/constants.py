from eth_utils import denoms

#
# Difficulty
#
BYZANTIUM_DIFFICULTY_ADJUSTMENT_CUTOFF = 9


EIP649_BLOCK_REWARD = 3 * denoms.ether

EIP658_TRANSACTION_STATUS_CODE_FAILURE = b''
EIP658_TRANSACTION_STATUS_CODE_SUCCESS = b'\x01'
