import os
import json

from evm.utils.test_builder.test_builder import (
    fill_test,
)
from evm.utils.test_builder.formatters import (
    filler_formatter,
)
from evm.utils.test_builder.builder_utils import (
    get_test_name,
)

from eth_utils import (
    keccak,
)

from evm.utils.hexadecimal import (
    encode_hex,
)

from tests.fillers.vm_fillers.paygas_fillers import (
    paygas_omitted_test,
    paygas_normal_test,
    paygas_zero_gas_price_test,
    paygas_repeated_test,
    paygas_repeated_same_gasprice_test,
    paygas_insufficient_balance_test,
    paygas_after_call_test,
    paygas_in_call_test,
    paygas_fail_before_test,
    paygas_fail_thereafter_test,
)


PARENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PARENT_DIR, "json")
FILLER_PARENT_DIR = os.path.join(OUTPUT_DIR, "fillers")
TEST_PARENT_DIR = os.path.join(OUTPUT_DIR, "tests")


DIR_STRUCTURE = {
    ("GeneralStateTestFiller", "GeneralStateTests"): {
        "stPaygas": [
            paygas_omitted_test,
            paygas_normal_test,
            paygas_zero_gas_price_test,
            paygas_repeated_test,
            paygas_repeated_same_gasprice_test,
            paygas_insufficient_balance_test,
            paygas_after_call_test,
            paygas_in_call_test,
            paygas_fail_before_test,
            paygas_fail_thereafter_test,
        ]
    }
}


if __name__ == "__main__":
    for (filler_dir, test_dir), test_groups in DIR_STRUCTURE.items():
        for test_group, tests in test_groups.items():
            for filler, filler_kwargs in tests:
                test_name = get_test_name(filler)
                filename = test_name + ".json"

                filler_src_path = os.path.join(filler_dir, test_group, filename)
                filler_path = os.path.join(FILLER_PARENT_DIR, filler_src_path)
                test_path = os.path.join(TEST_PARENT_DIR, test_dir, test_group, filename)

                for path in [filler_path, test_path]:
                    os.makedirs(os.path.dirname(path), exist_ok=True)

                formatted_filler = filler_formatter(filler)
                filler_string = json.dumps(formatted_filler, indent=4, sort_keys=True)
                with open(filler_path, "w") as filler_file:
                    filler_file.write(filler_string)

                filler_hash = keccak(filler_string.encode("ascii"))
                info = {
                    "source": filler_src_path,
                    "sourceHash": encode_hex(filler_hash),
                }

                test = fill_test(filler, info=info, **filler_kwargs or {})
                with open(test_path, "w") as test_file:
                    json.dump(test, test_file, indent=4, sort_keys=True)
