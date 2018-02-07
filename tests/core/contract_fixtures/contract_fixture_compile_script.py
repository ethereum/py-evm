
import os
import json

from viper.compile_lll import (
    compile_to_assembly,
    assembly_to_evm,
)
from viper.parser.parser_utils import LLLnode

from eth_utils import (
    encode_hex,
)

from evm.utils.address import generate_CREATE2_contract_address

from tests.core.contract_fixtures.CREATE2_contract import (
    simple_transfer_contract_lll_code,
    CREATE2_contract_lll_code,
    simple_factory_contract_bytecode,
)
from tests.core.contract_fixtures.PAYGAS_contract import (
    simple_forwarder_contract_lll_code,
    PAYGAS_contract_normal_lll_code,
    PAYGAS_contract_triggered_twice_lll_code,
)


DIR = os.path.dirname(__file__)


simple_transfer_contract_bytecode = assembly_to_evm(
    compile_to_assembly(
        LLLnode.from_list(simple_transfer_contract_lll_code)
    )
)


CREATE2_contract_bytecode = assembly_to_evm(
    compile_to_assembly(
        LLLnode.from_list(CREATE2_contract_lll_code)
    )
)


CREATE2_json = {
    "simple_transfer_contract": {
        "bytecode": encode_hex(simple_transfer_contract_bytecode),
        "address": encode_hex(
            generate_CREATE2_contract_address(b'', simple_transfer_contract_bytecode)
        ),
    },
    "CREATE2_contract": {
        "bytecode": encode_hex(CREATE2_contract_bytecode),
        "address": encode_hex(
            generate_CREATE2_contract_address(b'', CREATE2_contract_bytecode)
        ),
    },
    "simple_factory_contract": {
        "bytecode": encode_hex(simple_factory_contract_bytecode),
    }
}


with open(os.path.join(DIR, 'CREATE2_contracts.json'), 'w') as f:
    json.dump(CREATE2_json, f, indent=4, sort_keys=True)


simple_forwarder_contract_bytecode = assembly_to_evm(
    compile_to_assembly(
        LLLnode.from_list(simple_forwarder_contract_lll_code)
    )
)


PAYGAS_contract_normal_bytecode = assembly_to_evm(
    compile_to_assembly(
        LLLnode.from_list(PAYGAS_contract_normal_lll_code)
    )
)


PAYGAS_contract_triggered_twice_bytecode = assembly_to_evm(
    compile_to_assembly(
        LLLnode.from_list(PAYGAS_contract_triggered_twice_lll_code)
    )
)


PAYGAS_json = {
    "simple_forwarder_contract": {
        "bytecode": encode_hex(simple_forwarder_contract_bytecode),
        "address": encode_hex(
            generate_CREATE2_contract_address(b'', simple_forwarder_contract_bytecode)
        ),
    },
    "PAYGAS_contract_normal": {
        "bytecode": encode_hex(PAYGAS_contract_normal_bytecode),
        "address": encode_hex(
            generate_CREATE2_contract_address(b'', PAYGAS_contract_normal_bytecode)
        ),
    },
    "PAYGAS_contract_triggered_twice": {
        "bytecode": encode_hex(PAYGAS_contract_triggered_twice_bytecode),
        "address": encode_hex(
            generate_CREATE2_contract_address(b'', PAYGAS_contract_triggered_twice_bytecode)
        ),
    },
}


with open(os.path.join(DIR, 'PAYGAS_contracts.json'), 'w') as f:
    json.dump(PAYGAS_json, f, indent=4, sort_keys=True)
