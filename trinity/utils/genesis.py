from evm import constants as evm_constants

from cytoolz import (
    compose,
)
from cytoolz.curried import (
    assoc,
)

from eth_utils import (
    to_bytes,
    to_canonical_address,
    to_int,
)
from eth_utils.curried import (
    apply_key_map,
    apply_formatters_to_dict,
    hexstr_if_str,
)


#
# Genesis param helpers
#
GENESIS_PARAMS_KEY_MAP = {
    'extraData': 'extra_data',
    'gasLimit': 'gas_limit',
    'gasUsed': 'gas_used',
    'logsBloom': 'bloom',
    'mixhash': 'mix_hash',
    'parentHash': 'parent_hash',
    'receiptsRoot': 'receipt_root',
    'sha3Uncles': 'uncles_hash',
    'stateRoot': 'state_root',
    'transactionsRoot': 'transaction_root',
}
GENESIS_PARAMS_NORMALIZERS = {
    'parent_hash': hexstr_if_str(to_bytes),
    'uncles_hash': hexstr_if_str(to_bytes),
    'coinbase': to_canonical_address,
    'state_root': hexstr_if_str(to_bytes),
    'transaction_root': hexstr_if_str(to_bytes),
    'receipt_root': hexstr_if_str(to_bytes),
    'bloom': hexstr_if_str(to_int),
    'difficulty': hexstr_if_str(to_int),
    'block_number': hexstr_if_str(to_int),
    'gas_limit': hexstr_if_str(to_int),
    'gas_used': hexstr_if_str(to_int),
    'timestamp': hexstr_if_str(to_int),
    'extra_data': hexstr_if_str(to_bytes),
    'mix_hash': hexstr_if_str(to_bytes),
    'nonce': hexstr_if_str(to_bytes),
}
format_genesis_params = apply_formatters_to_dict(GENESIS_PARAMS_NORMALIZERS)


normalize_genesis_params = compose(
    format_genesis_params,
    assoc(key='block_number', value=evm_constants.GENESIS_BLOCK_NUMBER),
    apply_key_map(GENESIS_PARAMS_KEY_MAP),
)
